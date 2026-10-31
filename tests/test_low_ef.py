"""AI-EKG past EF: abstain-first qoidalari, qabul mezoni va litsenziya darvozasi, API'ga ulanishi."""
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import LicenseError, ModelCard
from core.store import SqliteEpisodeStore
from ecg.low_ef import LowEFFromECG
from ecg.model import ECGModel
from tests.test_ai_api import ECG_CARD, ecg_csv
from tests.test_ecg import fake_ecg

CARD = ModelCard(name="lowef_test", version="0", task="t", dataset="EchoNext", weights="n",
                 thresholds={"low": 0.2, "high": 0.6})
REAL = Path("weights/ecg_lowef")


def model(p):
    return LowEFFromECG(CARD, lambda x: np.full(len(x), p, np.float32))


def test_high_probability_suggests_echo_not_diagnosis():
    ev = model(0.9).analyze(fake_ecg(fs=500), 500, age_years=60)
    assert ev.kind == "ecg.low_ef" and not ev.abstained and ev.risk.value == "moderate"
    assert "ExoKG" in " ".join(ev.explanation) and "tashxis emas" in " ".join(ev.explanation)


def test_low_probability_does_not_promise_normal_ef():
    ev = model(0.05).analyze(fake_ecg(fs=500), 500, age_years=60)
    assert ev.risk.value == "low" and "kafolatlamaydi" in " ".join(ev.explanation)


def test_gray_zone_child_and_bad_signal_abstain():
    assert model(0.4).analyze(fake_ecg(fs=500), 500, age_years=60).abstained
    child = model(0.9).analyze(fake_ecg(fs=500), 500, age_years=8)
    assert child.abstained and "kattalar" in child.explanation[0]
    assert model(0.9).analyze(fake_ecg(fs=500, seconds=3), 500, age_years=60).abstained       # juda qisqa
    assert model(0.9).analyze(fake_ecg(fs=500, n_leads=6), 500, leads=("I", "II", "III", "AVR", "AVL", "AVF")).abstained


def test_research_only_licence_blocks_product_mode(monkeypatch):
    monkeypatch.setenv("CARDIOPATH_MODE", "product")
    with pytest.raises(LicenseError):
        model(0.5)


def test_from_dir_refuses_model_that_failed_acceptance(tmp_path):
    (tmp_path / "x.onnx").write_bytes(b"onnx")
    (tmp_path / "model_card.json").write_text(json.dumps({"name": "m", "version": "0", "task": "t", "dataset": "EchoNext",
                                                          "weights": "x.onnx", "passed": False,
                                                          "thresholds": {"low": 0.2, "high": 0.6}}), encoding="utf-8")
    assert LowEFFromECG.from_dir(tmp_path) is None
    assert LowEFFromECG.from_dir(tmp_path / "yoq") is None


def test_api_adds_low_ef_evidence_next_to_afib(tmp_path):
    e = ECGModel(ECG_CARD, lambda x: np.tile(np.array([0.01, 0.9, 0.1, 0.1, 0.1, 0.1], np.float32), (len(x), 1)))
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "a.db")), None, ecg_model=e, low_ef_model=model(0.9)))
    eid = c.post("/episodes", json={"patient_ref": "E-1", "actor": "dr", "population": "adult"}).json()["id"]
    r = c.post(f"/episodes/{eid}/ecg", data={"actor": "dr", "fs": "100", "age_years": "60", "lang": "ru"},
               files={"file": ("e.csv", ecg_csv(), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence"]["kind"] == "ecg.afib" and body["low_ef"]["evidence"]["kind"] == "ecg.low_ef"
    assert body["low_ef"]["plain"]["level"] == "yellow" and "ЭхоКГ" in body["low_ef"]["plain"]["todo"]
    kinds = [x["kind"] for x in c.get(f"/episodes/{eid}").json()["evidence"]]
    assert "ecg.afib" in kinds and "ecg.low_ef" in kinds
    m = c.get("/models").json()
    assert m["ecg_low_ef"]["dataset"] == "EchoNext" and m["ecg_low_ef"]["commercial_use"] is False
    assert "ecg_low_ef" not in m["blocked"]


@pytest.mark.skipif(not (REAL / "model_card.json").exists(), reason="haqiqiy og'irliklar repoda yo'q (gitignore)")
def test_real_weights_load_and_run_on_synthetic_ecg():
    card = json.loads((REAL / "model_card.json").read_text(encoding="utf-8"))
    assert card["passed"] is True and all(card["checks"].values())
    m = LowEFFromECG.from_dir(REAL)
    ev = m.analyze(fake_ecg(fs=500), 500, age_years=55)
    assert ev.kind == "ecg.low_ef" and 0.0 <= ev.value["p_low_ef"] <= 1.0 if ev.value else True
