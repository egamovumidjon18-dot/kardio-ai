"""Sintetik ma'lumotda o'qitilgan modellar klinik dasturga hech qachon yuklanmasligi kerak."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import DATASET_LICENSES, SYNTHETIC_DATASET, ModelCard
from core.store import SqliteEpisodeStore
from cxr.model import CXRModel
from guardian.wound_cv import WoundImageModel
from risk.aki import AKIModel

LOADERS = {"aki": AKIModel, "wound": WoundImageModel, "cxr": CXRModel}


@pytest.mark.parametrize("d", sorted(LOADERS))
def test_synthetic_weights_are_not_loaded(d):
    card = json.loads(Path(f"weights/{d}/model_card.json").read_text(encoding="utf-8"))
    assert card["dataset"] == SYNTHETIC_DATASET
    assert card["metrics"] == {}, "haqiqiy bemorda o'lchanmagan ko'rsatkich kartada bo'lmasligi kerak"
    assert card["validation"]["clinical_use"] is False
    assert LOADERS[d].from_dir(f"weights/{d}") is None


def test_synthetic_card_flags():
    c = ModelCard(name="x", version="1", task="t", dataset=SYNTHETIC_DATASET, weights="x.onnx")
    assert c.synthetic and not c.commercial_use and c.to_dict()["synthetic"] is True


def test_no_fake_open_licences():
    assert "MIMIC-IV + Cleveland Clinic Priors" not in DATASET_LICENSES
    assert "CardioPath SternoWound-CV + SurgWound Priors" not in DATASET_LICENSES
    assert DATASET_LICENSES["CheXpert / NIH ChestX-ray14"][1] is False
    assert DATASET_LICENSES["MIMIC-IV"][1] is False


def test_models_endpoint_blocks_synthetic(tmp_path):
    app = create_app(SqliteEpisodeStore(str(tmp_path / "t.db")), pcg=None,
                     aki_model=AKIModel.from_dir("weights/aki"),
                     wound_model=WoundImageModel.from_dir("weights/wound"),
                     cxr_model=CXRModel.from_dir("weights/cxr"))
    data = TestClient(app).get("/models").json()
    assert data["csa_aki_ml"] is None and data["wound_image_cv"] is None and data["cxr"] is None
    for k in ("csa_aki_ml", "wound_image_cv", "cxr"):
        assert "SINTETIK" in data["blocked"][k]
