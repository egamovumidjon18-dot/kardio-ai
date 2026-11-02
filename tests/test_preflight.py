"""Auskultatsiya audio pre-flight sifati testlari."""
import io
import wave
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.store import SqliteEpisodeStore
from screening.pcg import TARGET_SR
from screening.preflight import check_audio_preflight


def _make_wav(signal: np.ndarray, sr: int = TARGET_SR) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        raw_int = (np.clip(signal, -1.0, 1.0) * 32767).astype(np.int16)
        wf.writeframes(raw_int.tobytes())
    return buf.getvalue()


def test_preflight_valid_heart_sound():
    t = np.linspace(0, 6.0, int(6.0 * TARGET_SR), endpoint=False)
    # 50 Hz va 120 Hz yurak tonlari (S1/S2)
    sig = 0.5 * np.sin(2 * np.pi * 50 * t) + 0.3 * np.sin(2 * np.pi * 120 * t)
    wav_bytes = _make_wav(sig)

    rep = check_audio_preflight(wav_bytes)
    assert rep.ok is True
    assert rep.duration_s >= 5.0
    assert rep.snr_db > 0.0
    assert len(rep.reasons) == 0


def test_preflight_too_short():
    t = np.linspace(0, 2.0, int(2.0 * TARGET_SR), endpoint=False)
    sig = 0.4 * np.sin(2 * np.pi * 60 * t)
    wav_bytes = _make_wav(sig)

    rep = check_audio_preflight(wav_bytes)
    assert rep.ok is False
    assert any("qisqa" in r for r in rep.reasons)


def test_preflight_silence():
    sig = np.zeros(int(6.0 * TARGET_SR), dtype=np.float32)
    wav_bytes = _make_wav(sig)

    rep = check_audio_preflight(wav_bytes)
    assert rep.ok is False
    assert any("deyarli yo'q" in r for r in rep.reasons)


def test_preflight_clipping():
    t = np.linspace(0, 6.0, int(6.0 * TARGET_SR), endpoint=False)
    sig = 2.5 * np.sin(2 * np.pi * 50 * t)  # juda baland amplitudada kesiladi
    wav_bytes = _make_wav(sig)

    rep = check_audio_preflight(wav_bytes)
    assert rep.ok is False
    assert any("kesilgan" in r for r in rep.reasons)


def test_preflight_friction_noise():
    t = np.linspace(0, 6.0, int(6.0 * TARGET_SR), endpoint=False)
    # Kiyim ishqalanishi — yuqori chastotali (>800 Hz) shovqin ustun
    sig = 0.05 * np.sin(2 * np.pi * 50 * t) + 0.6 * np.sin(2 * np.pi * 850 * t)
    wav_bytes = _make_wav(sig)

    rep = check_audio_preflight(wav_bytes)
    assert rep.ok is False
    assert any("ishqalanish" in r for r in rep.reasons)


def test_preflight_api_endpoint(tmp_path):
    db_path = str(tmp_path / "preflight_test.db")
    store = SqliteEpisodeStore(db_path)
    client = TestClient(create_app(store, None))

    t = np.linspace(0, 6.0, int(6.0 * TARGET_SR), endpoint=False)
    sig = 0.5 * np.sin(2 * np.pi * 50 * t)
    wav_bytes = _make_wav(sig)

    r = client.post("/screening/preflight", files={"file": ("test.wav", wav_bytes, "audio/wav")})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["duration_s"] >= 5.0
