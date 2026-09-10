# fly-brain — Glossary

Ubiquitous language for this repo. Terms are defined once here; code and docs use them exactly.

- **Neuron** — one proofread FlyWire v783 cell, identified by its root id. Inside the model it has a dense index 0..N-1.
- **Connection** — a directed Neuron pair with a signed weight. Positive means excitatory (acetylcholine, monoamines), negative means inhibitory (GABA, glutamate). Magnitude is proportional to the synapse count.
- **Population** — a named set of Neurons, selected either by an annotation query (cell type, class, side) or an explicit list of root ids.
- **Stimulus** — a Poisson spike drive at a given rate applied to a Population. The rate may change every Tick.
- **Poke** — a manual, transient Stimulus applied by a person to a Population or a single Neuron.
- **Readout** — a Population whose firing is reported and interpreted, for example motor neurons or descending neurons.
- **Frame** — the spikes of one visualization window, aggregated as (Neuron index, spike count) pairs.
- **Tick** — one update of the Arena. A Tick and a Frame cover the same window; the World advances in lock-step with the brain.
- **World** — the persistent, shared state a server hosts: the brain, the Arena and everything in it. It runs indefinitely; every viewer sees the same World.
- **Trial** — one bounded episode of a World: a duration, a timestep, a starting pose and a set of Stimuli and Readouts.
- **Arena** — the two-dimensional, walled space the Fly moves in.
- **Fly** — the simulated animal's pose in the Arena: position and heading. The brain is the Fly's controller.
- **Odor Source** — a point in the Arena emitting an odor whose concentration falls off with distance, stretched downwind when wind is set.
- **Sugar Patch** — a disk in the Arena; while the Fly is over it, its sugar-sensing Neurons are stimulated.
- **Sense** — the mapping from Arena state to Stimulus rates each Tick, for example odor concentration at each antenna to the olfactory Neurons on that side.
- **Motor Map** — the mapping from Readout rates to the Fly's forward speed and turning rate each Tick.
- **Feed** — an event counted when the Fly is over a Sugar Patch and its proboscis motor Readout fires above a threshold.
- **Soma position** — the annotated cell-body coordinate of a Neuron. Some Neurons have none and are simulated but not drawn.
- **Slice** — a slab of the drawn brain kept visible while everything outside it is clipped away, either along an anatomical axis or along the viewing direction.
