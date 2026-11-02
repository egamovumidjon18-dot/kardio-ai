"""Mahalliy tasdiqlangan holatlardan o'rganish ma'lumotini tayyorlash.

Belgi: ExoKG tashxisi (oltin standart). Musbat — nuqson (ASD, VSD, PDA, AVSD, TOF, COA, PS, AS); manfiy — NORMAL.
PFO va OTHER noaniq (odatda shovqinsiz yoki turli) — o'qitishga ham, baholashga ham kirmaydi. 29 kundan kichik
bolalar chiqariladi (platforma ularda yurak tovushi AI'ni ishlatmaydi).

Bo'linish barqaror bemor kodining xeshi bo'yicha: bola bir marta test/val/o'qitishga tushsa, keyingi sikllarda
ham o'sha yerda qoladi. Shunda test to'plami o'qitishga sizib kirmaydi va sikllar orasida solishtirsa bo'ladi.
"""
from __future__ import annotations

import hashlib
import math
from typing import Optional

CHD_POSITIVE = {"ASD", "VSD", "PDA", "AVSD", "TOF", "COA", "PS", "AS"}
MIN_AGE_DAYS = 29
TEST_FRAC, VAL_FRAC = 0.25, 0.15
SPLIT_SCHEME = "patient-ref-v1"


def label_of(dx: str) -> Optional[int]:
    if dx in CHD_POSITIVE:
        return 1
    return 0 if dx == "NORMAL" else None


def usable(children: list[dict]) -> list[dict]:
    return [c for c in children if label_of(c["dx"]) is not None and c.get("patient_key")
            and c.get("age_days") is not None and math.isfinite(c["age_days"])
            and MIN_AGE_DAYS <= c["age_days"] <= 365 * 21]


def bucket(eid: str) -> str:
    """Barqaror bemor kaliti bo'yicha: 'test' (25%), 'val' (15%), qolgani 'train'."""
    x = int(hashlib.sha256(eid.encode()).hexdigest()[:8], 16) / 2 ** 32
    if x < TEST_FRAC:
        return "test"
    return "val" if x < TEST_FRAC + VAL_FRAC else "train"


def split_children(children: list[dict]) -> dict[str, list[dict]]:
    out = {"train": [], "val": [], "test": []}
    for c in usable(children):
        out[bucket(c["patient_key"])].append(c)
    return out


def to_patients(children: list[dict]) -> list[dict]:
    """research.train_pcg / evaluate_pcg tushunadigan bemor lug'atlari (yozuvlar yo'li bilan)."""
    return [{"id": c["eid"], "murmur": "Present" if label_of(c["dx"]) else "Absent", "outcome": 0,
             "additional_id": None, "age_days": c.get("age_days"),
             "recordings": [{"path": f["path"], "location": f["location"],
                             "murmur": label_of(c["dx"])} for f in c["files"]]} for c in children]
