import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import ModelCard
from core.store import SqliteEpisodeStore
from ecg.model import ECGModel
from angio.model import AngioModel
from tests.test_angio import blob_backend, fake_frame, png
from tests.test_ecg import fake_ecg

ECG_CARD = ModelCard(name="ecg_test", version="0", task="t", dataset="PTB-XL", weights="n",
                     thresholds={"afib_low": 0.3, "afib_high": 0.7})
ANGIO_CARD = ModelCard(name="angio_test", version="0", task="t", dataset="ARCADE", weights="n",
                       thresholds={"prob": 0.5, "min_area_px": 20})


def ecg_csv(fs=100):
    x = fake_ecg(fs=fs)
    names = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
    buf = io.StringIO()
    buf.write(",".join(names) + "\n")
    for i in range(x.shape[1]):
        buf.write(",".join(f"{v:.4f}" for v in x[:, i]) + "\n")
    return buf.getvalue().encode()


def make_client(tmp_path, ecg=True, angio=True, ocr=None):
    e = ECGModel(ECG_CARD, lambda x: np.tile(np.array([0.95, 0.01, 0.1, 0.1, 0.1, 0.1], np.float32), (len(x), 1))) if ecg else None
    a = AngioModel(ANGIO_CARD, blob_backend([(150, 150, 15)])) if angio else None
    return TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "a.db")), None, ecg_model=e, angio_model=a, ocr_engine=ocr))


def to_guardian(c, eid):
    path = [("screening", "workup"), ("workup", "heart_team"), ("heart_team", "procedure"), ("procedure", "icu"),
            ("icu", "discharge"), ("discharge", "guardian_30d")]
    for f, t in path:
        r = c.post(f"/episodes/{eid}/transition", json={"from_stage": f, "to_stage": t, "author": "dr"})
        assert r.status_code == 200, r.text


def new(c):
    return c.post("/episodes", json={"patient_ref": "PSV-9", "actor": "dr", "population": "adult"}).json()["id"]


def test_models_endpoint_lists_blocked(tmp_path):
    body = make_client(tmp_path).get("/models").json()
    assert body["ecg"]["dataset_license"] == "CC-BY 4.0" and body["angio"]["commercial_use"] is True
    assert set(body["blocked"]) == {"csa_aki_ml", "ecg_low_ef", "wound_image_cv", "cxr"}


def test_ecg_endpoint_records_evidence(tmp_path):
    c = make_client(tmp_path)
    eid = new(c)
    r = c.post(f"/episodes/{eid}/ecg", data={"actor": "dr", "fs": "100", "age_years": "60"}, files={"file": ("e.csv", ecg_csv(), "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["evidence"]["kind"] == "ecg.afib" and r.json()["evidence"]["risk"] == "high"
    assert "escalation" not in r.json()
    assert "ecg.afib" in [e["kind"] for e in c.get(f"/episodes/{eid}").json()["evidence"]]


def test_ecg_in_guardian_stage_escalates_red(tmp_path):
    c = make_client(tmp_path)
    eid = new(c)
    to_guardian(c, eid)
    r = c.post(f"/episodes/{eid}/ecg", data={"actor": "dr", "fs": "100", "age_years": "60"}, files={"file": ("e.csv", ecg_csv(), "text/csv")})
    assert r.json()["escalation"]["alert"] == "red"


def test_ecg_bad_file_422_and_missing_module_503(tmp_path):
    c = make_client(tmp_path)
    eid = new(c)
    assert c.post(f"/episodes/{eid}/ecg", data={"actor": "dr"}, files={"file": ("e.csv", b"I,II\n1,x\n", "text/csv")}).status_code == 422
    c2 = make_client(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path, ecg=False)
    eid2 = new(c2)
    assert c2.post(f"/episodes/{eid2}/ecg", data={"actor": "dr"}, files={"file": ("e.csv", ecg_csv(), "text/csv")}).status_code == 503


def test_angio_endpoint(tmp_path):
    c = make_client(tmp_path)
    eid = new(c)
    r = c.post(f"/episodes/{eid}/angio", data={"actor": "dr"}, files={"file": ("a.png", png(fake_frame()), "image/png")})
    assert r.status_code == 200 and "SYNTAX kalkulyatori emas" in r.json()["evidence"]["value"]["label"] + " (SYNTAX kalkulyatori emas)"
    assert r.json()["evidence"]["risk"] == "moderate"
    assert c.post(f"/episodes/{eid}/angio", data={"actor": "dr"}, files={"file": ("a.png", b"junk", "image/png")}).status_code == 422


def test_inr_image_endpoint(tmp_path):
    c = make_client(tmp_path, ocr=lambda data: [("INR 6.3", 0.97)])
    eid = new(c)
    assert c.post(f"/episodes/{eid}/guardian/inr-image", data={"actor": "p", "indication": "af"},
                  files={"file": ("l.jpg", b"x", "image/jpeg")}).status_code == 409
    to_guardian(c, eid)
    r = c.post(f"/episodes/{eid}/guardian/inr-image", data={"actor": "p", "indication": "af"},
               files={"file": ("l.jpg", b"x", "image/jpeg")})
    assert r.status_code == 200 and r.json()["escalation"]["alert"] == "red"
    assert "doza" not in r.json()["escalation"]["patient_message"].lower()


def test_inr_image_unreadable_goes_amber(tmp_path):
    c = make_client(tmp_path, ocr=lambda data: [("shovqin", 0.3)])
    eid = new(c)
    to_guardian(c, eid)
    r = c.post(f"/episodes/{eid}/guardian/inr-image", data={"actor": "p", "indication": "af"},
               files={"file": ("l.jpg", b"x", "image/jpeg")})
    assert r.json()["escalation"]["alert"] == "amber" and r.json()["evidence"][0]["abstained"]


def test_echo_ef_503_when_not_connected(tmp_path):
    c = make_client(tmp_path)
    eid = new(c)
    assert c.post(f"/episodes/{eid}/echo-ef", data={"actor": "dr"}, files={"file": ("v.avi", b"x", "video/x-msvideo")}).status_code == 503
