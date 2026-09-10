"""Chemotaxis benchmark: K episodes from random poses, odor on vs off; index = (d_start - d_end) / d_start."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import math

import numpy as np

from flybrain.model import Brain
from flybrain.world import SIZE, World

ap = argparse.ArgumentParser()
ap.add_argument("--episodes", type=int, default=10)
ap.add_argument("--duration", type=float, default=5000.0, help="bio ms per episode")
ap.add_argument("--radius", type=float, default=10.0, help="mm, 'near source' radius")
ap.add_argument("--device", default="auto")
ap.add_argument("--record", help="directory to save one npz per episode")
a = ap.parse_args()

b = Brain(a.device)
w = World(b)
src = dict(x=SIZE * 0.75, y=SIZE / 2)
rng = np.random.default_rng(1)
ticks = round(a.duration / w.window)


def episode(k, odor):
    w.cmds.put(dict(cmd="reset", seed=k))
    w.cmds.put(dict(cmd="delete", kind="source", id="s"))
    if odor:
        w.cmds.put(dict(cmd="source", id="s", **src))
    x, y = rng.uniform(10, SIZE * 0.5), rng.uniform(10, SIZE - 10)
    w.cmds.put(dict(cmd="fly", x=x, y=y, theta=rng.uniform(-math.pi, math.pi)))
    if a.record:
        w.cmds.put(dict(cmd="record", on=True))
    near = 0
    d0 = math.hypot(x - src["x"], y - src["y"])
    for _ in range(ticks):
        w.tick()
        near += math.hypot(w.pose[0] - src["x"], w.pose[1] - src["y"]) < a.radius
    d1 = math.hypot(w.pose[0] - src["x"], w.pose[1] - src["y"])
    if a.record:
        w.save(f"{a.record}/ep{k}_{'odor' if odor else 'ctrl'}.npz")
    return (d0 - d1) / d0, near / ticks, w.feeds


for odor in (True, False):
    r = np.array([episode(k, odor) for k in range(a.episodes)])
    print(f"odor {'on ':3} " if odor else "odor off ", end="")
    print(f"index {r[:, 0].mean():+.2f} ± {r[:, 0].std():.2f}   near {r[:, 1].mean():.2f}   feeds/ep {r[:, 2].mean():.1f}   (n={a.episodes}, {a.duration / 1000:.0f} s)")
