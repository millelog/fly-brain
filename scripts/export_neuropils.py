"""One-time export of FlyWire neuropil hull meshes to flybrain/static/neuropils.glb (µm, FlyWire space).

Run: uv run --with fafbseg --with trimesh --with navis python scripts/export_neuropils.py
"""
from pathlib import Path

import numpy as np
import trimesh
from fafbseg import flywire

out = Path(__file__).resolve().parent.parent / "flybrain" / "static" / "neuropils.glb"
scene = trimesh.Scene()
names = [n for n in flywire.get_neuropil_volumes(None) if n not in ('BRAIN',)]  # no-arg call lists names
for vol in flywire.get_neuropil_volumes(names):  # coordinates in nm
    m = trimesh.Trimesh(np.asarray(vol.vertices) / 1000.0, np.asarray(vol.faces))
    if len(m.faces) > 1500:
        m = m.simplify_quadric_decimation(face_count=1500)
    scene.add_geometry(m, node_name=vol.name, geom_name=vol.name)
scene.export(out)
print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(scene.geometry)} neuropils)")
