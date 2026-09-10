# fly-brain

![viewer](docs/viewer.png)

Whole-brain spiking simulation of the adult *Drosophila* connectome (FlyWire v783: 138,639 neurons, 15.1 M weighted
connections) steering a fly through a 2D arena by smell, with a live 3D brain viewer you can slice, fade and poke. Model and parameters follow Shiu et al. 2024 (*Nature*), "A Drosophila computational
brain model reveals sensorimotor processing". Vocabulary is in `CONTEXT.md`.

## Run locally (CPU or CUDA)

```bash
scripts/fetch_data.sh                      # ~135 MB into data/
uv sync
uv run pytest                              # milestone 1: sugar GRNs -> MN9 fires
uv run python -m flybrain.model            # headless trial, prints Readout rates and wall time
uv run uvicorn flybrain.server:app --port 8420   # arena + viewer at http://localhost:8420
uv run python scripts/dn_screen.py                # which descending neurons respond to left vs right odor
uv run python scripts/benchmark.py --episodes 10  # chemotaxis index, odor on vs off
REPLAY=trial.npz uv run uvicorn flybrain.server:app --port 8420   # scrub a recording, no GPU needed
```

## Arena (milestone 2)

The server hosts one shared World: a 100 mm square arena, a Fly, odor sources and sugar patches. Every browser tab sees
the same World and can change it. Each Tick (one 10 ms Frame) the loop runs brain → descending-neuron rates → Fly pose →
odor concentration at each antenna → ORN stimulus rates for the next Frame. Bio time runs at whatever the GPU gives
(~0.2x real time on a GTX 1080).

- **Sense**: odor sources are Gaussians (stretched 3x downwind when wind is set). Concentration at the left/right
  antenna drives the food-odor ORNs (DM1, DM2, DM4, VA2) on that side: `r = r0 + r_max·c/(c+k)`. Over a sugar patch, the
  sugar GRNs get 150 Hz; a Feed is counted when MN9 fires above threshold.
- **Motor Map**: `v = v_base + g_f·DNp09 − g_b·MDN`, `ω = g_t·(DNa02_L − DNa02_R) + noise`. Every gain is a slider.
  See `docs/adr/0002` for why locomotion is decoded from descending neurons.
- **Interact**: click = odor source, shift-click = sugar patch, drag to move, right-drag the fly to set heading, Delete
  removes, wind and dt inputs, pause/reset, record/save. Poke any Population or a single neuron at a rate for a duration.
- **Brain view**: axis-aligned and view-aligned clip slabs, opacity per super class (optic lobes start at 25%), "activity
  only" fades silent neurons, "isolate" keeps only the selected neuron, its synaptic partners and the Readouts. Click a
  neuron for type, side, transmitter, live rate and strongest partners; pin it for a spike trace. Neuropil hulls come from
  `flybrain/static/neuropils.glb` (`scripts/export_neuropils.py`, one-time export via fafbseg).

First result (raw weights, dt 0.1 ms): DNp09 and MDN never fire, only the left DNa02 does, and no descending neuron is
lateralized by odor side, so the default Motor Map does not produce chemotaxis. `scripts/benchmark.py` measures it;
`scripts/dn_screen.py` is where the next Motor Map comes from.

## Run on gpu1 (Docker)

gpu1 has no GitHub credentials for this private repo, so sync the tree from dev1 (data included, saves the download):

```bash
rsync -az --delete --exclude .venv --exclude .git -e "ssh -i ~/.ssh/homelab_ed25519" ./ millelog@gpu1.lan:apps/fly-brain/
ssh -i ~/.ssh/homelab_ed25519 millelog@gpu1.lan 'cd apps/fly-brain && docker compose up -d --build'   # http://gpu1.lan:8420
```

Measured, 1 s biological at dt 0.1 ms, sugar stimulus: GTX 1080 5.1 s wall, dev1 CPU (Ryzen 3600X) 7 s wall. The GPU is
kernel-launch bound at this activity level; raising dt or batching trials is the lever if it ever matters. Image is 14 GB
(CUDA wheels); container idles at ~1 GB RAM and 320 MB VRAM.

## How it works

- `flybrain/data.py` loads the connectome as CSR by presynaptic neuron and joins FlyWire annotations.
- `flybrain/model.py` is the LIF step loop. Synaptic input is gathered only for neurons that spiked (event-driven), so a
  step costs roughly proportional to activity, not to the 15 M edges. dt = 0.1 ms; ~7 s wall per biological second on a CPU.
- `flybrain/populations.py` names Populations (annotation queries or root-id lists) used as Stimuli and Readouts.
- `flybrain/world.py` is the Arena: one `tick()` per Frame applies queued commands, reads DN rates, moves the Fly and
  writes the next stimulus rates into the tensor the brain loop reads.
- `flybrain/server.py` runs one World on a thread and fans out Frames (10 ms windows of spike counts, plus a pose/rate
  trailer) over WebSockets to `static/index.html`: `arena.js` (2D canvas) and `brain.js` (three.js soma cloud).

Data sources: [eonsystemspbc/fly-brain](https://github.com/eonsystemspbc/fly-brain) (Shiu-format v783 weights),
[flyconnectome/flywire_annotations](https://github.com/flyconnectome/flywire_annotations) (cell types, soma positions).
