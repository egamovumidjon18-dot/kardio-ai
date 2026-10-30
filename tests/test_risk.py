import numpy as np
import pytest

from core.concordance import Agreement
from core.episode import Episode, Stage
from core.evidence import RiskLevel
from core.registry import ModelCard
from risk.aki import AKIInput, AKIModel, thakar
from risk.euroscore2 import EuroScoreInput, cockcroft_gault, euroscore2, lv_category, pa_category
from risk.protocol import aki_concordance, heart_team_protocol


def base(**kw):
    d = dict(age=55, female=False, weight_kg=80, creatinine_umol_l=70)
    d.update(kw)
    return EuroScoreInput(**d)


def test_minimum_euroscore_is_050_percent():
    e = euroscore2(base())               # CC > 85, hech qanday xavf omili yo'q
    assert e.value == pytest.approx(0.50, abs=0.005) and e.risk == RiskLevel.LOW


def test_matches_official_calculator_reference_case():
    """Rasmiy EuroSCORE II kalkulyatoridagi holat: 89.32%
    (michaeldismorrmd.github.io/posts/implement-euroscore2-risk-score-in-r)."""
    x = EuroScoreInput(age=70, female=True, weight_kg=70, creatinine_umol_l=300, on_dialysis=True,
                       extracardiac_arteriopathy=True, poor_mobility=True, previous_cardiac_surgery=True,
                       chronic_lung_disease=True, active_endocarditis=True, critical_preop_state=True,
                       insulin_diabetes=True, nyha=2, ccs4_angina=True, lvef_percent=25, recent_mi=True,
                       pa_systolic_mmhg=40, urgency="elective", weight_of_intervention="single_non_cabg",
                       thoracic_aorta=True)
    e = euroscore2(x)
    assert e.value == pytest.approx(89.32, abs=0.01) and e.risk == RiskLevel.VERY_HIGH


def test_age_term_and_renal_categories():
    assert euroscore2(base(age=60)).value == euroscore2(base(age=45)).value   # ≤60 → 1 ball
    assert euroscore2(base(age=75)).value > euroscore2(base(age=60)).value
    cc = cockcroft_gault(70, 70, 150, female=False)
    assert cc == pytest.approx((70 * 70) / (72 * 150 / 88.4))
    assert any("≤50" in s for s in euroscore2(base(age=70, weight_kg=70, creatinine_umol_l=150)).explanation)


def test_categories_and_validity():
    assert [lv_category(v) for v in (60, 50, 31, 30, 21, 20)] == ["good", "moderate", "moderate", "poor", "poor", "very_poor"]
    assert [pa_category(v) for v in (None, 30, 31, 55, 56)] == ["normal", "normal", "moderate", "moderate", "severe"]
    assert euroscore2(base(age=97)).abstained
    assert euroscore2(base(nyha=5)).abstained


def aki_in(**kw):
    d = dict(female=False, congestive_heart_failure=False, lvef_percent=55, preop_iabp=False, copd=False,
             insulin_diabetes=False, previous_cardiac_surgery=False, emergency=False, surgery="cabg",
             creatinine_umol_l=80)
    d.update(kw)
    return AKIInput(**d)


def test_thakar_points():
    assert thakar(aki_in()).value == 0
    full = aki_in(female=True, congestive_heart_failure=True, lvef_percent=30, preop_iabp=True, copd=True,
                  insulin_diabetes=True, previous_cardiac_surgery=True, emergency=True, surgery="other",
                  creatinine_umol_l=2.5 * 88.4)
    e = thakar(full)
    assert e.value == 17 and e.risk == RiskLevel.VERY_HIGH
    assert thakar(aki_in(creatinine_umol_l=1.5 * 88.4, surgery="valve")).value == 3
    assert thakar(aki_in(creatinine_umol_l=1.5 * 88.4, surgery="valve")).risk == RiskLevel.MODERATE


CARD = ModelCard(name="aki_test", version="0", task="KDIGO AKI", dataset="MIMIC-IV", weights="x",
                 thresholds={"moderate": 0.2, "high": 0.5, "abstain_band": [0.45, 0.5]})


def test_aki_model_and_concordance():
    ep = Episode(patient_ref="P", population="adult", stage=Stage.HEART_TEAM)
    ep.add(thakar(aki_in()))                                          # LOW
    ep.add(AKIModel(CARD, lambda x: 0.7).analyze(aki_in()))           # HIGH
    conc = aki_concordance(ep)
    assert conc.status == Agreement.DISAGREE and conc.final_risk == RiskLevel.HIGH
    ep.add(AKIModel(CARD, lambda x: 0.47).analyze(aki_in()))
    assert aki_concordance(ep).status == Agreement.AI_ABSTAINED


def test_aki_model_feature_vector_shape():
    seen = {}
    AKIModel(CARD, lambda x: seen.setdefault("x", x) is not None and 0.1).analyze(aki_in(surgery="cabg_valve"))
    assert seen["x"].shape == (1, 12) and seen["x"][0, 10] == 1.0


def test_protocol_lists_mandatory_discussion():
    ep = Episode(patient_ref="PSV-7", population="adult", stage=Stage.HEART_TEAM)
    ep.add(euroscore2(base(age=72)))
    ep.add(thakar(aki_in()))
    ep.add(AKIModel(CARD, lambda x: 0.9).analyze(aki_in()))
    text = heart_team_protocol(ep)
    assert "PSV-7" in text and "EuroSCORE II" in text and "ZIDDIYAT" in text
    assert "YAKUNIY TASHXIS EMAS" in text
    empty = heart_team_protocol(Episode(patient_ref="X", stage=Stage.HEART_TEAM))
    assert "EuroSCORE II hisoblanmagan" in empty
