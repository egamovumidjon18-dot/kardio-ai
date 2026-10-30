"""Rad etilgan ko'p manbali model tasodifan ishlatilmasin; ZCHSound ishtirokidagi model mahsulot rejimida bloklansin."""
from pathlib import Path

import pytest

from core.registry import DATASET_LICENSES, LicenseError, ModelCard, check_license
from screening.model import PCGModel

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("dataset", ["ZCHSound", "CirCor DigiScope + ZCHSound"])
def test_zchsound_models_are_blocked_in_product_mode(monkeypatch, dataset):
    card = ModelCard(name="m", version="1", task="t", dataset=dataset, weights="x.onnx")
    assert DATASET_LICENSES[dataset][1] is False
    monkeypatch.setenv("CARDIOPATH_MODE", "product")
    with pytest.raises(LicenseError):
        check_license(card)
    monkeypatch.setenv("CARDIOPATH_MODE", "research")
    check_license(card)                                    # tadqiqot rejimida ishlaydi


def test_circor_only_model_stays_product_safe(monkeypatch):
    monkeypatch.setenv("CARDIOPATH_MODE", "product")
    check_license(ModelCard(name="m", version="1", task="t", dataset="CirCor DigiScope", weights="x.onnx"))


def test_rejected_multisite_model_cannot_be_auto_loaded():
    d = ROOT / "weights" / "pcg_multisite"
    assert not (d / "model_card.json").exists()            # karta ataylab model_card.experimental.json deb nomlangan
    assert PCGModel.from_dir(d) is None
    report = (d / "report.md").read_text(encoding="utf-8") if (d / "report.md").exists() else ""
    assert not report or "RAD ETILDI" in report            # hisobot bo'lsa, rad etilgani yozilgan
