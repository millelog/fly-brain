# 0003 — 3D flight and body-part bindings

Date: 2026-09-10 · Status: accepted

## Context
The 2D Arena (ADR 0002) could only use smell and three walking-related descending neurons, while the brain holds
photoreceptors, wind-sensing Johnston's organ neurons, head bristles and the wingbeat-amplitude descending neurons
DNg02 (Namiki et al. 2022). None of those had a body to act through, and the sensory afferents were not even drawn:
they have no soma in the annotations, so the brain view showed stimuli arriving from nowhere.

## Decision
- The Arena is a walled 100×100×50 mm box and the Fly flies: pose is (x, y, z, heading), the Motor Map adds
  `vz = g_lift·DNg02 − sink`, and the Fly is Landed when z = 0. Pillars are obstacles, an optional Light Source
  lights the eyes, Odor Sources are 3D Gaussians.
- Body Parts are the unit of binding between Populations and physics: antennae (food ORNs, JO wind neurons,
  antennal motor neurons), eyes (R1-6), head bristles, proboscis (sugar GRNs, MN9), legs (DNp09, MDN), wings
  (DNg02, DNa02), neck (neck motor neurons). Each Sense Channel and Motor Channel is named after its Population,
  so the wire Trailer, the Channel Strip and the fly model's hover/click bindings all derive from two lists in
  `world.py`. Neurons without a soma are drawn at their annotated arbor position.
- Heat in the brain view decays in biological time and is rendered by a point shader (size and color by activity),
  so propagation is watched at the simulation's pace and pausing freezes the picture.

## Consequences
- Lift from DNg02_a/b is the one evidence-based flight channel; the wind, light and bristle formulas are placeholders
  behind sliders, and DNg02_c..h are excluded until screened.
- 7.9k photoreceptors are cheap only while dark: `ambient` defaults to 0, and placing a light raises step cost.
- Recordings saved before this ADR (`pose`/`ema` arrays) no longer replay; the format is now one `trail` row per
  Frame matching the Trailer.
- Steering still does not emerge from raw weights (ADR 0002); this ADR gives the brain more senses and a body, not
  a better Motor Map.
