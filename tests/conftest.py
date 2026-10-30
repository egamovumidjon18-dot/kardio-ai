import io
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def make_wav(seconds: float = 10.0, sr: int = 4000, murmur: bool = False, amp: float = 0.3,
             seed: int = 0, clip: bool = False) -> bytes:
    """Sun'iy PCG: ~75 bpm S1/S2 impulslari (+ ixtiyoriy sistolik 'shovqin')."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    x = 0.01 * rng.standard_normal(t.size)
    for beat in np.arange(0, seconds, 0.8):
        for onset, f in ((beat, 50.0), (beat + 0.3, 70.0)):
            m = (t >= onset) & (t < onset + 0.08)
            x[m] += np.sin(2 * np.pi * f * (t[m] - onset)) * np.hanning(m.sum())
        if murmur:
            m = (t >= beat + 0.1) & (t < beat + 0.28)
            x[m] += 0.4 * rng.standard_normal(m.sum())
    x = x / np.abs(x).max() * (1.5 if clip else amp)
    pcm = (np.clip(x, -1, 0.99997) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


@pytest.fixture
def wav_factory():
    return make_wav
