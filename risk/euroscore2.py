"""EuroSCORE II — operatsiyadagi o'lim xavfi (deterministik logistik formula).

Nashef SAM et al. EuroSCORE II. Eur J Cardiothorac Surg 2012;41(4):734–745.
Koeffitsiyentlar nashrdagi jadvaldan; rasmiy kalkulyatordagi namunaviy holat
testlarda tekshiriladi (tests/test_risk.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

REFERENCE = "Nashef SAM et al. EuroSCORE II. Eur J Cardiothorac Surg 2012;41(4):734-745"
CONSTANT = -5.324537

COEF = {
    "age": 0.0285181, "female": 0.2196434,
    "dialysis": 0.6421508, "cc_le50": 0.8592256, "cc_50_85": 0.303553,
    "extracardiac_arteriopathy": 0.5360268, "poor_mobility": 0.2407181,
    "previous_cardiac_surgery": 1.118599, "chronic_lung_disease": 0.1886564,
    "active_endocarditis": 0.6194522, "critical_preop_state": 1.086517,
    "insulin_diabetes": 0.3542749,
    "nyha": {1: 0.0, 2: 0.1070545, 3: 0.2958358, 4: 0.5597929},
    "ccs4_angina": 0.2226147,
    "lv": {"good": 0.0, "moderate": 0.3150652, "poor": 0.8084096, "very_poor": 0.9346919},
    "recent_mi": 0.1528943,
    "pa": {"normal": 0.0, "moderate": 0.1788899, "severe": 0.3491475},
    "urgency": {"elective": 0.0, "urgent": 0.3174673, "emergency": 0.7039121, "salvage": 1.362947},
    "weight": {"isolated_cabg": 0.0, "single_non_cabg": 0.0062118, "two": 0.5521478, "three_plus": 0.9724533},
    "thoracic_aorta": 0.6527205,
}


def cockcroft_gault(age: float, weight_kg: float, creatinine_umol_l: float, female: bool) -> float:
    """Kreatinin klirensi (ml/min). O'zbekistonda kreatinin odatda µmol/L da."""
    cr_mg_dl = creatinine_umol_l / 88.4
    return (140 - age) * weight_kg * (0.85 if female else 1.0) / (72 * cr_mg_dl)


def lv_category(ef_percent: float) -> str:
    if ef_percent > 50:
        return "good"
    if ef_percent >= 31:
        return "moderate"
    if ef_percent >= 21:
        return "poor"
    return "very_poor"


def pa_category(pa_systolic_mmhg: Optional[float]) -> str:
    if pa_systolic_mmhg is None or pa_systolic_mmhg < 31:
        return "normal"
    return "moderate" if pa_systolic_mmhg <= 55 else "severe"


@dataclass
class EuroScoreInput:
    age: float
    female: bool
    weight_kg: float
    creatinine_umol_l: float
    on_dialysis: bool = False
    extracardiac_arteriopathy: bool = False
    poor_mobility: bool = False
    previous_cardiac_surgery: bool = False
    chronic_lung_disease: bool = False
    active_endocarditis: bool = False
    critical_preop_state: bool = False
    insulin_diabetes: bool = False
    nyha: int = 1
    ccs4_angina: bool = False
    lvef_percent: float = 60
    recent_mi: bool = False                      # ≤90 kun
    pa_systolic_mmhg: Optional[float] = None
    urgency: Literal["elective", "urgent", "emergency", "salvage"] = "elective"
    weight_of_intervention: Literal["isolated_cabg", "single_non_cabg", "two", "three_plus"] = "isolated_cabg"
    thoracic_aorta: bool = False


def risk_category(pct: float) -> RiskLevel:
    """Platforma konvensiyasi (EuroSCORE II rasmiy toifalari yo'q)."""
    if pct < 2:
        return RiskLevel.LOW
    if pct < 5:
        return RiskLevel.MODERATE
    if pct < 10:
        return RiskLevel.HIGH
    return RiskLevel.VERY_HIGH


def euroscore2(x: EuroScoreInput) -> Evidence:
    prov = Provenance(name="euroscore2", version="2012", reference=REFERENCE)
    if not 18 <= x.age <= 95:
        return Evidence.abstain("risk.euroscore2", Source.RULE, prov,
                                f"yosh {x.age}: EuroSCORE II 18–95 yosh uchun validatsiya qilingan")
    if x.nyha not in COEF["nyha"] or x.weight_kg <= 0 or x.creatinine_umol_l <= 0:
        return Evidence.abstain("risk.euroscore2", Source.RULE, prov, "kiritilgan qiymatlar noto'g'ri")

    terms: list[tuple[str, float]] = [("konstanta", CONSTANT),
                                      (f"yosh {x.age:.0f}", COEF["age"] * max(1.0, x.age - 59))]
    cc = cockcroft_gault(x.age, x.weight_kg, x.creatinine_umol_l, x.female)
    if x.on_dialysis:
        terms.append(("dializ", COEF["dialysis"]))
    elif cc <= 50:
        terms.append((f"CC {cc:.0f} ml/min (≤50)", COEF["cc_le50"]))
    elif cc <= 85:
        terms.append((f"CC {cc:.0f} ml/min (51–85)", COEF["cc_50_85"]))
    for flag in ("female", "extracardiac_arteriopathy", "poor_mobility", "previous_cardiac_surgery",
                 "chronic_lung_disease", "active_endocarditis", "critical_preop_state",
                 "insulin_diabetes", "ccs4_angina", "recent_mi", "thoracic_aorta"):
        if getattr(x, flag):
            terms.append((flag, COEF[flag]))
    lv, pa = lv_category(x.lvef_percent), pa_category(x.pa_systolic_mmhg)
    for label, val in ((f"NYHA {x.nyha}", COEF["nyha"][x.nyha]), (f"LV {lv} (EF {x.lvef_percent:.0f}%)", COEF["lv"][lv]),
                       (f"PA {pa}", COEF["pa"][pa]), (f"shoshilinchlik {x.urgency}", COEF["urgency"][x.urgency]),
                       (f"aralashuv {x.weight_of_intervention}", COEF["weight"][x.weight_of_intervention])):
        if val:
            terms.append((label, val))

    logit = sum(v for _, v in terms)
    pct = 100.0 / (1.0 + math.exp(-logit))
    return Evidence(kind="risk.euroscore2", value=round(pct, 2), unit="% o'lim", source=Source.RULE,
                    provenance=prov, risk=risk_category(pct),
                    explanation=[f"{k}: {v:+.4f}" for k, v in terms] +
                                [f"logit {logit:.4f} → {pct:.2f}%", f"kreatinin klirensi {cc:.0f} ml/min"])
