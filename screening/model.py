"""PCG shovqin (murmur) modeli — ONNX Runtime CPU inference + abstain-first.

Bemor darajasidagi qaror:
  * har bir yozuv (auskultatsiya nuqtasi) → oynalar → oyna ehtimolliklari;
  * yozuv ehtimolligi = oynalar o'rtachasi; bemor = yozuvlar maksimumi
    (shovqin bitta nuqtada eshitilsa ham bor deb hisoblanadi — CirCor kabi);
  * abstain: sifatli yozuv yo'q / oynalar kelishmaydi / ehtimollik noaniq zonada.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.model_safety import age_error, valid_probabilities
from core.registry import ModelCard, check_license
from screening.features import log_mel
from screening.pcg import assess_quality, load_wav, preprocess, windows

LOCATIONS = ("AV", "PV", "TV", "MV", "Phc")   # CirCor auskultatsiya nuqtalari

# backend: [N,1,M,T] → (p_murmur[N], p_abnormal[N])
Backend = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]


def _softmax_pos(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return (e[:, 1] / e.sum(axis=1)).astype(np.float32)


def onnx_backend(path: str | Path) -> Backend:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    def run(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        murmur, outcome = sess.run(["murmur_logits", "outcome_logits"], {in_name: x})
        return _softmax_pos(murmur), _softmax_pos(outcome)

    return run


@dataclass
class Recording:
    location: str
    wav: bytes | str | Path


class PCGModel:
    def __init__(self, card: ModelCard, backend: Backend) -> None:
        check_license(card)
        self.card = card
        self.backend = backend
        th = card.thresholds
        self.low = float(th.get("murmur_low", 0.3))         # ≤ low → shovqin yo'q
        self.high = float(th.get("murmur_high", 0.7))       # ≥ high → shovqin bor
        self.min_agreement = float(th.get("window_agreement", 0.6))
        # CirCor'da neonatlar deyarli yo'q (6 ta); ZCHSound tashqi sinovida neonatlarda ishlamadi.
        self.min_age_days = float(th.get("min_age_days", 29))

    @classmethod
    def from_dir(cls, weights_dir: str | Path) -> Optional["PCGModel"]:
        """Og'irliklar bo'lmasa None — platforma RULE_ONLY rejimida ishlaydi."""
        card_path = Path(weights_dir) / "model_card.json"
        if not card_path.exists():
            return None
        card = ModelCard.load(card_path)
        return cls(card, onnx_backend(Path(weights_dir) / card.weights))

    def _provenance(self) -> Provenance:
        return Provenance(name=self.card.name, version=self.card.version,
                          reference=f"{self.card.task}; {self.card.dataset}",
                          dataset_license=self.card.dataset_license)

    def analyze(self, recordings: list[Recording], age_days: Optional[float] = None,
                age_range_days: Optional[tuple[float, float]] = None) -> Evidence:
        prov = self._provenance()
        reason = age_error(age_days, self.min_age_days, 365 * 21, "kun")
        # Research datasets may give a documented age band instead of an exact age.
        # Accept only if the ENTIRE band is eligible; never invent an exact age.
        if age_days is None and age_range_days is not None:
            lo, hi = age_range_days
            if lo <= hi and not age_error(lo, self.min_age_days, 365 * 21, "kun") and not age_error(hi, self.min_age_days, 365 * 21, "kun"):
                reason = None
        if reason:
            return Evidence.abstain("screening.pcg", Source.MODEL, prov, reason)
        per_rec, skipped = [], []
        for rec in recordings:
            raw, sr, clip = load_wav(rec.wav)
            q = assess_quality(raw, sr, clip)
            if not q.ok:
                skipped.append(f"{rec.location}: " + "; ".join(q.reasons))
                continue
            win = windows(preprocess(raw, sr))
            p_m, p_o = self.backend(log_mel(win))
            if not valid_probabilities(p_m, (len(win),)) or not valid_probabilities(p_o, (len(win),)):
                return Evidence.abstain("screening.pcg", Source.MODEL, prov,
                                        "model ehtimolliklari noto'g'ri — qayta tekshirish kerak")
            p_rec = float(p_m.mean())
            agree = float(np.mean((p_m >= 0.5) == (p_rec >= 0.5)))
            per_rec.append({"location": rec.location, "p_murmur": p_rec,
                            "p_abnormal": round(float(p_o.mean()), 4),
                            "window_agreement": agree, "n_windows": int(len(p_m))})

        if not per_rec:
            return Evidence.abstain("screening.pcg", Source.MODEL, prov,
                                    "sifatli yozuv yo'q: " + " | ".join(skipped),
                                    value={"recordings": [], "skipped": skipped})

        top = max(per_rec, key=lambda r: r["p_murmur"])
        p = top["p_murmur"]
        value = {"p_murmur": p, "p_abnormal": max(r["p_abnormal"] for r in per_rec),
                 "max_location": top["location"], "recordings": per_rec, "skipped": skipped}
        expl = [f"eng yuqori ehtimollik {top['location']} nuqtasida: {p:.2f}"] + \
               [f"o'tkazib yuborildi — {s}" for s in skipped]

        if top["window_agreement"] < self.min_agreement:
            return Evidence.abstain("screening.pcg", Source.MODEL, prov,
                                    f"{top['location']}: oynalar kelishmadi "
                                    f"({top['window_agreement']:.0%} < {self.min_agreement:.0%})", value=value)
        if self.low < p < self.high:
            return Evidence.abstain("screening.pcg", Source.MODEL, prov,
                                    f"noaniq zona ({self.low:.2f} < p={p:.2f} < {self.high:.2f})", value=value)

        murmur = p >= self.high
        return Evidence(kind="screening.pcg", value=value, source=Source.MODEL, provenance=prov,
                        risk=RiskLevel.MODERATE if murmur else RiskLevel.LOW,
                        uncertainty=round(1.0 - abs(2 * p - 1), 4),
                        explanation=["patologik shovqin ehtimoli yuqori" if murmur else "shovqin aniqlanmadi"] + expl)
