"""Sternotomiya yarasi rasmidan infeksiya / chok ajralishini aniqlash (CV modeli).

Klinik tekshiruvlar:
  1. Rasm sifati: xiralik (Laplacian blur variance), chaqnash (glare) va kam yorug'lik;
  2. Sternotomiya choki holati: clean (toza), erythema (qizarish), discharge (ajralma), dehiscence (ajralish);
  3. Xavf eskalatsiyasi: yuqori xavfda shifokor / jarrohga darhol ogohlantirish (Alert.RED / Alert.AMBER).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union
import numpy as np
from PIL import Image

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard, check_license

LABELS = ["clean", "erythema", "discharge", "dehiscence"]


def laplacian_variance(gray: np.ndarray) -> float:
    """Rasm xiraligini aniqlash uchun pure-numpy Laplacian dispersiyasi."""
    padded = np.pad(gray.astype(np.float32), 1, mode="edge")
    lap = (
        padded[0:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, 0:-2]
        + padded[1:-1, 2:]
        - 4.0 * gray.astype(np.float32)
    )
    return float(np.var(lap))


class WoundImageModel:
    available = True

    def __init__(self, card: ModelCard, session) -> None:
        check_license(card)
        self.card = card
        self.session = session
        self.input_name = session.get_inputs()[0].name

    @classmethod
    def from_dir(cls, weights_dir: str | Path) -> Optional["WoundImageModel"]:
        card_path = Path(weights_dir) / "model_card.json"
        if not card_path.exists():
            return None
        import onnxruntime as ort

        card = ModelCard.load(card_path)
        weights_file = Path(weights_dir) / card.weights
        if not weights_file.exists():
            return None
        session = ort.InferenceSession(str(weights_file), providers=["CPUExecutionProvider"])
        return cls(card, session)

    def validate_quality(self, img_pil: Image.Image) -> tuple[bool, str, dict]:
        """Tasvir sifatini klinik talablar bo'yicha tekshirish."""
        w, h = img_pil.size
        if w < 64 or h < 64:
            return False, f"Rasm o'lchami juda kichik ({w}x{h}), kamida 64x64 bo'lishi kerak", {}

        gray = np.array(img_pil.convert("L"), dtype=np.float32)
        blur_var = laplacian_variance(gray)
        mean_bright = float(np.mean(gray))

        th = self.card.thresholds or {}
        min_blur = th.get("min_blur_variance", 35.0)
        min_bright = th.get("min_brightness", 25.0)
        max_bright = th.get("max_brightness", 240.0)

        metrics = {"blur_variance": round(blur_var, 1), "brightness": round(mean_bright, 1)}

        if mean_bright < min_bright:
            return False, f"Rasm juda qorong'i (yorug'lik {mean_bright:.1f} < {min_bright}), yorug'roq joyda oling", metrics
        if mean_bright > max_bright:
            return False, f"Rasmda chaqnash (glare) yoki haddan ortiq yorug'lik bor ({mean_bright:.1f} > {max_bright})", metrics
        if blur_var < min_blur:
            return False, f"Rasm xira (fokus yo'q, dispersiya {blur_var:.1f} < {min_blur}), qayta oling", metrics

        # Haddan ortiq oq (clipped) piksellar nisbati
        overexposed_ratio = float(np.mean(gray >= 252.0))
        if overexposed_ratio > 0.40:
            return False, "Rasmda chaqnash (glare) sababli yara sohasi ko'rinmaydi", metrics

        return True, "", metrics

    def analyze(self, image_input: Union[bytes, Image.Image, np.ndarray]) -> Evidence:
        prov = Provenance(
            name=self.card.name,
            version=self.card.version,
            reference=self.card.task,
            dataset_license=self.card.dataset_license
        )

        try:
            if isinstance(image_input, bytes):
                img_pil = Image.open(io.BytesIO(image_input)).convert("RGB")
            elif isinstance(image_input, Image.Image):
                img_pil = image_input.convert("RGB")
            elif isinstance(image_input, np.ndarray):
                if image_input.dtype != np.uint8 and image_input.max() <= 1.0:
                    image_input = (image_input * 255).astype(np.uint8)
                img_pil = Image.fromarray(image_input).convert("RGB")
            else:
                return Evidence.abstain("guardian.wound_image", Source.MODEL, prov, "Noma'lum rasm formati")
        except Exception as exc:
            return Evidence.abstain("guardian.wound_image", Source.MODEL, prov, f"Rasm faylini ochib bo'lmadi: {exc}")

        ok, reason, metrics = self.validate_quality(img_pil)
        if not ok:
            return Evidence.abstain("guardian.wound_image", Source.MODEL, prov, reason, value=metrics)

        # 224x224 ga masshtablash va ImageNet standart normallashtirish
        resized = img_pil.resize((224, 224), Image.Resampling.BILINEAR)
        arr = np.array(resized, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
        norm = (arr - mean) / std
        tensor = np.transpose(norm, (2, 0, 1))[np.newaxis, ...]  # (1, 3, 224, 224)

        try:
            raw_out = self.session.run(None, {self.input_name: tensor})[0]
            probs = np.ravel(raw_out)
        except Exception as exc:
            return Evidence.abstain("guardian.wound_image", Source.MODEL, prov, f"Inference xatosi: {exc}")

        p_clean, p_erythema, p_discharge, p_dehiscence = [float(p) for p in probs[:4]]
        val = {
            "clean": round(p_clean, 4),
            "erythema": round(p_erythema, 4),
            "discharge": round(p_discharge, 4),
            "dehiscence": round(p_dehiscence, 4),
            "blur_variance": metrics.get("blur_variance")
        }

        th = self.card.thresholds or {}
        conf_min = th.get("abstain_confidence", 0.35)
        if max(p_clean, p_erythema, p_discharge, p_dehiscence) < conf_min:
            return Evidence.abstain("guardian.wound_image", Source.MODEL, prov,
                                    f"Noaniq tasvir (ishonchlilik darajasi past < {conf_min})", value=val)

        explanation = []
        if p_dehiscence >= th.get("dehiscence", 0.35):
            risk = RiskLevel.VERY_HIGH
            explanation.append(f"Sternotomiya chokida ajralish (dehissensiya) ehtimoli yuqori ({p_dehiscence:.1%})")
        elif p_discharge >= th.get("discharge", 0.45):
            risk = RiskLevel.HIGH
            explanation.append(f"Yaradan ekssudat / yiringli ajralma belgilari aniqlandi ({p_discharge:.1%})")
        elif p_erythema >= th.get("erythema", 0.35):
            risk = RiskLevel.MODERATE
            explanation.append(f"Yara atrofida 2+ sm eritema / yallig'lanish belgilari ({p_erythema:.1%})")
        else:
            risk = RiskLevel.LOW
            explanation.append(f"Sternotomiya yarasi toza, bitish asoratsiz ({p_clean:.1%})")

        return Evidence(
            kind="guardian.wound_image",
            value=val,
            unit="ehtimollik",
            source=Source.MODEL,
            provenance=prov,
            risk=risk,
            explanation=explanation
        )
