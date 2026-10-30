"""EKG signalini tayyorlash va sifatini baholash — faqat numpy + stdlib.

O'qitish (research/train_ecg.py) va inference AYNAN shu funksiyalardan
foydalanadi (train/serve farqi bo'lmasligi uchun). Birlik: millivolt (mV).
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

LEADS_12 = ("I", "II", "III", "AVR", "AVL", "AVF", "V1", "V2", "V3", "V4", "V5", "V6")
TARGET_FS = 100           # Hz — PTB-XL records100 bilan bir xil
DURATION_S = 10.0         # model oynasi (PTB-XL yozuvi uzunligi)
N_SAMPLES = int(TARGET_FS * DURATION_S)
BAND = (0.5, 40.0)        # Hz — bazal chiziq siljishi va tarmoq shovqinini olib tashlaydi
MIN_DURATION_S = 8.0


def norm_lead(name: str) -> str:
    """'aVR' / 'avr' / 'Lead II' / 'MLII' → 'AVR' / 'II'."""
    n = re.sub(r"^(LEAD|ML)", "", name.strip().upper().replace(" ", ""))
    return n


def resample(x: np.ndarray, fs: float, target: int = TARGET_FS) -> np.ndarray:
    """[L, N] → [L, N'] FFT orqali qayta diskretlash."""
    if fs == target or x.shape[-1] == 0:
        return x.astype(np.float32)
    n_out = int(round(x.shape[-1] * target / fs))
    spec = np.fft.rfft(x, axis=-1)
    keep = n_out // 2 + 1
    if spec.shape[-1] >= keep:
        spec = spec[..., :keep]
    else:
        spec = np.pad(spec, [(0, 0)] * (spec.ndim - 1) + [(0, keep - spec.shape[-1])])
    return (np.fft.irfft(spec, n=n_out, axis=-1) * (n_out / x.shape[-1])).astype(np.float32)


def bandpass(x: np.ndarray, fs: float = TARGET_FS, band: tuple[float, float] = BAND) -> np.ndarray:
    """Nol-fazali FFT band-pass (oflayn tahlil uchun yetarli)."""
    if x.shape[-1] == 0:
        return x
    spec = np.fft.rfft(x, axis=-1)
    freqs = np.fft.rfftfreq(x.shape[-1], d=1.0 / fs)
    spec[..., (freqs < band[0]) | (freqs > band[1])] = 0
    return np.fft.irfft(spec, n=x.shape[-1], axis=-1).astype(np.float32)


def fit_length(x: np.ndarray, n: int = N_SAMPLES) -> np.ndarray:
    """Markaziy kesish yoki nol bilan to'ldirish → aniq n namuna."""
    cur = x.shape[-1]
    if cur >= n:
        s = (cur - n) // 2
        return x[..., s:s + n]
    pad = n - cur
    return np.pad(x, [(0, 0)] * (x.ndim - 1) + [(pad // 2, pad - pad // 2)])


def preprocess(x: np.ndarray, fs: float) -> np.ndarray:
    """[L, N] mV → [L, 1000] tarmoq bo'yicha standartlashtirilgan float32."""
    y = fit_length(bandpass(resample(np.nan_to_num(x.astype(np.float32)), fs)))
    mu = y.mean(axis=-1, keepdims=True)
    sd = y.std(axis=-1, keepdims=True)
    return ((y - mu) / np.maximum(sd, 1e-3)).astype(np.float32)


@dataclass
class Quality:
    ok: bool
    duration_s: float
    reasons: list[str] = field(default_factory=list)
    bad_leads: list[str] = field(default_factory=list)


def assess_quality(x: np.ndarray, fs: float, leads: tuple[str, ...]) -> Quality:
    """Abstain-first: sifatsiz EKGga model umuman qo'llanmaydi.

    Tarmoq "yaroqsiz": NaN, tekis chiziq (elektrod tushgan), >8 mV amplituda
    (saturatsiya/artefakt) yoki yuqori chastotali shovqin ulushi katta.
    12 tarmoqdan 2 tadan ko'pi yaroqsiz bo'lsa yoki bitta tarmoqli rejimda tarmoq
    yaroqsiz bo'lsa — butun yozuv rad etiladi.
    """
    dur = x.shape[-1] / fs if fs else 0.0
    reasons: list[str] = []
    if dur < MIN_DURATION_S:
        reasons.append(f"yozuv juda qisqa ({dur:.1f} s < {MIN_DURATION_S:.0f} s)")
        return Quality(False, dur, reasons)
    bad = []
    for i, name in enumerate(leads):
        lead = x[i]
        if np.isnan(lead).mean() > 0.05:
            bad.append(f"{name}: ma'lumot yo'q"); continue
        lead = np.nan_to_num(lead)
        y = bandpass(lead[None], fs)[0]
        p2p = float(np.percentile(y, 99.5) - np.percentile(y, 0.5))
        if p2p < 0.05:
            bad.append(f"{name}: tekis chiziq (elektrod?)"); continue
        if float(np.abs(lead - np.median(lead)).max()) > 8.0:
            bad.append(f"{name}: amplituda >8 mV (artefakt)"); continue
        if fs >= 100:
            hf = bandpass(lead[None], fs, (40.0, fs / 2))[0]
            if float(hf.std()) > 0.5 * max(float(y.std()), 1e-6):
                bad.append(f"{name}: yuqori chastotali shovqin"); continue
    max_bad = 2 if len(leads) == 12 else 0
    if len(bad) > max_bad:
        reasons.append(f"{len(bad)} ta tarmoq yaroqsiz: " + "; ".join(bad))
    return Quality(not reasons, dur, reasons, bad)


# ---------------------------------------------------------------- o'qish
def read_csv(src: bytes | str | Path, fs: float) -> tuple[np.ndarray, tuple[str, ...]]:
    """CSV: birinchi qator tarmoq nomlari (I,II,...,V6), keyingilari mV qiymatlar.
    'time'/'t' ustuni bo'lsa tashlanadi."""
    text = src.decode("utf-8-sig") if isinstance(src, bytes) else Path(src).read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        raise ValueError("CSV bo'sh")
    header = [norm_lead(h) for h in rows[0]]
    keep = [i for i, h in enumerate(header) if h not in ("TIME", "T", "SAMPLE", "")]
    try:
        data = np.array([[float(r[i]) if r[i].strip() else np.nan for i in keep] for r in rows[1:] if r],
                        dtype=np.float32)
    except (ValueError, IndexError) as exc:
        raise ValueError(f"CSV qiymatlari son emas: {exc}") from None
    return data.T, tuple(header[i] for i in keep)


def read_wfdb(record: str | Path) -> tuple[np.ndarray, float, tuple[str, ...]]:
    """PhysioNet WFDB (format 16) → ([L, N] mV, fs, tarmoqlar). PTB-XL uchun yetarli."""
    record = Path(record)
    lines = [ln for ln in record.with_suffix(".hea").read_text().splitlines() if ln and not ln.startswith("#")]
    head = lines[0].split()
    n_sig, fs, n = int(head[1]), float(head[2].split("/")[0]), int(head[3])
    gains, bases, names = [], [], []
    for ln in lines[1:1 + n_sig]:
        p = ln.split()
        if p[1] != "16":
            raise ValueError(f"WFDB format {p[1]} qo'llab-quvvatlanmaydi (faqat 16)")
        g = p[2].split("/")[0]
        gain = float(g.split("(")[0]) if g else 200.0
        base = int(g.split("(")[1].rstrip(")")) if "(" in g else int(p[4])
        gains.append(gain or 200.0); bases.append(base); names.append(norm_lead(p[-1]))
    raw = np.fromfile(record.with_suffix(".dat"), dtype="<i2")[:n * n_sig].reshape(n, n_sig).T
    x = (raw.astype(np.float32) - np.array(bases)[:, None]) / np.array(gains)[:, None]
    return x.astype(np.float32), fs, tuple(names)


def select_leads(x: np.ndarray, names: tuple[str, ...], want: tuple[str, ...]) -> np.ndarray:
    """Kerakli tarmoqlarni kerakli tartibda; yo'q bo'lsa ValueError."""
    idx = {n: i for i, n in enumerate(names)}
    missing = [w for w in want if w not in idx]
    if missing:
        raise ValueError(f"tarmoq(lar) yo'q: {', '.join(missing)} (kerak: {', '.join(want)})")
    return x[[idx[w] for w in want]]
