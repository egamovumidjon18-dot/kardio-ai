import io
from pathlib import Path
import numpy as np
from PIL import Image
import pytest

from core.evidence import RiskLevel, Source
from guardian.wound_cv import WoundImageModel


def test_wound_onnx_model_loads_and_validates():
    weights_dir = Path("weights/wound")
    if not (weights_dir / "wound.onnx").exists():
        pytest.skip("weights/wound/wound.onnx mavjud emas")

    assert WoundImageModel.from_dir(weights_dir) is None   # sintetik — dasturga yuklanmaydi
    model = WoundImageModel.from_dir(weights_dir, allow_synthetic=True)
    assert model is not None
    assert model.available is True
    assert model.card.name == "wound_image_cv"
    assert model.card.synthetic is True and model.card.commercial_use is False

    # 1. Rasm xiralik (blur) testi — silliq monoxrom rasm (dispersiya < 35)
    smooth_arr = np.ones((224, 224, 3), dtype=np.uint8) * 128
    ev_blur = model.analyze(smooth_arr)
    assert ev_blur.abstained
    assert "xira" in ev_blur.explanation[0]

    # 2. Qorong'i rasm testi (mean < 25)
    dark_arr = np.ones((224, 224, 3), dtype=np.uint8) * 10
    ev_dark = model.analyze(dark_arr)
    assert ev_dark.abstained
    assert "qorong'i" in ev_dark.explanation[0]

    # 3. Yaroqli rasm tahlili (teksturali)
    rng = np.random.default_rng(42)
    textured = np.clip(rng.normal(128, 30, (224, 224, 3)), 0, 255).astype(np.uint8)
    ev_valid = model.analyze(textured)
    assert not ev_valid.abstained
    assert ev_valid.kind == "guardian.wound_image"
    assert ev_valid.source == Source.MODEL
    assert "clean" in ev_valid.value
    assert "dehiscence" in ev_valid.value
