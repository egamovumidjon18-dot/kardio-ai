"""Kardioxirurgiyadan keyingi buyrak zararlanishi: qoida (Thakar) + ML trek.

Thakar CV et al. A clinical score to predict acute renal failure after cardiac
surgery. J Am Soc Nephrol 2005;16(1):162–168. Natija: dializ talab qiladigan
O'BYe; ML modeli (MIMIC-IV, KDIGO AKI) boshqa natijani bashorat qilgani uchun
Concordance faqat xavf TOIFASI darajasida, tolerance=1 bilan solishtiriladi.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Callable, Literal, Optional

import numpy as np

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard, check_license

REFERENCE = "Thakar CV et al. J Am Soc Nephrol 2005;16(1):162-168"

SURGERY_POINTS = {"cabg": 0, "valve": 1, "cabg_valve": 2, "other": 2}


@dataclass
class AKIInput:
    female: bool
    congestive_heart_failure: bool
    lvef_percent: float
    preop_iabp: bool
    copd: bool
    insulin_diabetes: bool
    previous_cardiac_surgery: bool
    emergency: bool
    surgery: Literal["cabg", "valve", "cabg_valve", "other"]
    creatinine_umol_l: float


def thakar(x: AKIInput) -> Evidence:
    prov = Provenance(name="thakar_cleveland", version="2005", reference=REFERENCE)
    if (not math.isfinite(x.creatinine_umol_l) or not math.isfinite(x.lvef_percent)
            or x.creatinine_umol_l <= 0 or not 0 < x.lvef_percent <= 100 or x.surgery not in SURGERY_POINTS):
        return Evidence.abstain("risk.aki.rule", Source.RULE, prov, "kiritilgan qiymatlar noto'g'ri")
    cr = x.creatinine_umol_l / 88.4
    items = [
        ("ayol", 1, x.female), ("yurak yetishmovchiligi", 1, x.congestive_heart_failure),
        ("LVEF <35%", 1, x.lvef_percent < 35), ("operatsiyagacha IABP", 2, x.preop_iabp),
        ("COPD", 1, x.copd), ("insulin talab qiluvchi diabet", 1, x.insulin_diabetes),
        ("oldingi yurak operatsiyasi", 1, x.previous_cardiac_surgery), ("shoshilinch", 2, x.emergency),
        (f"operatsiya turi: {x.surgery}", SURGERY_POINTS[x.surgery], True),
        (f"kreatinin {cr:.2f} mg/dL", 5 if cr >= 2.1 else 2 if cr >= 1.2 else 0, True),
    ]
    score = sum(p for _, p, on in items if on)
    if score <= 2:
        risk = RiskLevel.LOW
    elif score <= 5:
        risk = RiskLevel.MODERATE
    elif score <= 8:
        risk = RiskLevel.HIGH
    else:
        risk = RiskLevel.VERY_HIGH
    trace = [f"{name}: +{p}" for name, p, on in items if on and p] + \
            [f"jami {score}/17 (0–2 past, 3–5 o'rta, 6–8 yuqori, ≥9 juda yuqori)"]
    return Evidence(kind="risk.aki.rule", value=score, unit="ball", source=Source.RULE,
                    provenance=prov, risk=risk, explanation=trace)


# ---------------------------------------------------------------- ML trek
FEATURES = ["female", "congestive_heart_failure", "lvef_percent", "preop_iabp", "copd",
            "insulin_diabetes", "previous_cardiac_surgery", "emergency", "creatinine_umol_l",
            "surgery_valve", "surgery_cabg_valve", "surgery_other"]


def featurize(x: AKIInput) -> np.ndarray:
    d = asdict(x)
    row = [float(d[k]) for k in FEATURES[:9]] + [float(x.surgery == s) for s in ("valve", "cabg_valve", "other")]
    return np.array([row], dtype=np.float32)


class AKIModel:
    """MIMIC-IV da o'qitiladigan model uchun interfeys (ONNX, CPU).

    Karta thresholds: {"low": p, "moderate": p, "high": p} — ehtimollik chegaralari;
    "abstain_band": [a, b] — shu oraliqda xulosa berilmaydi.
    """

    def __init__(self, card: ModelCard, predict: Callable[[np.ndarray], float]) -> None:
        check_license(card)
        self.card, self.predict = card, predict

    @classmethod
    def from_dir(cls, weights_dir: str | Path) -> Optional["AKIModel"]:
        card_path = Path(weights_dir) / "model_card.json"
        if not card_path.exists():
            return None
        import onnxruntime as ort

        card = ModelCard.load(card_path)
        sess = ort.InferenceSession(str(Path(weights_dir) / card.weights), providers=["CPUExecutionProvider"])
        name = sess.get_inputs()[0].name
        return cls(card, lambda x: float(np.ravel(sess.run(None, {name: x})[-1])[-1]))

    def analyze(self, x: AKIInput) -> Evidence:
        prov = Provenance(name=self.card.name, version=self.card.version, reference=self.card.task,
                          dataset_license=self.card.dataset_license)
        if thakar(x).abstained:
            return Evidence.abstain("risk.aki.model", Source.MODEL, prov, "kiritilgan qiymatlar noto'g'ri")
        p = self.predict(featurize(x))
        if not math.isfinite(p) or not 0 <= p <= 1:
            return Evidence.abstain("risk.aki.model", Source.MODEL, prov, "model ehtimolligi noto'g'ri")
        th = self.card.thresholds
        band = th.get("abstain_band")
        if band and band[0] < p < band[1]:
            return Evidence.abstain("risk.aki.model", Source.MODEL, prov,
                                    f"noaniq zona ({band[0]} < p={p:.3f} < {band[1]})", value=round(p, 4))
        if p >= th.get("high", 0.5):
            risk = RiskLevel.HIGH
        elif p >= th.get("moderate", 0.2):
            risk = RiskLevel.MODERATE
        else:
            risk = RiskLevel.LOW
        return Evidence(kind="risk.aki.model", value=round(p, 4), unit="ehtimollik", source=Source.MODEL,
                        provenance=prov, risk=risk, explanation=[f"KDIGO AKI ehtimoli {p:.1%}"])
