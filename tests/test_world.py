"""Milestone 2: the closed loop ticks, senses on the correct side, stays in the arena, and packs the wire format."""
import struct

import numpy as np
import torch

from flybrain.model import Brain
from flybrain.world import SIZE, TRAILER, World


def test_world_ticks():
    b = Brain("cpu")
    w = World(b)
    w.cmds.put(dict(cmd="source", id="s", x=90, y=50))
    w.cmds.put(dict(cmd="fly", x=80, y=50, theta=1.0))  # heading up-right: left antenna is farther from the source
    for _ in range(5):
        buf = w.tick()
    n = struct.unpack_from("<fI", buf)[1]
    assert len(buf) == 8 + 6 * n + struct.calcsize(TRAILER)
    rl, rr = w.rate[w.idx["orn_food_l"]].mean(), w.rate[w.idx["orn_food_r"]].mean()
    assert rr > rl > w.gains["r0"]
    assert 0 <= w.pose[0] <= SIZE and 0 <= w.pose[1] <= SIZE
    w.cmds.put(dict(cmd="pause", on=True))
    assert w.tick() is None


def test_tensor_stimuli_match_dict():
    b = Brain("cpu")
    a = [f[1].tolist() for f in b.frames(50, {"shiu_sugar": 150.0})]
    t = [f[1].tolist() for f in b.frames(50, b.rate_tensor({"shiu_sugar": 150.0}))]
    assert a == t and any(a)
