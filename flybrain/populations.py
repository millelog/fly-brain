"""Population registry: name -> pandas query on the annotations frame, or explicit root ids."""
import numpy as np
import pandas as pd

# Shiu et al. 2024 example: 21 right-hemisphere sugar GRNs (one id absent in v783) and MN9.
SHIU_SUGAR = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345, 720575940617000768,
    720575940630797113, 720575940632889389, 720575940621754367, 720575940621502051, 720575940640649691,
    720575940639332736, 720575940616885538, 720575940639198653, 720575940620900446, 720575940617937543,
    720575940632425919, 720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
SHIU_MN9 = [720575940660219265]

REGISTRY: dict[str, str | list[int]] = {
    "shiu_sugar": SHIU_SUGAR,
    "shiu_mn9": SHIU_MN9,
    "sugar_grn": "cell_sub_class == 'sugar/water'",
    "bitter_grn": "cell_sub_class == 'bitter'",
    "proboscis_mn": "cell_sub_class == 'proboscis_motor_neuron'",
    "ingestion_mn": "cell_sub_class == 'ingestion_motor_neuron'",
    "motor": "super_class == 'motor'",
    "descending": "super_class == 'descending'",
    "dna02": "cell_type == 'DNa02'",
    "dnp09": "cell_type == 'DNp09'",
    "mdn": "cell_type == 'MDN'",
    "dna02_l": "cell_type == 'DNa02' and side == 'left'",
    "dna02_r": "cell_type == 'DNa02' and side == 'right'",
    "orn_food_l": "cell_type in ['ORN_DM1', 'ORN_DM2', 'ORN_DM4', 'ORN_VA2'] and side == 'left'",
    "orn_food_r": "cell_type in ['ORN_DM1', 'ORN_DM2', 'ORN_DM4', 'ORN_VA2'] and side == 'right'",
    "orn": "cell_class == 'olfactory'",
}


def resolve(name: str, neurons: pd.DataFrame) -> np.ndarray:
    """Dense model indices for a registered Population name."""
    spec = REGISTRY[name]
    if isinstance(spec, str):
        return neurons.query(spec).index.to_numpy()
    return neurons.index[neurons["root_id"].isin(spec)].to_numpy()
