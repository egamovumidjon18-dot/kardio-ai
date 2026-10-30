"""Fonokardiogramma (PCG) signalini tayyorlash — faqat numpy + stdlib.

O'qitish (research/train_pcg.py) va inference AYNAN shu funksiyalardan
foydalanadi, aks holda train/serve farqi paydo bo'ladi.
"""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

TARGET_SR = 2000          # Hz — yurak tovushlari < 800 Hz
BAND = (25.0, 400.0)      # Hz — S1/S2 va shovqinlarning asosiy diapazoni
WIN_S = 4.0               # model oynasi (s) — ~3–5 yurak sikli
HOP_S = 2.0
MIN_DURATION_S = 5.0


def load_wav(src: str | Path | bytes) -> tuple[np.ndarray, int, float]:
    """WAV → (signal [-1,1] float32, sample rate, kesilgan (clipping) ulush)."""
    try:
        with wave.open(io.BytesIO(src) if isinstance(src, bytes) else str(src), "rb") as fh:
            sr, n, ch, width = fh.getframerate(), fh.getnframes(), fh.getnchannels(), fh.getsampwidth()
            raw = fh.readframes(n)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"WAV (PCM) fayl emas yoki buzilgan: {exc}") from None
    if width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"qo'llab-quvvatlanmaydigan WAV namuna kengligi: {width} bayt")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    clip_frac = float(np.mean(np.abs(x) >= 0.999)) if x.size else 0.0
    return x, sr, clip_frac


def resample(x: np.ndarray, sr: int, target: int = TARGET_SR) -> np.ndarray:
    """FFT orqali qayta diskretlash (ideal past chastota filtri bilan)."""
    if sr == target or x.size == 0:
        return x.astype(np.float32)
    n_out = int(round(x.size * target / sr))
    spec = np.fft.rfft(x)
    keep = n_out // 2 + 1
    spec = spec[:keep] if spec.size >= keep else np.pad(spec, (0, keep - spec.size))
    return (np.fft.irfft(spec, n=n_out) * (n_out / x.size)).astype(np.float32)


def bandpass(x: np.ndarray, sr: int = TARGET_SR, band: tuple[float, float] = BAND) -> np.ndarray:
    """Nol-fazali FFT band-pass (oflayn tahlil uchun yetarli)."""
    if x.size == 0:
        return x
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, d=1.0 / sr)
    spec[(freqs < band[0]) | (freqs > band[1])] = 0
    return np.fft.irfft(spec, n=x.size).astype(np.float32)


def preprocess(x: np.ndarray, sr: int) -> np.ndarray:
    y = bandpass(resample(x, sr))
    std = float(y.std())
    return (y - y.mean()) / std if std > 1e-8 else y


@dataclass
class Quality:
    ok: bool
    duration_s: float
    reasons: list[str] = field(default_factory=list)


def assess_quality(raw: np.ndarray, sr: int, clip_frac: float) -> Quality:
    """Abstain-first: sifatsiz yozuvga model umuman qo'llanmaydi."""
    dur = raw.size / sr if sr else 0.0
    reasons = []
    if dur < MIN_DURATION_S:
        reasons.append(f"yozuv juda qisqa ({dur:.1f} s < {MIN_DURATION_S:.0f} s)")
    if clip_frac > 0.01:
        reasons.append(f"signal kesilgan (clipping {clip_frac:.1%}) — mikrofon kuchaytirgichi baland")
    if raw.size and float(np.std(raw)) < 1e-4:
        reasons.append("signal deyarli yo'q (stetoskop teriga tegmagan?)")
    return Quality(ok=not reasons, duration_s=dur, reasons=reasons)


def windows(y: np.ndarray, sr: int = TARGET_SR, win_s: float = WIN_S, hop_s: float = HOP_S) -> np.ndarray:
    """[n_windows, win] — oxirgi to'liq bo'lmagan oyna tashlanadi."""
    win, hop = int(win_s * sr), int(hop_s * sr)
    if y.size < win:
        return np.zeros((0, win), dtype=np.float32)
    starts = range(0, y.size - win + 1, hop)
    return np.stack([y[s:s + win] for s in starts]).astype(np.float32)
