import numpy as np
import pytest

from core.concordance import Agreement
from core.evidence import RiskLevel
from core.registry import ModelCard
from screening.features import N_MELS, log_mel
from screening.model import PCGModel, Recording
from screening.pcg import TARGET_SR, assess_quality, bandpass, load_wav, preprocess, resample, windows
from screening.rules import newborn_pulse_ox, red_flags, resting_spo2
from screening.triage import triage


# ---- AAP 2020 pulsoksimetriya
@pytest.mark.parametrize("rh,foot,attempt,expected", [
    (98, 97, 1, "pass"),
    (95, 92, 1, "pass"),     # ≥95 va farq 3
    (97, 93, 1, "repeat"),   # farq 4
    (93, 93, 1, "repeat"),   # ikkalasi 90–94
    (93, 93, 2, "fail"),     # 2-urinish
    (89, 96, 1, "fail"),     # <90
    (96, 89, 2, "fail"),
])
def test_cchd_algorithm(rh, foot, attempt, expected):
    e = newborn_pulse_ox(rh, foot, attempt)
    assert e.value == expected
    assert e.risk == {"pass": RiskLevel.LOW, "repeat": RiskLevel.MODERATE, "fail": RiskLevel.HIGH}[expected]


def test_cchd_invalid_value_abstains_and_early_warning():
    assert newborn_pulse_ox(120, 95).abstained
    assert any("24 soat" in s for s in newborn_pulse_ox(98, 98, age_hours=10).explanation)


def test_resting_spo2_and_red_flags():
    assert resting_spo2(88).risk == RiskLevel.HIGH
    assert resting_spo2(93).risk == RiskLevel.MODERATE
    assert resting_spo2(98).risk == RiskLevel.LOW
    assert red_flags(["cyanosis"]).risk == RiskLevel.HIGH
    assert red_flags(["recurrent_pneumonia", "exercise_intolerance"]).risk == RiskLevel.MODERATE
    assert red_flags([]).risk == RiskLevel.NORMAL
    assert red_flags(["bogus"]).abstained


# ---- Signal
def test_resample_and_bandpass():
    x = np.random.default_rng(0).standard_normal(4000 * 3).astype(np.float32)
    assert resample(x, 4000).size == TARGET_SR * 3
    t = np.arange(TARGET_SR * 2) / TARGET_SR
    low, high = np.sin(2 * np.pi * 100 * t), np.sin(2 * np.pi * 600 * t)
    assert np.allclose(bandpass(low + high), low, atol=1e-3)


def test_quality_gates(wav_factory):
    raw, sr, clip = load_wav(wav_factory(seconds=3))
    assert not assess_quality(raw, sr, clip).ok
    raw, sr, clip = load_wav(wav_factory(clip=True))
    assert any("clipping" in r for r in assess_quality(raw, sr, clip).reasons)
    raw, sr, clip = load_wav(wav_factory())
    assert assess_quality(raw, sr, clip).ok
    q = assess_quality(np.zeros(sr * 10, dtype=np.float32), sr, 0.0)
    assert not q.ok


def test_logmel_shape(wav_factory):
    raw, sr, _ = load_wav(wav_factory(seconds=10))
    win = windows(preprocess(raw, sr))
    assert win.shape == (4, int(4 * TARGET_SR))   # 10 s, 4 s oyna, 2 s qadam
    feats = log_mel(win)
    assert feats.shape == (4, 1, N_MELS, 243) and feats.dtype == np.float32
    assert np.isfinite(feats).all()


# ---- Model (soxta backend)
CARD = ModelCard(name="pcg_test", version="0", task="t", dataset="CirCor DigiScope", weights="none",
                 thresholds={"murmur_low": 0.3, "murmur_high": 0.7, "window_agreement": 0.6})


def const_backend(p_m, p_o=0.2):
    return lambda x: (np.full(len(x), p_m, np.float32), np.full(len(x), p_o, np.float32))


def test_model_decides_and_aggregates_max_location(wav_factory):
    calls = iter([0.1, 0.9])
    model = PCGModel(CARD, lambda x: (np.full(len(x), next(calls), np.float32), np.zeros(len(x), np.float32)))
    e = model.analyze([Recording("AV", wav_factory()), Recording("MV", wav_factory(seed=1))], age_days=900)
    assert not e.abstained and e.risk == RiskLevel.MODERATE
    assert e.value["max_location"] == "MV" and e.value["p_murmur"] == pytest.approx(0.9)
    assert e.provenance.dataset_license == "ODC-By 1.0"


def test_model_low_probability_is_low_risk(wav_factory):
    e = PCGModel(CARD, const_backend(0.05)).analyze([Recording("AV", wav_factory())], age_days=900)
    assert e.risk == RiskLevel.LOW and not e.abstained


def test_model_abstains_in_gray_zone(wav_factory):
    e = PCGModel(CARD, const_backend(0.5)).analyze([Recording("AV", wav_factory())], age_days=900)
    assert e.abstained and "noaniq zona" in e.explanation[0]


def test_model_abstains_on_window_disagreement(wav_factory):
    backend = lambda x: (np.array([0.95, 0.95, 0.1, 0.1][:len(x)], np.float32), np.zeros(len(x), np.float32))
    e = PCGModel(CARD, backend).analyze([Recording("AV", wav_factory())], age_days=900)
    assert e.abstained and "kelishmadi" in e.explanation[0]


def test_model_abstains_for_neonates(wav_factory):
    model = PCGModel(CARD, const_backend(0.9))
    e = model.analyze([Recording("AV", wav_factory())], age_days=10)
    assert e.abstained and "validatsiya qilinmagan" in e.explanation[0]
    assert not model.analyze([Recording("AV", wav_factory())], age_days=40).abstained
    assert model.analyze([Recording("AV", wav_factory())]).abstained      # yosh noma'lum


def test_model_abstains_without_quality_recordings(wav_factory):
    e = PCGModel(CARD, const_backend(0.9)).analyze([Recording("AV", wav_factory(seconds=2))], age_days=900)
    assert e.abstained and "sifatli yozuv yo'q" in e.explanation[0]


# ---- Triaj
def test_triage_cchd_fail_overrides_everything():
    r = triage([newborn_pulse_ox(85, 95), red_flags([])], None)
    assert r.concordance.final_risk == RiskLevel.VERY_HIGH and r.action.startswith("DARHOL")


def test_triage_ai_escalates_but_flags_disagreement(wav_factory):
    pcg = PCGModel(CARD, const_backend(0.9)).analyze([Recording("AV", wav_factory())], age_days=900)
    r = triage([newborn_pulse_ox(98, 98), red_flags([])], pcg)
    assert r.concordance.status == Agreement.DISAGREE
    assert r.concordance.final_risk == RiskLevel.MODERATE and r.action.startswith("REJALI")


def test_triage_cchd_repeat_asks_for_second_measurement():
    r = triage([newborn_pulse_ox(93, 93, attempt=1), red_flags([])], None)
    assert r.concordance.final_risk == RiskLevel.MODERATE and r.action.startswith("QAYTA O'LCHASH")
    r2 = triage([newborn_pulse_ox(93, 93, attempt=2), red_flags([])], None)
    assert r2.action.startswith("DARHOL")


def test_triage_rule_only_when_no_model():
    r = triage([red_flags(["hepatomegaly"])], None)
    assert r.concordance.status == Agreement.RULE_ONLY and r.concordance.final_risk == RiskLevel.HIGH
