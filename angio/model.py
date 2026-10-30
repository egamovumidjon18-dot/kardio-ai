"""Koronar angiografiya stenoz nomzodlari (ARCADE, U-Net) — ONNX Runtime CPU inference + abstain-first.

MUHIM: bu SYNTAX KALKULYATORI EMAS. Natija — "SYNTAX bahosiga yordamchi": kadrdagi shubhali stenoz
nomzodlarini ko'rsatadi, xolos. Segment nomi, okklyuziya, bifurkatsiya, kalsifikatsiya va SYNTAX balli
baholanmaydi — buni Heart Team (shifokor) qiladi. "Nomzod topilmadi" — "stenoz yo'q" degani EMAS.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np

from angio.image import SIZE, assess_quality, candidates, load_gray, to_model_input
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard, check_license

Backend = Callable[[np.ndarray], np.ndarray]   # [1,1,512,512] → [512,512] ehtimollik

LABEL = "SYNTAX-ga yordamchi: stenoz nomzodlari (SYNTAX kalkulyatori emas)"


def onnx_backend(path: str | Path) -> Backend:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    def run(x: np.ndarray) -> np.ndarray:
        logits = sess.run(["logits"], {name: x})[0][0, 0]
        return (1.0 / (1.0 + np.exp(-logits))).astype(np.float32)

    return run


class AngioModel:
    # Bir kadrda nomzodlar soni mantiqiy chegarasi: undan ko'pi — model shovqinda "ko'ryapti".
    max_plausible = 12

    def __init__(self, card: ModelCard, backend: Backend) -> None:
        check_license(card)
        self.card, self.backend = card, backend
        th = card.thresholds
        self.thr = float(th.get("prob", 0.5))
        self.min_area = int(th.get("min_area_px", 30))

    @classmethod
    def from_dir(cls, weights_dir: str | Path) -> Optional["AngioModel"]:
        card_path, onnx = Path(weights_dir) / "model_card.json", Path(weights_dir) / "angio.onnx"
        if not card_path.exists() or not onnx.exists():
            return None
        card = ModelCard.load(card_path)
        return cls(card, onnx_backend(Path(weights_dir) / card.weights))

    def _prov(self) -> Provenance:
        return Provenance(name=self.card.name, version=self.card.version,
                          reference=f"{self.card.task}; {self.card.dataset}",
                          dataset_license=self.card.dataset_license)

    def analyze(self, image: bytes | str | Path | np.ndarray) -> Evidence:
        """image: PNG/JPG baytlari, fayl yo'li yoki kulrang uint8 [H, W]."""
        prov, kind = self._prov(), "angio.stenosis_assist"
        gray = image if isinstance(image, np.ndarray) else load_gray(image)
        q = assess_quality(gray)
        if not q.ok:
            return Evidence.abstain(kind, Source.MODEL, prov, "kadr yaroqsiz: " + "; ".join(q.reasons))
        prob = self.backend(to_model_input(gray))
        cands = candidates(prob, self.thr, self.min_area)
        value = {"label": LABEL, "n_candidates": len(cands), "candidates": cands,
                 "size": SIZE, "prob_threshold": self.thr}
        note = "Bu SYNTAX kalkulyatori emas — nomzodlarni Heart Team angiogrammada tekshiradi."
        if len(cands) > self.max_plausible:
            return Evidence.abstain(kind, Source.MODEL, prov,
                                    f"{len(cands)} ta nomzod — ishonchsiz (shovqin yoki noto'g'ri turdagi kadr)", value=value)
        if not cands:
            # Nomzod yo'qligi tinchlantirmaydi (sezgirlik < 100%): xavf UNKNOWN qoladi, LOW emas.
            return Evidence(kind=kind, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.UNKNOWN,
                            explanation=["bu kadrda stenoz nomzodi topilmadi — bu 'stenoz yo'q' degani EMAS; "
                                         "ko'p ko'rinishli angiogrammani shifokor baholaydi", note])
        return Evidence(kind=kind, value=value, source=Source.MODEL, provenance=prov, risk=RiskLevel.MODERATE,
                        uncertainty=round(1.0 - float(np.mean([c["confidence"] for c in cands])), 3),
                        explanation=[f"{len(cands)} ta stenoz nomzodi; eng ishonchlisi {cands[0]['confidence']:.2f} "
                                     f"(markaz {cands[0]['center_xy']})", note])
