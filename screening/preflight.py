"""Fonokardiogramma (PCG) audio sifatini pre-flight tekshirish moduli.

Stetoskop yozuvini AI modeliga yuborishdan oldin uning fizik va akustik sifatini
(shovqin, kiyimga ishqalanish, kesilish, davomiylik) real vaqt rejimida tekshiradi.
"""
from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from screening.pcg import BAND, MIN_DURATION_S, TARGET_SR, load_wav, resample


@dataclass
class PreflightReport:
    ok: bool
    duration_s: float
    snr_db: float
    heart_band_ratio: float
    clip_frac: float
    reasons: list[str] = field(default_factory=list)
    advice: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def check_audio_preflight(audio_bytes_or_path: bytes | str | Path) -> PreflightReport:
    """WAV audio sifatini tekshiradi va shifokorga tavsiya qaytaradi."""
    try:
        raw, sr, clip_frac = load_wav(audio_bytes_or_path)
    except Exception as exc:
        return PreflightReport(
            ok=False,
            duration_s=0.0,
            snr_db=0.0,
            heart_band_ratio=0.0,
            clip_frac=0.0,
            reasons=[f"WAV faylni o'qib bo'lmadi: {exc}"],
            advice="Faqat standart PCM WAV formatidagi audio fayllarni yuklang.",
        )

    dur = raw.size / sr if sr else 0.0
    reasons: list[str] = []

    # 1. Davomiylik tekshiruvi
    if dur < MIN_DURATION_S:
        reasons.append(f"Yozuv juda qisqa ({dur:.1f} s < {MIN_DURATION_S:.0f} s)")

    # 2. Kesilish (clipping) tekshiruvi
    if clip_frac > 0.02:
        reasons.append(f"Signal kesilgan (clipping {clip_frac:.1%}) — mikrofon kuchaytirilishi haddan tashqari baland")

    # 3. Yassi signal (jimlik)
    rms = float(np.sqrt(np.mean(raw**2))) if raw.size else 0.0
    if rms < 1e-4:
        reasons.append("Signal deyarli yo'q (stetoskop teriga tegmagan yoki o'chirilgan)")
        return PreflightReport(
            ok=False,
            duration_s=round(dur, 2),
            snr_db=-99.0,
            heart_band_ratio=0.0,
            clip_frac=round(clip_frac, 4),
            reasons=reasons,
            advice="Stetoskop boshchasini ko'krak qafasiga to'g'ri joylashtirib, ovoz yozishni qayta boshlang.",
        )

    # 4. Spektral energiya tahlili (FFT)
    # Signalni 2000 Hz ga keltiramiz
    y = resample(raw, sr, TARGET_SR)
    spec = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(y.size, d=1.0 / TARGET_SR)

    # Yurak tovushlari diapazoni (25 - 400 Hz)
    heart_mask = (freqs >= BAND[0]) & (freqs <= BAND[1])
    # Ishqalanish/yuqori chastotali tashqi shovqin (> 600 Hz)
    friction_mask = freqs >= 600.0

    heart_energy = float(np.sum(spec[heart_mask] ** 2))
    friction_energy = float(np.sum(spec[friction_mask] ** 2))
    total_energy = float(np.sum(spec**2)) + 1e-12

    heart_ratio = heart_energy / total_energy
    friction_ratio = friction_energy / total_energy

    # SNR hisoblash (yurak signali va shovqin nisbati)
    noise_energy = total_energy - heart_energy
    snr_db = round(10.0 * np.log10(max(heart_energy / max(noise_energy, 1e-12), 1e-4)), 1)

    # Kiyimga ishqalanish
    if friction_ratio > 0.40 and heart_ratio < 0.35:
        reasons.append(f"Kiyimga ishqalanish yoki yuqori shovqin aniqlandi (>600 Hz energiya: {friction_ratio:.1%})")

    # Tavsiya shakllantirish
    advice = "Ovoz sifati a'lo darajada."
    if reasons:
        advices = []
        if any("qisqa" in r for r in reasons):
            advices.append("Kamida 5 soniya davomida uzluksiz yozing.")
        if any("kesilgan" in r for r in reasons):
            advices.append("Stetoskop mikrofonining sezgirligini biroz pasaytiring.")
        if any("ishqalanish" in r for r in reasons):
            advices.append("Stetoskopni kiyim ustidan emas, bevosita quruq teriga mahkam bosing va harakatlanmang.")
        advice = " ".join(advices)

    ok = len(reasons) == 0
    return PreflightReport(
        ok=ok,
        duration_s=round(dur, 2),
        snr_db=snr_db,
        heart_band_ratio=round(heart_ratio, 3),
        clip_frac=round(clip_frac, 4),
        reasons=reasons,
        advice=advice,
    )
