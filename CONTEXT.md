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
- **Arena** — the walled 100×100×50 mm box the Fly flies in.
- **Fly** — the simulated animal in the Arena: position (x, y, z), heading, horizontal and vertical speed. The brain is the Fly's controller.
- **Landed** — the Fly's state while z = 0. Only a Landed Fly tastes a Sugar Patch; legs walk, wings fold.
- **Body Part** — a part of the Fly bound to the Populations it senses with or is driven by: antennae, eyes, bristles, proboscis, legs, wings, neck.
- **Odor Source** — a point in the Arena emitting an odor whose concentration falls off with distance in 3D, stretched downwind when wind is set.
- **Pillar** — a vertical cylinder the Fly cannot pass through; touching it drives the head bristles on that side.
- **Light Source** — a point whose brightness, by the angle to each eye, drives that eye's photoreceptors.
- **Sugar Patch** — a disk on the Arena floor; while the Fly is Landed on it, its sugar-sensing Neurons are stimulated.
- **Sense** — the mapping from Arena state to Stimulus rates each Tick, for example odor concentration at each antenna to the olfactory Neurons on that side.
- **Motor Map** — the mapping from Readout rates to the Fly's forward speed, turning rate and climb each Tick.
- **Sense Channel / Motor Channel** — one number per Tick named after its Population: the rate written into a sensory Population, or the smoothed rate read from a Readout.
- **Trailer** — the Channels, pose and Feed count appended to each Frame on the wire; its layout is derived from the Channel lists.
- **Channel Strip** — the viewer's scrolling plot of every Channel over the last two seconds of biological time.
- **Chase Cam** — the Arena camera that follows behind the Fly.
- **Feed** — an event counted when the Fly is over a Sugar Patch and its proboscis motor Readout fires above a threshold.
- **Soma position** — the annotated cell-body coordinate of a Neuron. Some Neurons have none and are simulated but not drawn.
- **Slice** — a slab of the drawn brain kept visible while everything outside it is clipped away, either along an anatomical axis or along the viewing direction.
