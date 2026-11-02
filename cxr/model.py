"""Ko'krak qafasi rentgenogrammasi (CXR) modeli — ONNX CPU inference + abstain-first.

Tahlil yo'nalishlari:
  1. Kardiomegaliya (yurak kengayishi): Kardio-torakal indeks (CTR > 0.50);
  2. O'pka venoz dimlanishi va o'pka shishi (pulmonary congestion/edema).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Union

import numpy as np
from PIL import Image

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard, check_license
from cxr.image import assess_cxr_quality, load_cxr_gray, to_model_input

Backend = Callable[[np.ndarray], np.ndarray]


def onnx_backend(path: str | Path) -> Backend:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    def run(x: np.ndarray) -> np.ndarray:
        return sess.run(["output"], {name: x})[0]

    return run


class CXRModel:
    def __init__(self, card: ModelCard, backend: Backend) -> None:
        check_license(card)
        self.card = card
        self.backend = backend
        th = card.thresholds
        self.cardio_th = float(th.get("cardiomegaly_prob", 0.50))
        self.congest_th = float(th.get("congestion_prob", 0.50))
        self.ctr_cutoff = float(th.get("ctr_cutoff", 0.50))
        self.ctr_severe = float(th.get("ctr_severe", 0.60))
        self.congest_severe = float(th.get("congestion_severe", 0.75))

    @classmethod
    def from_dir(cls, weights_dir: str | Path = "weights/cxr") -> Optional["CXRModel"]:
        p = Path(weights_dir)
        card_p = p / "model_card.json"
        onnx_p = p / "cxr.onnx"
        if not card_p.exists() or not onnx_p.exists():
            return None
        card = ModelCard.load(card_p)
        return cls(card, onnx_backend(p / card.weights))

    def _prov(self) -> Provenance:
        return Provenance(
            name=self.card.name,
            version=self.card.version,
            reference=f"{self.card.task}; {self.card.dataset}",
            dataset_license=self.card.dataset_license,
        )

    def predict(
        self,
        source: Union[bytes, str, Path, np.ndarray, Image.Image],
        view_position: str = "PA",
    ) -> Evidence:
        """Rentgenogrammani tahlil qiladi va Evidence qaytaradi."""
        prov = self._prov()

        # Proyeksiya tekshiruvi: lateral (yon) yoki qiyshiq bo'lsa abstain
        norm_view = (view_position or "PA").strip().upper()
        if norm_view not in ("PA", "AP"):
            return Evidence.abstain(
                kind="cxr.findings",
                source=Source.MODEL,
                provenance=prov,
                reason=f"Faqat frontal (PA/AP) proyeksiyalar qabul qilinadi (kiritildi: {norm_view})",
            )

        try:
            arr = load_cxr_gray(source)
        except Exception as exc:
            return Evidence.abstain(
                kind="cxr.findings",
                source=Source.MODEL,
                provenance=prov,
                reason=f"Rentgenogramma tasvirini ochib bo'lmadi: {exc}",
            )

        ok, err = assess_cxr_quality(arr)
        if not ok:
            return Evidence.abstain(
                kind="cxr.findings",
                source=Source.MODEL,
                provenance=prov,
                reason=f"Tasvir sifati yetarli emas: {err}",
            )

        inp = to_model_input(arr)
        raw = self.backend(inp)[0]  # [3]

        # Sigmoid va CTR hisoblash
        p_cardio = float(1.0 / (1.0 + np.exp(-raw[0])))
        p_congest = float(1.0 / (1.0 + np.exp(-raw[1])))
        # raw[2] sigmoid qilinib [0.35, 0.75] oralig'iga masshtablanadi
        sig_ctr = float(1.0 / (1.0 + np.exp(-raw[2])))
        ctr = round(float(sig_ctr * 0.40 + 0.35), 3)

        has_cardio = ctr > self.ctr_cutoff or p_cardio >= self.cardio_th
        has_congest = p_congest >= self.congest_th

        # Klinik xavf darajasi va tushuntirish
        expl = []
        if ctr >= self.ctr_severe:
            risk = RiskLevel.VERY_HIGH
            expl.append(f"Og'ir kardiomegaliya (CTR={ctr:.2f} >= {self.ctr_severe})")
        elif has_cardio:
            risk = RiskLevel.HIGH
            expl.append(f"Kardiomegaliya belgilari (CTR={ctr:.2f} > {self.ctr_cutoff}, ehtimollik {int(p_cardio*100)}%)")
        else:
            expl.append(f"Yurak soyasi o'lchamlari me'yorda (CTR={ctr:.2f} <= {self.ctr_cutoff})")

        if p_congest >= self.congest_severe:
            risk = RiskLevel.VERY_HIGH
            expl.append(f"O'tkir o'pka shishi / kuchli venoz dimlanish (ehtimollik {int(p_congest*100)}%)")
        elif has_congest:
            if risk != RiskLevel.VERY_HIGH:
                risk = RiskLevel.HIGH
            expl.append(f"O'pka qon aylanishida venoz dimlanish belgilari (ehtimollik {int(p_congest*100)}%)")
        else:
            expl.append("O'pka maydonlarida yaqqol dimlanish belgilari yo'q")

        if not has_cardio and not has_congest:
            risk = RiskLevel.LOW

        val = {
            "view": norm_view,
            "ctr_ratio": ctr,
            "cardiomegaly": bool(has_cardio),
            "cardiomegaly_prob": round(p_cardio, 4),
            "pulmonary_congestion": bool(has_congest),
            "congestion_prob": round(p_congest, 4),
            "severity": "severe" if risk == RiskLevel.VERY_HIGH else "moderate" if risk == RiskLevel.HIGH else "normal",
        }

        return Evidence(
            kind="cxr.findings",
            value=val,
            source=Source.MODEL,
            provenance=prov,
            risk=risk,
            explanation=expl,
        )
