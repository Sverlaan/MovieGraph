from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class NodeDataset:
    label: str
    keys: List[str]
    dataframe: pd.DataFrame


@dataclass
class EdgeDataset:
    type: str
    source_label: str
    target_label: str
    source_key: str
    target_key: str
    dataframe: pd.DataFrame
    merge_key: Optional[str] = field(default=None)
