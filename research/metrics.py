"""Torch'siz metrikalar: server yo'li (learning → research.export_local) ham ishlatadi, shuning uchun torch import qilinmaydi."""
from __future__ import annotations

import numpy as np


def auroc(y: np.ndarray, s: np.ndarray) -> float:
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    ranks[order] = np.arange(1, len(order) + 1)
    # teng qiymatlar uchun o'rtacha rang
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        idx = allv == v
        ranks[idx] = ranks[idx].mean()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))
