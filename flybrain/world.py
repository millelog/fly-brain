"""Arena: a 2D world the brain steers a Fly through by smell. One tick() per Frame, lock-step with the brain."""
import json
import math
import queue
import struct

import numpy as np
import torch

from .model import Brain, Params

SIZE = 100.0  # mm, square arena, origin bottom-left
TRAILER = "<3f5fI"  # appended to each Frame: pose x, y, theta; EMA Hz of DN; feeds
DN = ["dnp09", "mdn", "dna02_l", "dna02_r", "shiu_mn9"]
GAINS = dict(g_f=0.2, g_b=0.2, g_t=0.01, v_base=5.0, vmax=30.0, noise=1.0, r0=2.0, r_max=150.0, k=0.3,
             antenna=0.5, mn9_thr=20.0)


class World:
    def __init__(self, brain: Brain, window_ms=10.0, seed=0):
        self.brain, self.window = brain, window_ms
        self.rate = torch.zeros(brain.n, device=brain.device)
        self.np_idx = {k: brain.pop(k) for k in DN + ["orn_food_l", "orn_food_r", "sugar_grn"]}
        self.idx = {k: torch.tensor(v, device=brain.device) for k, v in self.np_idx.items()}
        self.sources, self.patches, self.wind, self.gains = {}, {}, None, dict(GAINS)
        self.pokes, self.cmds, self.rec, self.events = [], queue.Queue(), None, []
        self.paused, self.dt, self.seed = False, brain.p.dt, seed
        self.reset()

    def reset(self, dt=None, seed=None):
        self.dt, self.seed = dt or self.dt, self.seed if seed is None else seed
        self.brain.p = Params(dt=self.dt)
        self.rate.zero_()
        self.gen = self.brain.frames(1e9, self.rate, self.window, self.seed)
        self.rng = np.random.default_rng(self.seed)
        self.pose = np.array([SIZE / 2, SIZE / 2, 0.0])
        self.start = self.pose.copy()
        self.ema = dict.fromkeys(DN, 0.0)
        self.t, self.feeds, self.feeding, self.pokes = 0.0, 0, False, []

    # --- commands (drained on the brain thread, so world state has one writer) ---
    def apply(self, m):
        c = m.get("cmd")
        if c == "source":
            self.sources[m["id"]] = dict(x=m["x"], y=m["y"], amp=m.get("amp", 1.0), sigma=m.get("sigma", 20.0))
        elif c == "patch":
            self.patches[m["id"]] = dict(x=m["x"], y=m["y"], r=m.get("r", 5.0))
        elif c == "delete":
            (self.sources if m["kind"] == "source" else self.patches).pop(m["id"], None)
        elif c == "fly":
            for i, k in enumerate("xy"):
                if k in m: self.pose[i] = min(SIZE, max(0.0, m[k]))
            if "theta" in m: self.pose[2] = m["theta"]
            self.start = self.pose.copy()
        elif c == "pause":
            self.paused = bool(m["on"])
        elif c == "reset":
            self.reset(m.get("dt"), m.get("seed"))
        elif c == "wind":
            self.wind = m.get("dir")
        elif c == "gains":
            self.gains.update({k: float(v) for k, v in m.items() if k in GAINS})
        elif c == "poke":
            ix = self.brain.pop(m["pop"]) if "pop" in m else np.asarray(m["idx"])
            self.pokes.append([torch.tensor(ix, device=self.brain.device), float(m["rate"]), max(1, round(m.get("ms", 100) / self.window))])
        elif c == "record":
            self.rec = [] if m["on"] else None
        elif c == "save":
            self.save(m["path"])
        self.events.append((self.t, m))

    def state(self):
        return dict(sources=self.sources, patches=self.patches, wind=self.wind, gains=self.gains, paused=self.paused,
                    dt=self.dt, seed=self.seed, t=self.t, feeds=self.feeds, start=self.start.tolist(), size=SIZE)

    # --- physics ---
    def conc(self, x, y):
        """Odor concentration at (x, y): sum of Gaussian sources, stretched 3x downwind if wind is set."""
        c = 0.0
        for s in self.sources.values():
            dx, dy = x - s["x"], y - s["y"]
            if self.wind is None:
                c += s["amp"] * math.exp(-(dx * dx + dy * dy) / (2 * s["sigma"] ** 2))
            else:
                u = dx * math.cos(self.wind) + dy * math.sin(self.wind)  # along-wind
                w = -dx * math.sin(self.wind) + dy * math.cos(self.wind)
                su = s["sigma"] * (3.0 if u > 0 else 1.0)
                c += s["amp"] * math.exp(-(u * u / (2 * su * su) + w * w / (2 * s["sigma"] ** 2)))
        return c

    def tick(self):
        """Advance one Frame. Returns the wire bytes (Frame + TRAILER) or None when paused."""
        while not self.cmds.empty():
            self.apply(self.cmds.get_nowait())
        if self.paused:
            return None
        G = self.gains
        t, idx, c = next(self.gen)
        self.t = t
        cnt = np.zeros(self.brain.n, dtype=np.float32)
        cnt[idx] = c
        a = 1 - math.exp(-self.window / 50.0)
        for k in DN:
            self.ema[k] += a * (cnt[self.np_idx[k]].mean() * 1000 / self.window - self.ema[k])
        e = self.ema
        v = min(G["vmax"], G["v_base"] + G["g_f"] * e["dnp09"] - G["g_b"] * e["mdn"])
        w = G["g_t"] * (e["dna02_l"] - e["dna02_r"]) + G["noise"] * self.rng.standard_normal()
        dt = self.window / 1000.0
        x, y, th = self.pose
        th += w * dt
        x = min(SIZE, max(0.0, x + v * math.cos(th) * dt))  # per-axis clip = slide along walls
        y = min(SIZE, max(0.0, y + v * math.sin(th) * dt))
        self.pose[:] = x, y, th
        # Sense: two antennae at ±30° drive the food-odor ORNs on their side.
        d = G["antenna"]
        cl = self.conc(x + d * math.cos(th + 0.52), y + d * math.sin(th + 0.52))
        cr = self.conc(x + d * math.cos(th - 0.52), y + d * math.sin(th - 0.52))
        self.rate.zero_()
        self.rate[self.idx["orn_food_l"]] = G["r0"] + G["r_max"] * cl / (cl + G["k"])
        self.rate[self.idx["orn_food_r"]] = G["r0"] + G["r_max"] * cr / (cr + G["k"])
        on = any((x - p["x"]) ** 2 + (y - p["y"]) ** 2 < p["r"] ** 2 for p in self.patches.values())
        if on:
            self.rate[self.idx["sugar_grn"]] = 150.0
        feeding = on and e["shiu_mn9"] > G["mn9_thr"]
        self.feeds += feeding and not self.feeding  # rising edge
        self.feeding = feeding
        for p in self.pokes:
            self.rate[p[0]] += p[1]
            p[2] -= 1
        self.pokes = [p for p in self.pokes if p[2] > 0]
        buf = pack_frame(t, idx, c) + struct.pack(TRAILER, x, y, th, *(e[k] for k in DN), self.feeds)
        if self.rec is not None:
            self.rec.append((t, idx, c, self.pose.copy(), [e[k] for k in DN], self.feeds))
        return buf

    def save(self, path):
        """Trial recording: Frames + arena trailer per Frame + the command log, replayable without a GPU."""
        r = self.rec or []
        np.savez_compressed(path, t=np.array([f[0] for f in r]), idx=np.concatenate([f[1] for f in r] or [np.zeros(0, np.uint32)]),
                            counts=np.concatenate([f[2] for f in r] or [np.zeros(0, np.uint16)]),
                            offsets=np.cumsum([0] + [len(f[1]) for f in r]), pose=np.array([f[3] for f in r]).reshape(-1, 3),
                            ema=np.array([f[4] for f in r]).reshape(-1, len(DN)), feeds=np.array([f[5] for f in r]),
                            events=json.dumps(self.events), state=json.dumps(self.state()))


def pack_frame(t, idx, c):
    return struct.pack("<fI", t, len(idx)) + idx.astype(np.uint32).tobytes() + c.astype(np.uint16).tobytes()
