import numpy as np
import pytest

from core.evidence import RiskLevel
from core.registry import LicenseError, ModelCard
from ecg.model import ECGModel
from ecg.signal import LEADS_12, N_SAMPLES, assess_quality, preprocess, read_csv, resample, select_leads

CARD = ModelCard(name="ecg_test", version="0", task="t", dataset="PTB-XL", weights="none",
                 thresholds={"afib_low": 0.3, "afib_high": 0.7,
                             "class_thresholds": {"MI": 0.5, "STTC": 0.5, "CD": 0.5, "HYP": 0.5}})


def fake_ecg(fs=500, seconds=10.0, seed=0, n_leads=12):
    """Sun'iy EKG: ~75/min QRS + T to'lqinlari, ozgina shovqin."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(fs * seconds)) / fs
    x = np.zeros_like(t)
    for b in np.arange(0.4, seconds, 0.8):
        x += 1.2 * np.exp(-((t - b) ** 2) / (2 * 0.012 ** 2)) + 0.3 * np.exp(-((t - b - 0.25) ** 2) / (2 * 0.05 ** 2))
    return np.stack([x * (1 + 0.1 * i) + 0.01 * rng.standard_normal(t.size) for i in range(n_leads)]).astype(np.float32)


def backend(probs):
    return lambda x: np.tile(np.array(probs, dtype=np.float32), (len(x), 1))


#                      AFIB  NORM  MI   STTC  CD   HYP
def model(probs):
    return ECGModel(CARD, backend(probs))


def test_preprocess_shape_and_resample():
    x = fake_ecg(fs=500)
    y = preprocess(x, 500)
    assert y.shape == (12, N_SAMPLES) and y.dtype == np.float32
    assert np.allclose(y.mean(axis=1), 0, atol=1e-3)
    assert resample(x, 500).shape[-1] == 1000


def test_afib_high_probability_is_high_risk():
    ev = model([0.95, 0.01, 0.1, 0.1, 0.1, 0.1]).analyze(fake_ecg(), 500, age_years=60)
    assert not ev.abstained and ev.risk == RiskLevel.HIGH and ev.kind == "ecg.afib"
    assert "shifokor" in ev.explanation[0]


def test_uncertain_zone_abstains():
    ev = model([0.5, 0.5, 0.1, 0.1, 0.1, 0.1]).analyze(fake_ecg(), 500, age_years=60)
    assert ev.abstained and "noaniq" in ev.explanation[0]


def test_no_afib_other_findings_moderate_and_normal_low():
    assert model([0.02, 0.1, 0.9, 0.1, 0.1, 0.1]).analyze(fake_ecg(), 500, age_years=60).risk == RiskLevel.MODERATE
    ev = model([0.02, 0.9, 0.1, 0.1, 0.1, 0.1]).analyze(fake_ecg(), 500, age_years=60)
    assert ev.risk == RiskLevel.LOW and not ev.abstained


def test_poor_quality_abstains():
    flat = fake_ecg()
    flat[:] = 0
    assert model([0.9, 0, 0, 0, 0, 0]).analyze(flat, 500, age_years=60).abstained
    ev = model([0.9, 0, 0, 0, 0, 0]).analyze(fake_ecg(seconds=4), 500, age_years=60)
    assert ev.abstained and "qisqa" in ev.explanation[0]
    noisy = fake_ecg()
    noisy += np.random.default_rng(1).standard_normal(noisy.shape).astype(np.float32) * 1.5
    assert not assess_quality(noisy, 500, LEADS_12).ok


def test_one_or_two_bad_leads_tolerated_three_not():
    x = fake_ecg()
    x[3] = 0
    x[4] = 0
    assert assess_quality(x, 500, LEADS_12).ok
    x[5] = 0
    assert not assess_quality(x, 500, LEADS_12).ok


def test_missing_leads_and_children_abstain():
    m = model([0.9, 0, 0, 0, 0, 0])
    ev = m.analyze(fake_ecg(n_leads=1), 500, ("II",), age_years=60)
    assert ev.abstained and "tarmoq" in ev.explanation[0]
    assert m.analyze(fake_ecg(), 500, age_years=9).abstained


def test_lead_order_is_respected():
    x = fake_ecg()
    out = select_leads(x, tuple(reversed(LEADS_12)), LEADS_12)
    assert np.array_equal(out, x[::-1])


def test_csv_reader():
    x = fake_ecg(fs=100, seconds=10)
    lines = ["time,I,II,aVR"] + [f"{i / 100},{x[0, i]},{x[1, i]},{x[2, i]}" for i in range(x.shape[1])]
    sig, leads = read_csv("\n".join(lines).encode(), 100)
    assert leads == ("I", "II", "AVR") and sig.shape == (3, 1000)
    with pytest.raises(ValueError):
        read_csv(b"I,II\n1,abc\n", 100)


def test_product_mode_license(monkeypatch):
    monkeypatch.setenv("CARDIOPATH_MODE", "product")
    model([0.1] * 6)                                           # PTB-XL: CC-BY → ruxsat
    with pytest.raises(LicenseError):
        ECGModel(ModelCard(name="x", version="0", task="t", dataset="MIMIC-IV-ECHO", weights="n"), backend([0.1] * 6))


def test_from_dir_missing_returns_none(tmp_path):
    assert ECGModel.from_dir(tmp_path) is None
