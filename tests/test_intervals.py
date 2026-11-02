"""Test ecg/intervals.py — PR, QRS, QT, QTc and heart rate measurements."""
import numpy as np
import pytest

from core.evidence import RiskLevel
from ecg.intervals import detect_r_peaks, measure_intervals


def generate_synthetic_ecg(hr_bpm=75, duration_s=10.0, fs=100.0, pr_ms=160, qrs_ms=90, qt_ms=380, seed=42):
    rng = np.random.default_rng(seed)
    N = int(fs * duration_s)
    t = np.arange(N) / fs
    ecg = 0.01 * rng.standard_normal(N)
    rr_s = 60.0 / hr_bpm
    beats = np.arange(0.4, duration_s - 0.3, rr_s)

    for b in beats:
        # P wave
        p_t = b - (pr_ms / 1000.0)
        ecg += 0.15 * np.exp(-((t - p_t) / 0.04) ** 2)
        # Q wave
        ecg -= 0.15 * np.exp(-((t - (b - 0.025)) / 0.015) ** 2)
        # R wave
        ecg += 1.20 * np.exp(-((t - b) / 0.02) ** 2)
        # S wave
        ecg -= 0.30 * np.exp(-((t - (b + 0.025)) / 0.018) ** 2)
        # T wave
        t_t = b + (qt_ms - 80) / 1000.0
        ecg += 0.30 * np.exp(-((t - t_t) / 0.07) ** 2)

    return ecg.astype(np.float32)


def test_detect_r_peaks_normal_hr():
    sig = generate_synthetic_ecg(hr_bpm=72, duration_s=10.0, fs=100.0)
    peaks = detect_r_peaks(sig, 100.0)
    # 10s at 72 bpm = ~12 beats
    assert 10 <= len(peaks) <= 13


def test_measure_intervals_normal():
    sig = generate_synthetic_ecg(hr_bpm=75, duration_s=10.0, fs=100.0, pr_ms=160, qrs_ms=90, qt_ms=380)
    ev = measure_intervals(sig, 100.0, leads=("II",))
    assert not ev.abstained
    val = ev.value
    assert 70 <= val["heart_rate_bpm"] <= 80
    assert val["rr_ms"] > 0
    assert val["qtc_bazett_ms"] is not None
    assert ev.risk in (RiskLevel.LOW, RiskLevel.MODERATE)


def test_measure_intervals_prolonged_qtc():
    # Long QT: 520 ms
    sig = generate_synthetic_ecg(hr_bpm=60, duration_s=10.0, fs=100.0, qt_ms=530)
    ev = measure_intervals(sig, 100.0, leads=("II",))
    assert not ev.abstained
    # at 60 bpm, RR = 1.0s, QTc = QT = ~530ms -> HIGH risk
    assert ev.risk == RiskLevel.HIGH
    assert any("QTc" in exp for exp in ev.explanation)


def test_measure_intervals_flatline_abstains():
    flat = np.zeros(1000, dtype=np.float32)
    ev = measure_intervals(flat, 100.0, leads=("II",))
    assert ev.abstained
    assert "yetarli emas" in ev.explanation[0]
