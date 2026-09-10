# fly-brain — Glossary

Ubiquitous language for this repo. Terms are defined once here; code and docs use them exactly.

- **Neuron** — one proofread FlyWire v783 cell, identified by its root id. Inside the model it has a dense index 0..N-1.
- **Connection** — a directed Neuron pair with a signed weight. Positive means excitatory (acetylcholine, monoamines), negative means inhibitory (GABA, glutamate). Magnitude is proportional to the synapse count.
- **Population** — a named set of Neurons, selected either by an annotation query (cell type, class, side) or an explicit list of root ids.
- **Stimulus** — a Poisson spike drive at a given rate applied to a Population for the duration of a Trial.
- **Readout** — a Population whose firing is reported and interpreted, for example motor neurons or descending neurons.
- **Trial** — one run of the model: a duration, a timestep, a set of Stimuli and a set of Readouts.
- **Frame** — the spikes of one visualization window, aggregated as (Neuron index, spike count) pairs.
- **Soma position** — the annotated cell-body coordinate of a Neuron. Some Neurons have none and are simulated but not drawn.
