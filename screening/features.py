"""Log-mel spektrogramma — numpy, torch/librosa'siz (CPU inference uchun)."""
from __future__ import annotations

import numpy as np

from screening.pcg import TARGET_SR

N_FFT = 256      # 128 ms @ 2 kHz
HOP = 32         # 16 ms
N_MELS = 64
FMIN, FMAX = 20.0, 800.0


def _hz_to_mel(f):
    return 2595.0 * np.log10(1.0 + np.asarray(f) / 700.0)


def _mel_to_hz(m):
    return 700.0 * (10.0 ** (np.asarray(m) / 2595.0) - 1.0)


def mel_filterbank(sr: int = TARGET_SR, n_fft: int = N_FFT, n_mels: int = N_MELS,
                   fmin: float = FMIN, fmax: float = FMAX) -> np.ndarray:
    bins = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    pts = _mel_to_hz(np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2))
    fb = np.zeros((n_mels, bins.size), dtype=np.float32)
    for i in range(n_mels):
        lo, mid, hi = pts[i], pts[i + 1], pts[i + 2]
        up = (bins - lo) / (mid - lo)
        down = (hi - bins) / (hi - mid)
        fb[i] = np.maximum(0.0, np.minimum(up, down))
    return fb


_FB = mel_filterbank()
_WINDOW = np.hanning(N_FFT).astype(np.float32)


def log_mel(windows: np.ndarray) -> np.ndarray:
    """[N, samples] → [N, 1, N_MELS, T], har oyna alohida standartlashtiriladi."""
    n, length = windows.shape
    t = 1 + (length - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(t)[:, None]
    frames = windows[:, idx] * _WINDOW                     # [N, T, N_FFT]
    power = np.abs(np.fft.rfft(frames, axis=-1)) ** 2      # [N, T, F]
    mel = np.log(power @ _FB.T + 1e-6)                     # [N, T, M]
    mel = mel.transpose(0, 2, 1)                           # [N, M, T]
    mu = mel.mean(axis=(1, 2), keepdims=True)
    sd = mel.std(axis=(1, 2), keepdims=True) + 1e-6
    return ((mel - mu) / sd)[:, None].astype(np.float32)
