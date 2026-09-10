# 0001 — Hand-written PyTorch LIF loop instead of a spiking simulator

Date: 2026-09-10 · Status: accepted

## Context
The Shiu et al. 2024 whole-brain model is published in Brian2 and has been ported to Brian2CUDA, NEST GPU and GeNN
(eonsystems/fly-brain). NEST GPU is the fastest measured backend. We want live streaming of activity to a browser and,
later, a closed-loop arena that feeds sensory input every step.

## Decision
Implement the LIF model as a plain PyTorch step loop (one module, sparse CSR matvec) that runs unchanged on CPU and CUDA.

## Consequences
- We own the step loop, so per-step input injection and Frame emission are trivial. Simulators make this awkward.
- Same code on dev1 (CPU) and gpu1 (GTX 1080, Pascal, CUDA 12.x wheels only).
- Roughly 5-10x slower than NEST GPU per published benchmarks. Acceptable for the current scale; revisit if wall time per
  biological second becomes the limit, at which point the viz and arena interfaces are the contract to preserve.
