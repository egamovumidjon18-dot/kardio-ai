"""AI-EKG: tuzilmaviy yurak kasalliklari skriningi (EchoNext, research/train_shd.py) — faqat qabul mezonidan o'tgan yorliqlar.

Qaror tuzilishi (abstain-first):
  * model card'dagi `enabled` ro'yxatidan tashqaridagi yorliqlar umuman ko'rsatilmaydi (mezondan o'tmagan);
  * yosh < 18, sifatsiz EKG → abstain;
  * yoqilgan yorliqlardan biri p ≥ high → MODERATE: «… ehtimoli — ExoKG tavsiya etiladi» (tashxis emas);
  * hech biri musbat emas, lekin biri noaniq zonada → abstain;
  * hammasi p ≤ low → LOW: «belgi topilmadi» (kasallik yo'qligini kafolatlamaydi).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.model_safety import age_error, valid_probabilities
from core.registry import ModelCard, check_license
from ecg.signal import LEADS_12, N_SAMPLES, assess_quality, preprocess, select_leads

KIND = "ecg.shd"
NAMES_UZ = {"shd": "tuzilmaviy yurak kasalligi (umumiy)", "mitral_regurgitation": "mitral regurgitatsiya (o'rta/og'ir)",
            "tricuspid_regurgitation": "trikuspidal regurgitatsiya (o'rta/og'ir)",
            "rv_dysfunction": "o'ng qorincha sistolik disfunksiyasi (o'rta/og'ir)",
            "aortic_stenosis": "aorta stenozi (o'rta/og'ir)", "aortic_regurgitation": "aorta regurgitatsiyasi (o'rta/og'ir)",
            "pulmonary_hypertension": "o'pka gipertenziyasi (PASP ≥ 45)", "pericardial_effusion": "perikard suyuqligi",
            "lv_wall_thickness": "chap qorincha devori ≥ 13 mm", "tr_velocity": "TR tezligi ≥ 3.2 m/s",
            "pulmonary_regurgitation": "o'pka arteriyasi regurgitatsiyasi"}
Backend = Callable[[np.ndarray], np.ndarray]           # [N, 12, 1000] → [N, n_labels] ehtimollik


def onnx_backend(path: str | Path) -> Backend:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    def run(x: np.ndarray) -> np.ndarray:
        logits = sess.run(None, {name: x.astype(np.float32)})[0]
        return (1.0 / (1.0 + np.exp(-logits))).astype(np.float32)

    return run


class StructuralFromECG:
    min_age_years = 18.0

    def __init__(self, card: ModelCard, backend: Backend) -> None:
        check_license(card)
        self.card, self.backend = card, backend
        th = card.thresholds
        self.labels: list[str] = list(th["labels"])
        self.enabled: list[str] = [n for n in th["enabled"] if n in self.labels]
        self.th: dict[str, dict] = th["per_label"]
        self.leads = tuple(th.get("leads", LEADS_12))
        if not self.enabled:
            raise ValueError("birorta yorliq qabul mezonidan o'tmagan")

    @classmethod
    def from_dir(cls, weights_dir: str | Path) -> Optional["StructuralFromECG"]:
        d = Path(weights_dir)
        card_path = d / "model_card.json"
        if not card_path.exists() or not json.loads(card_path.read_text(encoding="utf-8")).get("passed", False):
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
        reason = age_error(age_years, self.min_age_years, 120, "yil")
        if reason:
            return Evidence.abstain(KIND, Source.MODEL, prov, reason)
        try:
            x12 = select_leads(np.asarray(signal, dtype=np.float32), tuple(leads), self.leads)
        except ValueError as exc:
            return Evidence.abstain(KIND, Source.MODEL, prov, str(exc))
        q = assess_quality(x12, fs, self.leads)
        if not q.ok:
            return Evidence.abstain(KIND, Source.MODEL, prov, "sifatsiz EKG: " + "; ".join(q.reasons))
        x = preprocess(x12, fs)
        assert x.shape[-1] == N_SAMPLES
        output = self.backend(x[None])
        if not valid_probabilities(output, (1, len(self.labels))):
            return Evidence.abstain(KIND, Source.MODEL, prov, "model ehtimolliklari noto'g'ri — qayta tekshirish kerak")
        p = output[0]
        status, probs = {}, {}
        for n in self.enabled:
            v = float(p[self.labels.index(n)])
            lo, hi = float(self.th[n]["low"]), float(self.th[n]["high"])
            probs[n] = v
            status[n] = "positive" if v >= hi else "negative" if v <= lo else "uncertain"
        pos = [n for n in self.enabled if status[n] == "positive"]
        value = {"probabilities": probs, "status": status, "positive": pos, "positive_names": [NAMES_UZ.get(n, n) for n in pos]}
        if pos:
            return Evidence(kind=KIND, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.MODERATE,
                            uncertainty=round(1.0 - max(probs[n] for n in pos), 4),
                            explanation=["EKG bo'yicha ehtimoli: " + ", ".join(NAMES_UZ.get(n, n) for n in pos),
                                         "ExoKG bilan tekshirish tavsiya etiladi — tashxis emas"])
        unsure = [n for n in self.enabled if status[n] == "uncertain"]
        if unsure:
            return Evidence.abstain(KIND, Source.MODEL, prov,
                                    "noaniq zona: " + ", ".join(NAMES_UZ.get(n, n) for n in unsure), value=value)
        return Evidence(kind=KIND, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.LOW,
                        uncertainty=round(max(probs.values()), 4),
                        explanation=["EKG bo'yicha tekshirilgan tuzilmaviy kasallik belgilari topilmadi",
                                     "bu kasallik yo'qligini kafolatlamaydi; shovqin yoki shikoyat bo'lsa ExoKG"])
