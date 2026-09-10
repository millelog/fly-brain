"""Milestone 1: sugar GRN drive makes MN9 (proboscis extension) fire, reproducing Shiu et al. 2024."""
from flybrain.model import Brain


def test_sugar_drives_mn9():
    b = Brain("cpu")
    base = b.rates(300, {}, ["shiu_mn9"])["shiu_mn9"]
    stim = b.rates(300, {"shiu_sugar": 150.0}, ["shiu_mn9", "motor"])
    assert base == 0.0
    assert stim["shiu_mn9"] > 20.0, stim
    assert stim["motor"] > stim["shiu_mn9"] / 20  # activity spread beyond the single readout
