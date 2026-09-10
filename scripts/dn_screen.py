"""DN screen: drive left vs right food-odor ORNs and rank descending neurons by side asymmetry."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from flybrain.model import Brain

ap = argparse.ArgumentParser()
ap.add_argument("--rate", type=float, default=100.0)
ap.add_argument("--duration", type=float, default=500.0)
ap.add_argument("--device", default="auto")
ap.add_argument("--top", type=int, default=30)
a = ap.parse_args()

b = Brain(a.device)
L = b.totals(a.duration, {"orn_food_l": a.rate}) * 1000 / a.duration
R = b.totals(a.duration, {"orn_food_r": a.rate}) * 1000 / a.duration
dn = b.pop("descending")
asym = (L[dn] - R[dn]) / (L[dn] + R[dn] + 1e-6)
order = dn[np.argsort(-(np.abs(asym) * (L[dn] + R[dn] > 0)))]
print(f"{'idx':>7} {'type':14} {'side':6} {'L Hz':>7} {'R Hz':>7} {'asym':>6}")
for i in order[: a.top]:
    n = b.neurons.iloc[i]
    print(f"{i:7d} {str(n.cell_type):14} {str(n.side):6} {L[i]:7.1f} {R[i]:7.1f} {(L[i] - R[i]) / (L[i] + R[i] + 1e-6):6.2f}")
print(f"\nDNs active under L or R: {int(((L[dn] + R[dn]) > 0).sum())} / {len(dn)}")
for t in ["DNa02", "DNp09", "MDN", "DNa01", "DNg13"]:
    for i in b.neurons.index[b.neurons.cell_type == t]:
        print(f"{t:6} {b.neurons.side[i]:6} L {L[i]:6.1f}  R {R[i]:6.1f}")
