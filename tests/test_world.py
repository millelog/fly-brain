"""Milestone 3: the closed loop ticks in a 3D box, senses on the correct side, collides, lands, feeds, packs the wire."""
import struct

import pytest

from flybrain.model import Brain
from flybrain.world import H, MOTOR, POSE, SENSE, SIZE, TRAILER, World


@pytest.fixture(scope="module")
def brain():
    return Brain("cpu")


def world(brain, *cmds, **gains):
    w = World(brain)
    w.cmds.put(dict(cmd="gains", noise=0.0, **gains))
    for c in cmds:
        w.cmds.put(c)
    return w


def test_trailer_matches_channels(brain):
    w = world(brain)
    for _ in range(3):
        buf = w.tick()
    n = struct.unpack_from("<fI", buf)[1]
    assert struct.calcsize(TRAILER) == 4 * (len(POSE) + len(SENSE) + len(MOTOR)) + 4
    assert len(buf) == 8 + 6 * n + struct.calcsize(TRAILER)
    *trail, feeds = struct.unpack_from(TRAILER, buf, 8 + 6 * n)
    assert feeds == 0 and 0 <= trail[2] <= H
    w.cmds.put(dict(cmd="pause", on=True))
    assert w.tick() is None


def test_box_bounds_and_ceiling_touch(brain):
    w = world(brain, dict(cmd="fly", x=99, y=99, z=49, theta=0.78), v_base=60.0, sink=-100.0)
    for _ in range(20):
        w.tick()
        assert 0 <= w.pose[0] <= SIZE and 0 <= w.pose[1] <= SIZE and 0 <= w.pose[2] <= H
    assert w.pose[2] == H and w.sense["bristle_l"] > 0 and w.sense["bristle_r"] > 0


def test_senses_are_side_correct(brain):
    w = world(brain, dict(cmd="source", id="s", x=90, y=50, z=25), dict(cmd="fly", x=80, y=50, z=25, theta=1.0))
    for _ in range(3):
        w.tick()
    S = w.sense
    assert S["orn_food_r"] > S["orn_food_l"] > w.gains["r0"]
    assert (w.rate[w.idx["orn_food_r"]] == S["orn_food_r"]).all()
    w = world(brain, dict(cmd="wind", dir=0.0), dict(cmd="fly", x=50, y=50, z=25, theta=1.5708), v_base=0.0)
    w.tick()
    assert w.sense["jo_wind_l"] > w.sense["jo_wind_r"] == pytest.approx(0.0, abs=1e-6)  # wind blows +x, fly faces +y: left side upwind
    w = world(brain, dict(cmd="light", id="light", x=100, y=50, z=25), dict(cmd="fly", x=50, y=50, z=25, theta=1.5708), v_base=0.0)
    w.tick()
    assert w.sense["r16_r"] > w.sense["r16_l"] == w.gains["ambient"] == 0.0
    w.cmds.put(dict(cmd="delete", kind="light", id="light"))
    w.tick()
    assert w.sense["r16_r"] == w.sense["r16_l"] == w.gains["ambient"]


def test_landing_and_feeding(brain):
    w = world(brain, dict(cmd="patch", id="p", x=50, y=50), dict(cmd="fly", x=50, y=50, z=0), v_base=0.0)
    w.tick()
    assert w.sense["sugar_grn"] == 150.0 and w.feeds == 0
    w.ema["shiu_mn9"] = 1e3
    w.tick()
    assert w.feeds == 1
    w.tick()
    assert w.feeds == 1  # rising edge only
    w.cmds.put(dict(cmd="fly", z=10))
    w.ema["shiu_mn9"] = 1e3
    w.tick()
    assert w.sense["sugar_grn"] == 0.0 and w.feeds == 1


def test_pillar_pushout(brain):
    w = world(brain, dict(cmd="pillar", id="c", x=60, y=50), dict(cmd="fly", x=52, y=50, z=25, theta=0.0), v_base=30.0)
    touched = False
    for _ in range(30):
        w.tick()
        assert ((w.pose[0] - 60) ** 2 + (w.pose[1] - 50) ** 2) ** 0.5 >= 5 + w.gains["body"] - 1e-6
        touched |= w.sense["bristle_l"] > 0 or w.sense["bristle_r"] > 0
    assert touched


def test_tensor_stimuli_match_dict(brain):
    a = [f[1].tolist() for f in brain.frames(50, {"shiu_sugar": 150.0})]
    t = [f[1].tolist() for f in brain.frames(50, brain.rate_tensor({"shiu_sugar": 150.0}))]
    assert a == t and any(a)
