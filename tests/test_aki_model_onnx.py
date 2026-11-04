from pathlib import Path
import pytest
from core.evidence import RiskLevel, Source
from risk.aki import AKIInput, AKIModel, thakar


def test_aki_onnx_model_loads_and_infers():
    weights_dir = Path("weights/aki")
    if not (weights_dir / "aki.onnx").exists():
        pytest.skip("weights/aki/aki.onnx mavjud emas")

    assert AKIModel.from_dir(weights_dir) is None   # sintetik — dasturga yuklanmaydi
    model = AKIModel.from_dir(weights_dir, allow_synthetic=True)   # faqat muhandislik sinovi
    assert model is not None
    assert model.card.name == "csa_aki_ml"
    assert model.card.synthetic is True
    assert model.card.commercial_use is False
    assert model.card.metrics == {}          # haqiqiy bemorda o'lchanmagan raqam yo'q

    # Past xavfli elektiv bemor (yosh, LVEF 60%, Cr 75, elektiv KShSh)
    low_x = AKIInput(
        female=False, congestive_heart_failure=False, lvef_percent=60.0,
        preop_iabp=False, copd=False, insulin_diabetes=False,
        previous_cardiac_surgery=False, emergency=False, surgery="cabg",
        creatinine_umol_l=75.0
    )
    ev_low = model.analyze(low_x)
    assert not ev_low.abstained
    assert ev_low.kind == "risk.aki.model"
    assert ev_low.source == Source.MODEL
    assert ev_low.risk == RiskLevel.LOW
    assert ev_low.value < 0.15

    # Yuqori xavfli bemor (Cr 260, IABP, shoshilinch, LVEF 25%, re-op)
    high_x = AKIInput(
        female=True, congestive_heart_failure=True, lvef_percent=25.0,
        preop_iabp=True, copd=True, insulin_diabetes=True,
        previous_cardiac_surgery=True, emergency=True, surgery="cabg_valve",
        creatinine_umol_l=260.0
    )
    ev_high = model.analyze(high_x)
    assert not ev_high.abstained
    assert ev_high.risk == RiskLevel.HIGH
    assert ev_high.value >= 0.50
