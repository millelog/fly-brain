# fly-brain

Whole-brain spiking simulation of the adult *Drosophila* connectome (FlyWire v783: 138,639 neurons, 15.1 M weighted
connections) with a live 3D viewer. Model and parameters follow Shiu et al. 2024 (*Nature*), "A Drosophila computational
brain model reveals sensorimotor processing". Vocabulary is in `CONTEXT.md`.

## Run locally (CPU or CUDA)

```bash
scripts/fetch_data.sh                      # ~135 MB into data/
uv sync
uv run pytest                              # milestone 1: sugar GRNs -> MN9 fires
uv run python -m flybrain.model            # headless trial, prints Readout rates and wall time
uv run uvicorn flybrain.server:app --port 8420   # viewer at http://localhost:8420
```

## Run on gpu1 (Docker)

```bash
scripts/fetch_data.sh && docker compose up -d --build   # http://gpu1.lan:8420
```

## How it works

- `flybrain/data.py` loads the connectome as CSR by presynaptic neuron and joins FlyWire annotations.
- `flybrain/model.py` is the LIF step loop. Synaptic input is gathered only for neurons that spiked (event-driven), so a
  step costs roughly proportional to activity, not to the 15 M edges. dt = 0.1 ms; ~7 s wall per biological second on a CPU.
- `flybrain/populations.py` names Populations (annotation queries or root-id lists) used as Stimuli and Readouts.
- `flybrain/server.py` streams Frames (10 ms windows of spike counts) over a WebSocket to `static/index.html`, a three.js
  point cloud of soma positions that glows where neurons fire.

Data sources: [eonsystemspbc/fly-brain](https://github.com/eonsystemspbc/fly-brain) (Shiu-format v783 weights),
[flyconnectome/flywire_annotations](https://github.com/flyconnectome/flywire_annotations) (cell types, soma positions).
