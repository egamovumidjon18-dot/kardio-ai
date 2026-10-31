"""AI-EKG: 12 tarmoqli EKG'dan past EF (LVEF ≤ 45%) skriningi — EchoNext'da o'qitilgan (research/train_lowef.py).

Qaror tuzilishi (abstain-first):
  * og'irliklar yo'q yoki model card'da passed=false → modul o'chiq (abstain, sababi bilan);
  * bemor 18 yoshdan kichik → abstain (EchoNext faqat kattalar);
  * EKG sifati yomon / tarmoqlar yetishmaydi → abstain;
  * low < p < high (val'da tanlangan noaniq zona) → abstain;
  * p ≥ high → MODERATE: «past EF ehtimoli — ExoKG tavsiya etiladi» (tashxis emas, ExoKG o'lchaydi);
  * p ≤ low → LOW: «past EF belgisi yo'q» — bu EF normal ekanini KAFOLATLAMAYDI.
Litsenziya: PhysioNet Restricted Health Data License — faqat tadqiqot; product rejimida yuklanmaydi.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard, check_license
from ecg.signal import LEADS_12, N_SAMPLES, assess_quality, preprocess, select_leads

KIND = "ecg.low_ef"
BLOCKED_REASON = ("AI-EKG past EF modeli ulanmagan (og'irliklar yo'q yoki qabul mezonlaridan o'tmagan). "
                  "EF'ni ExoKG o'lchaydi.")
Backend = Callable[[np.ndarray], np.ndarray]           # [N, 12, 1000] → [N] ehtimollik


def onnx_backend(path: str | Path) -> Backend:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    def run(x: np.ndarray) -> np.ndarray:
        logit = sess.run(None, {name: x.astype(np.float32)})[0].reshape(-1)
        return (1.0 / (1.0 + np.exp(-logit))).astype(np.float32)

    return run


class LowEFFromECG:
    min_age_years = 18.0

    def __init__(self, card: ModelCard, backend: Backend) -> None:
        check_license(card)
        self.card, self.backend = card, backend
        th = card.thresholds
        self.low, self.high = float(th["low"]), float(th["high"])
        self.leads = tuple(th.get("leads", LEADS_12))

    @classmethod
    def from_dir(cls, weights_dir: str | Path) -> Optional["LowEFFromECG"]:
        """Og'irlik yo'q yoki qabul mezonlaridan o'tmagan bo'lsa None (modul o'chiq)."""
        d = Path(weights_dir)
        card_path = d / "model_card.json"
        if not card_path.exists():
            return None
        if not json.loads(card_path.read_text(encoding="utf-8")).get("passed", False):
            return None
        card = ModelCard.load(card_path)
        if not (d / card.weights).exists():
            return None
        return cls(card, onnx_backend(d / card.weights))

    def _prov(self) -> Provenance:
        return Provenance(name=self.card.name, version=self.card.version,
                          reference=f"{self.card.task}; {self.card.dataset}", dataset_license=self.card.dataset_license)

    def analyze(self, signal: np.ndarray, fs: float, leads: tuple[str, ...] = LEADS_12,
                age_years: Optional[float] = None) -> Evidence:
        prov = self._prov()
        if age_years is not None and age_years < self.min_age_years:
            return Evidence.abstain(KIND, Source.MODEL, prov,
                                    f"yosh {age_years:.0f}: model faqat kattalarda (EchoNext) o'rgatilgan — EF'ni ExoKG o'lchaydi")
        try:
            x12 = select_leads(np.asarray(signal, dtype=np.float32), tuple(leads), self.leads)
        except ValueError as exc:
            return Evidence.abstain(KIND, Source.MODEL, prov, str(exc))
        q = assess_quality(x12, fs, self.leads)
        if not q.ok:
            return Evidence.abstain(KIND, Source.MODEL, prov, "sifatsiz EKG: " + "; ".join(q.reasons))
        x = preprocess(x12, fs)
        assert x.shape[-1] == N_SAMPLES
        p = round(float(self.backend(x[None])[0]), 4)
        value = {"p_low_ef": p, "threshold_lvef": 45, "low": self.low, "high": self.high}
        unc = round(1.0 - abs(2 * p - 1), 4)
        if self.low < p < self.high:
            return Evidence.abstain(KIND, Source.MODEL, prov,
                                    f"past EF uchun noaniq zona ({self.low:.2f} < p={p:.2f} < {self.high:.2f})", value=value)
        if p >= self.high:
            return Evidence(kind=KIND, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.MODERATE,
                            uncertainty=unc,
                            explanation=["EKG bo'yicha past EF (≤45%) ehtimoli — ExoKG bilan tekshirish tavsiya etiladi",
                                         f"ehtimollik {p:.2f}", "tashxis emas: EF'ni ExoKG o'lchaydi"])
        return Evidence(kind=KIND, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.LOW, uncertainty=unc,
                        explanation=["EKG bo'yicha past EF belgisi topilmadi", f"ehtimollik {p:.2f}",
                                     "bu EF normal ekanini kafolatlamaydi; klinik shubha bo'lsa ExoKG"])
