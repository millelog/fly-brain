# 0002 — Decode locomotion from descending neurons

Date: 2026-09-10 · Status: accepted

## Context
The closed-loop Arena needs the brain to move the Fly. FlyWire v783 is the brain only: its motor neurons drive the
proboscis, neck, antennae and eyes. Leg and wing motor neurons live in the ventral nerve cord, which is a separate
dataset (MANC/FANC) with no matched connectivity to these neurons in our data. The brain's only route to locomotion here
is its ~1300 descending neurons.

## Decision
The Motor Map reads named descending neurons and turns their rates into a unicycle command: DNp09 forward, MDN backward,
DNa02 left minus right for turning (ipsiversive, per Rayshubskiy et al. and Cheong et al. 2024). Gains are tunable at
run time. A DN screen script (`scripts/dn_screen.py`) ranks all descending neurons by left/right asymmetry so the map
can be revised from evidence rather than literature alone.

## Consequences
- The Fly's behaviour is a hand-made reading of a few neurons, not a simulated body. Findings about "chemotaxis" are
  findings about those neurons under this map.
- Alternatives rejected: a fitted decoder over all DNs (no ground-truth behaviour to fit to), and attaching a VNC model
  (not in the dataset; would be a new project). Either can replace the Motor Map later; the World's Tick interface is
  the contract to keep.
- First DN screen (2026-09-10, raw weights, dt 0.1 ms, 100 Hz on food ORNs): DNp09 and MDN silent, only the left DNa02
  active (≈60 Hz regardless of input side), no DN with a side asymmetry above a few Hz. Steering does not emerge from the
  default map with raw weights; the benchmark script measures how far off it is.
