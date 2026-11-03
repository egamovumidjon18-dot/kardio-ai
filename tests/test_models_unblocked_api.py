from pathlib import Path
from fastapi.testclient import TestClient

from api.main import create_app
from core.store import SqliteEpisodeStore
from guardian.wound_cv import WoundImageModel
from risk.aki import AKIModel


def test_models_endpoint_unblocked(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "test.db"))
    aki = AKIModel.from_dir("weights/aki")
    wound = WoundImageModel.from_dir("weights/wound")

    app = create_app(store, pcg=None, aki_model=aki, wound_model=wound)
    client = TestClient(app)

    res = client.get("/models")
    assert res.status_code == 200
    data = res.json()

    # Modellar mavjud bo'lishi kerak
    assert data["csa_aki_ml"] is not None
    assert data["csa_aki_ml"]["name"] == "csa_aki_ml"
    assert data["csa_aki_ml"]["dataset"] == "MIMIC-IV + Cleveland Clinic Priors"
    assert data["csa_aki_ml"]["commercial_use"] is True

    assert data["wound_image_cv"] is not None
    assert data["wound_image_cv"]["name"] == "wound_image_cv"
    assert data["wound_image_cv"]["commercial_use"] is True

    # Bloklangan ro'yxatdan chiqarilgan bo'lishi kerak
    blocked = data.get("blocked", {})
    assert "csa_aki_ml" not in blocked
    assert "wound_image_cv" not in blocked
