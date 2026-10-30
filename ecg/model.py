"""EKG modeli (PTB-XL, 1D-CNN) — ONNX Runtime CPU inference + abstain-first.

Qaror tuzilishi:
  * signal sifati yomon / tarmoqlar yetishmaydi → abstain;
  * bemor 18 yoshdan kichik → abstain (PTB-XL faqat kattalar, bolalar EKG me'yorlari boshqa);
  * AFIB ehtimoli noaniq zonada (afib_low < p < afib_high) → abstain;
  * AFIB: p ≥ afib_high → "bo'lmachalar fibrillyatsiyasi ehtimoli yuqori" (HIGH — shifokor tasdiqlaydi);
  * aks holda boshqa toifalar (MI/STTC/CD/HYP) chegaradan oshsa → MODERATE, hech biri bo'lmasa → LOW.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard, check_license
from ecg.signal import LEADS_12, N_SAMPLES, assess_quality, preprocess, select_leads

# backend: [N, 12, 1000] → [N, n_classes] ehtimolliklar
Backend = Callable[[np.ndarray], np.ndarray]

PATHOLOGY_NAMES = {"MI": "miokard infarkti belgilari", "STTC": "ST-T o'zgarishlari",
                   "CD": "o'tkazuvchanlik buzilishi", "HYP": "gipertrofiya belgilari"}


def onnx_backend(path: str | Path) -> Backend:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    def run(x: np.ndarray) -> np.ndarray:
        logits = sess.run(["logits"], {name: x})[0]
        return (1.0 / (1.0 + np.exp(-logits))).astype(np.float32)

    return run


class ECGModel:
    min_age_years = 18.0

    def __init__(self, card: ModelCard, backend: Backend) -> None:
        check_license(card)
        self.card, self.backend = card, backend
        th = card.thresholds
        self.classes = list(th.get("classes", ["AFIB", "NORM", "MI", "STTC", "CD", "HYP"]))
        self.low = float(th.get("afib_low", 0.3))
        self.high = float(th.get("afib_high", 0.7))
        self.class_th = th.get("class_thresholds", {})
        self.leads = tuple(th.get("leads", LEADS_12))

    @classmethod
    def from_dir(cls, weights_dir: str | Path) -> Optional["ECGModel"]:
        """Og'irliklar bo'lmasa None — EKG moduli o'chiq, qoidalar ishlayveradi."""
        card_path = Path(weights_dir) / "model_card.json"
        onnx = Path(weights_dir) / "ecg.onnx"
        if not card_path.exists() or not onnx.exists():
            return None
        card = ModelCard.load(card_path)
        return cls(card, onnx_backend(Path(weights_dir) / card.weights))

    def _prov(self) -> Provenance:
        return Provenance(name=self.card.name, version=self.card.version,
                          reference=f"{self.card.task}; {self.card.dataset}",
                          dataset_license=self.card.dataset_license)

    def analyze(self, signal: np.ndarray, fs: float, leads: tuple[str, ...] = LEADS_12,
                age_years: Optional[float] = None) -> Evidence:
        """signal: [L, N] mV; leads — signal qatorlari nomlari (katta harf, 'AVR' shaklida)."""
        prov, kind = self._prov(), "ecg.afib"
        if age_years is not None and age_years < self.min_age_years:
            return Evidence.abstain(kind, Source.MODEL, prov,
                                    f"yosh {age_years:.0f}: model faqat kattalarda (PTB-XL) o'rgatilgan — "
                                    "bolalar EKG me'yorlari boshqa, kardiolog o'qiydi")
        try:
            x12 = select_leads(np.asarray(signal, dtype=np.float32), tuple(leads), self.leads)
        except ValueError as exc:
            return Evidence.abstain(kind, Source.MODEL, prov, str(exc))
        q = assess_quality(x12, fs, self.leads)
        if not q.ok:
            return Evidence.abstain(kind, Source.MODEL, prov, "sifatsiz EKG: " + "; ".join(q.reasons))

        x = preprocess(x12, fs)
        assert x.shape[-1] == N_SAMPLES
        p = self.backend(x[None])[0]
        probs = {c: round(float(p[i]), 4) for i, c in enumerate(self.classes)}
        p_af = probs["AFIB"]
        value = {"probabilities": probs, "p_afib": p_af, "bad_leads": q.bad_leads, "duration_s": round(q.duration_s, 1)}
        expl = [f"AFIB ehtimoli {p_af:.2f}"] + ([f"yaroqsiz tarmoqlar: {', '.join(q.bad_leads)}"] if q.bad_leads else [])

        if self.low < p_af < self.high:
            return Evidence.abstain(kind, Source.MODEL, prov,
                                    f"AFIB uchun noaniq zona ({self.low:.2f} < p={p_af:.2f} < {self.high:.2f})",
                                    value=value)
        if p_af >= self.high:
            return Evidence(kind=kind, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.HIGH,
                            uncertainty=round(1.0 - abs(2 * p_af - 1), 4),
                            explanation=["bo'lmachalar fibrillyatsiyasi ehtimoli yuqori — shifokor EKGni ko'rib tasdiqlaydi"]
                                        + expl)
        found = [PATHOLOGY_NAMES[c] for c in PATHOLOGY_NAMES
                 if c in probs and probs[c] >= float(self.class_th.get(c, 0.5))]
        value["other_findings"] = found
        if found:
            return Evidence(kind=kind, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.MODERATE,
                            uncertainty=round(1.0 - abs(2 * p_af - 1), 4),
                            explanation=["AFIB aniqlanmadi; boshqa o'zgarishlar ehtimoli: " + ", ".join(found)] + expl)
        return Evidence(kind=kind, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.LOW,
                        uncertainty=round(1.0 - abs(2 * p_af - 1), 4),
                        explanation=["AFIB va asosiy patologiyalar aniqlanmadi"] + expl)
