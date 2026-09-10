"""Load the FlyWire v783 connectome (Shiu format) and neuron annotations."""
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow  # noqa: F401  # must import before torch (libarrow conflict)
import torch

DATA = Path(__file__).resolve().parent.parent / "data"
FILES = {
    "connectivity": "2025_Connectivity_783.parquet",
    "completeness": "2025_Completeness_783.csv",
    "annotations": "Supplemental_file1_neuron_annotations.tsv",
}
W_SYN = 0.275  # mV per synapse (Shiu et al.)


def load_neurons() -> pd.DataFrame:
    """Neurons in model index order, joined with annotations. Index = dense model index, `root_id` column."""
    comp = pd.read_csv(DATA / FILES["completeness"], index_col=0)
    ann = pd.read_csv(DATA / FILES["annotations"], sep="\t", low_memory=False).set_index("root_id")
    df = ann.reindex(comp.index)
    df.index.name = "root_id"
    return df.reset_index()


def load_weights(device="cpu", min_synapses=1):
    """CSR by presynaptic neuron: (ptr, post, w) with w in mV. Rows of spiking neurons are gathered event-driven."""
    con = pd.read_parquet(DATA / FILES["connectivity"])
    con = con[con["Connectivity"] >= min_synapses].sort_values("Presynaptic_Index")
    n = pd.read_csv(DATA / FILES["completeness"], index_col=0).shape[0]
    ptr = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(np.bincount(con["Presynaptic_Index"].values, minlength=n), out=ptr[1:])
    post = torch.tensor(con["Postsynaptic_Index"].values, device=device)
    w = torch.tensor(con["Excitatory x Connectivity"].values * W_SYN, dtype=torch.float32, device=device)
    return torch.tensor(ptr, device=device), post, w


VOXEL_UM = np.array([4, 4, 40], dtype=np.float32) / 1000  # annotations are in FlyWire 4x4x40 nm voxels


def soma_xyz(neurons: pd.DataFrame) -> np.ndarray:
    """(N, 3) float32 soma positions in µm; NaN rows for neurons without a soma."""
    return neurons[["soma_x", "soma_y", "soma_z"]].to_numpy(dtype=np.float32) * VOXEL_UM


def reverse_csr(ptr, post, w):
    """CSR by postsynaptic neuron: (ptr_in, pre, w_in), for looking up a neuron's inputs."""
    n = len(ptr) - 1
    order = torch.argsort(post, stable=True)
    pre = torch.repeat_interleave(torch.arange(n, device=ptr.device), ptr[1:] - ptr[:-1])[order]
    ptr_in = torch.zeros(n + 1, dtype=ptr.dtype, device=ptr.device)
    ptr_in[1:] = torch.cumsum(torch.bincount(post, minlength=n), 0)
    return ptr_in, pre, w[order]
