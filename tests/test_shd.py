"""AI-EKG tuzilmaviy kasalliklar: faqat mezondan o'tgan yorliqlar, abstain-first, API'ga ulanishi."""
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import LicenseError, ModelCard
from core.store import SqliteEpisodeStore
from ecg.model import ECGModel
from ecg.shd import StructuralFromECG
from tests.test_ai_api import ECG_CARD, ecg_csv
from tests.test_ecg import fake_ecg

LABELS = ["shd", "aortic_stenosis", "mitral_regurgitation", "rv_dysfunction"]
TH = {n: {"low": 0.2, "high": 0.6} for n in LABELS}
CARD = ModelCard(name="shd_test", version="0", task="t", dataset="EchoNext", weights="n",
                 thresholds={"labels": LABELS, "enabled": ["shd", "mitral_regurgitation", "rv_dysfunction"], "per_label": TH})
REAL = Path("weights/ecg_shd")


def model(*p):
    return StructuralFromECG(CARD, lambda x: np.tile(np.array(p, np.float32), (len(x), 1)))


def run(m, age=60):
    return m.analyze(fake_ecg(fs=500), 500, age_years=age)


def test_positive_label_suggests_echo_and_disabled_label_is_hidden():
    ev = run(model(0.1, 0.99, 0.9, 0.1))                 # aorta stenozi mezondan o'tmagan — 0.99 bo'lsa ham ko'rsatilmaydi
    assert not ev.abstained and ev.risk.value == "moderate"
    assert ev.value["positive"] == ["mitral_regurgitation"] and "aortic_stenosis" not in ev.value["probabilities"]
    assert "tashxis emas" in " ".join(ev.explanation)


def test_all_negative_is_low_but_not_a_guarantee():
    ev = run(model(0.05, 0.9, 0.05, 0.05))
    assert ev.risk.value == "low" and "kafolatlamaydi" in " ".join(ev.explanation)


def test_uncertain_child_and_bad_signal_abstain():
    assert run(model(0.4, 0.1, 0.1, 0.1)).abstained                    # noaniq zona
    assert run(model(0.9, 0.9, 0.9, 0.9), age=10).abstained
    assert model(0.9, 0.9, 0.9, 0.9).analyze(fake_ecg(fs=500, seconds=3), 500, age_years=60).abstained


def test_no_enabled_label_or_failed_card_is_not_loaded(tmp_path):
    bad = ModelCard(name="x", version="0", task="t", dataset="EchoNext", weights="n",
                    thresholds={"labels": LABELS, "enabled": [], "per_label": TH})
    with pytest.raises(ValueError):
        StructuralFromECG(bad, lambda x: x)
    (tmp_path / "model_card.json").write_text(json.dumps({"name": "x", "version": "0", "task": "t", "dataset": "EchoNext",
                                                          "weights": "w.onnx", "passed": False}), encoding="utf-8")
    assert StructuralFromECG.from_dir(tmp_path) is None


def test_product_mode_blocks_research_licence(monkeypatch):
    monkeypatch.setenv("CARDIOPATH_MODE", "product")
    with pytest.raises(LicenseError):
        model(0.1, 0.1, 0.1, 0.1)


def test_api_returns_structural_section(tmp_path):
    e = ECGModel(ECG_CARD, lambda x: np.tile(np.array([0.01, 0.9, 0.1, 0.1, 0.1, 0.1], np.float32), (len(x), 1)))
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "a.db")), None, ecg_model=e, shd_model=model(0.1, 0.1, 0.1, 0.95)))
    eid = c.post("/episodes", json={"patient_ref": "S-1", "actor": "dr", "population": "adult"}).json()["id"]
    r = c.post(f"/episodes/{eid}/ecg", data={"actor": "dr", "fs": "100", "age_years": "70"},
               files={"file": ("e.csv", ecg_csv(), "text/csv")})
    assert r.status_code == 200, r.text
    s = r.json()["structural"]
    assert s["evidence"]["kind"] == "ecg.shd" and s["plain"]["level"] == "yellow" and "o'ng qorincha" in s["plain"]["todo"]
    m = c.get("/models").json()
    assert m["ecg_shd_enabled"] == ["shd", "mitral_regurgitation", "rv_dysfunction"]


@pytest.mark.skipif(not (REAL / "model_card.json").exists(), reason="haqiqiy og'irliklar repoda yo'q")
def test_real_card_enables_only_labels_that_passed():
    card = json.loads((REAL / "model_card.json").read_text(encoding="utf-8"))
    per = card["metrics"]["test"]
    for n in card["thresholds"]["enabled"]:
        assert per[n]["passed"] and all(per[n]["checks"].values())
    assert "lvef_le_45" not in card["thresholds"]["enabled"]
    StructuralFromECG.from_dir(REAL).analyze(fake_ecg(fs=500), 500, age_years=55)
