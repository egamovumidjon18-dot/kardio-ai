"""Mahalliy ma'lumot yig'ish: rozilik bilan PCG yozuvlarini saqlash + ExoKG tashxisi.

Maqsad — model yangi klinika/stetoskopga moslashishi uchun 50–100+ tasdiqlangan
yozuv yig'ish (docs/experiments/zchsound_adaptation.md). Faqat psevdonim saqlanadi.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

ECHO_DIAGNOSES = ("NORMAL", "ASD", "VSD", "PDA", "PFO", "AVSD", "TOF", "COA", "PS", "AS", "OTHER")

_PROV = Provenance(name="local_collection", reference="ota-ona/vasiy yozma roziligi bilan")


def save_recordings(root: Path, episode_id: str, recs: list[tuple[str, bytes]], age_days: Optional[float],
                    device: str) -> Evidence:
    """WAV fayllarni <root>/<episode_id>/<nuqta>[_n].wav ga yozadi (mavjudlarini o'chirmaydi)."""
    folder = root / episode_id
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for loc, data in recs:
        path, n = folder / f"{loc}.wav", 1
        while path.exists():
            n += 1
            path = folder / f"{loc}_{n}.wav"
        path.write_bytes(data)
        files.append({"location": loc, "file": path.name})
    return Evidence(kind="research.recordings", value={"files": files, "age_days": age_days, "device": device,
                                                       "consent": True},
                    source=Source.CLINICIAN, provenance=_PROV,
                    explanation=[f"{len(files)} ta yozuv tadqiqot uchun saqlandi (rozilik bor)"])


def echo_diagnosis(dx: str, notes: str = "") -> Evidence:
    dx = dx.strip().upper()
    if dx not in ECHO_DIAGNOSES:
        raise ValueError(f"noma'lum tashxis: {dx} (ruxsat etilgan: {', '.join(ECHO_DIAGNOSES)})")
    return Evidence(kind="workup.echo_dx", value=dx, source=Source.CLINICIAN,
                    provenance=Provenance(name="echo_confirmed", reference="ExoKG (oltin standart)"),
                    risk=RiskLevel.NORMAL if dx == "NORMAL" else RiskLevel.UNKNOWN,
                    explanation=[f"ExoKG tashxisi: {dx}"] + ([notes] if notes else []))
