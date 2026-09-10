"""Whole-brain LIF model (Shiu et al. 2024 parameters) as a plain PyTorch step loop."""
import argparse
import time
from dataclasses import dataclass

import numpy as np
import torch

from . import data, populations


@dataclass
class Params:
    dt: float = 0.1        # ms
    v0: float = -52.0      # rest = reset, mV
    vth: float = -45.0     # threshold, mV
    tau_m: float = 20.0    # membrane, ms (paper text says 11; the released code and its ports use 20)
    tau_syn: float = 5.0   # synaptic decay, ms
    t_refrac: float = 2.2  # ms
    t_delay: float = 1.8   # ms
    stim_kick: float = 0.275 * 250  # mV per Poisson event; forces a spike (Shiu f_poi)


def pick_device(name="auto"):
    if name != "auto":
        return torch.device(name)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


class Brain:
    def __init__(self, device="auto", params: Params | None = None, min_synapses=1):
        self.device = pick_device(device)
        self.p = params or Params()
        self.neurons = data.load_neurons()
        self.ptr, self.post, self.w = data.load_weights(self.device, min_synapses)
        self.n = len(self.neurons)

    def synaptic_input(self, spikes):
        """Sum of outgoing weights of spiking neurons onto each postsynaptic neuron (event-driven gather)."""
        pre = spikes.nonzero().squeeze(1)
        out = torch.zeros(self.n, device=self.device)
        if len(pre) == 0:
            return out
        starts, lens = self.ptr[pre], self.ptr[pre + 1] - self.ptr[pre]
        seg = torch.repeat_interleave(starts - (lens.cumsum(0) - lens), lens) + torch.arange(int(lens.sum()), device=self.device)
        return out.index_add_(0, self.post[seg], self.w[seg])

    def pop(self, name):
        return populations.resolve(name, self.neurons)

    def frames(self, duration_ms, stimuli: dict[str, float], window_ms=10.0, seed=0):
        """Yield Frames (t_ms, idx, counts) every `window_ms`. `stimuli` maps Population name -> Poisson rate in Hz."""
        p, n, dev = self.p, self.n, self.device
        gen = torch.Generator(device=dev).manual_seed(seed)
        steps, D = round(duration_ms / p.dt), round(p.t_delay / p.dt)
        refrac_steps = torch.full((n,), round(p.t_refrac / p.dt), device=dev)
        stim_idx = torch.cat([torch.tensor(self.pop(k), device=dev) for k in stimuli]) if stimuli else torch.empty(0, dtype=torch.long, device=dev)
        stim_p = torch.cat([torch.full((len(self.pop(k)),), r * p.dt / 1000.0, device=dev) for k, r in stimuli.items()]) if stimuli else None
        refrac_steps[stim_idx] = 0  # Shiu: no refractory period for stimulated neurons

        v = torch.full((n,), p.v0, device=dev)
        g = torch.zeros(n, device=dev)
        refrac = torch.zeros(n, dtype=torch.long, device=dev)
        ring = torch.zeros(D + 1, n, dtype=torch.bool, device=dev)  # spike vectors, delivered D steps later
        counts = torch.zeros(n, device=dev)
        win_steps = round(window_ms / p.dt)
        a_syn, a_mem = p.dt / p.tau_syn, p.dt / p.tau_m

        for t in range(steps):
            active = refrac <= 0
            delayed = ring[t % (D + 1)]
            syn_in = self.synaptic_input(delayed)
            g = torch.where(active, g - a_syn * g, g) + syn_in  # on_pre applies even while refractory
            v = torch.where(active, v + a_mem * (p.v0 - v + g), v)
            if stim_p is not None:
                v[stim_idx] += p.stim_kick * torch.bernoulli(stim_p, generator=gen)
            spk = (v > p.vth) & active
            v = torch.where(spk, torch.full_like(v, p.v0), v)
            g = torch.where(spk, torch.zeros_like(g), g)
            refrac = torch.where(spk, refrac_steps, refrac - 1)
            ring[t % (D + 1)] = spk
            counts += spk
            if (t + 1) % win_steps == 0:
                idx = counts.nonzero().squeeze(1)
                yield (t + 1) * p.dt, idx.cpu().numpy(), counts[idx].cpu().numpy().astype(np.uint16)
                counts.zero_()

    def rates(self, duration_ms, stimuli, readouts: list[str], **kw) -> dict[str, float]:
        """Mean firing rate (Hz) per Readout Population over a Trial."""
        total = np.zeros(self.n)
        for _, idx, c in self.frames(duration_ms, stimuli, **kw):
            total[idx] += c
        return {r: float(total[self.pop(r)].mean() * 1000.0 / duration_ms) for r in readouts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stim", nargs="*", default=["shiu_sugar"])
    ap.add_argument("--rate", type=float, default=150.0)
    ap.add_argument("--readout", nargs="*", default=["shiu_mn9", "proboscis_mn", "ingestion_mn", "motor"])
    ap.add_argument("--duration", type=float, default=1000.0)
    ap.add_argument("--dt", type=float, default=0.1)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--record", help="save Frames to this .npz")
    a = ap.parse_args()
    b = Brain(a.device, Params(dt=a.dt))
    print(f"device={b.device} neurons={b.n} edges={len(b.w)}")
    t0, frames = time.perf_counter(), []
    for f in b.frames(a.duration, {s: a.rate for s in a.stim}):
        frames.append(f)
    wall = time.perf_counter() - t0
    print(f"{a.duration:.0f} ms biological in {wall:.1f} s wall ({wall / a.duration * 1000:.1f} s per bio-second)")
    total = np.zeros(b.n)
    for _, idx, c in frames:
        total[idx] += c
    for r in a.readout:
        print(f"{r:14s} {total[b.pop(r)].mean() * 1000 / a.duration:7.1f} Hz over {len(b.pop(r))} neurons")
    print(f"active neurons: {(total > 0).sum()}")
    if a.record:
        np.savez_compressed(a.record, t=np.array([f[0] for f in frames]),
                            idx=np.concatenate([f[1] for f in frames]), counts=np.concatenate([f[2] for f in frames]),
                            offsets=np.cumsum([0] + [len(f[1]) for f in frames]))


if __name__ == "__main__":
    main()
