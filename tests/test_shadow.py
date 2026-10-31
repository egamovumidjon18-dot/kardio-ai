"""Shadow mode: javob hech qayerga chiqmaydi, xato asosiy yo'lni buzmaydi, yorliq ro'yxati ko'r, hisobot to'g'ri sanaydi."""
import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import ModelCard
from core.shadow import MIN_AFIB, ShadowRhythmModel, ShadowStore
from core.store import SqliteEpisodeStore
from ecg.model import ECGModel
from tests.test_ai_api import ECG_CARD, ecg_csv
from tests.test_ecg import fake_ecg

CLASSES = ["SR", "SBRAD", "STACH", "AFIB", "AFL", "SVT"]
REAL = Path(__file__).resolve().parents[1] / "weights" / "ecg_afib_multi2"


def shadow_model(top="AFL", name="sh"):
    card = ModelCard(name=name, version="1", task="t", dataset="Chapman-Shaoxing", weights="n",
                     thresholds={"classes": CLASSES, "afib_threshold": 0.5})
    lg = np.full(6, -3.0, np.float32); lg[CLASSES.index(top)] = 3.0
    return ShadowRhythmModel(card, lambda x: np.tile(lg, (len(x), 1)))


def broken_model():
    def boom(x):
        raise RuntimeError("buzildi")
    card = ModelCard(name="broken", version="1", task="t", dataset="Chapman-Shaoxing", weights="n",
                     thresholds={"classes": CLASSES, "afib_threshold": 0.5})
    return ShadowRhythmModel(card, boom)


def client(tmp_path, models, live_afib=0.95):
    e = ECGModel(ECG_CARD, lambda x: np.tile(np.array([live_afib, 0.01, 0.1, 0.1, 0.1, 0.1], np.float32), (len(x), 1)))
    db = str(tmp_path / "a.db")
    store = ShadowStore(db)
    return TestClient(create_app(SqliteEpisodeStore(db), None, ecg_model=e, shadow_models=models, shadow_store=store)), store


def upload(c):
    eid = c.post("/episodes", json={"patient_ref": "SH-1", "actor": "dr", "population": "adult"}).json()["id"]
    r = c.post(f"/episodes/{eid}/ecg", data={"actor": "dr", "fs": "100", "age_years": "60"},
               files={"file": ("e.csv", ecg_csv(), "text/csv")})
    assert r.status_code == 200, r.text
    return eid, r


def test_shadow_output_never_reaches_response_episode_or_pending_list(tmp_path):
    c, store = client(tmp_path, [shadow_model("AFL")])
    eid, r = upload(c)
    body = json.dumps(r.json()) + json.dumps(c.get(f"/episodes/{eid}").json()) + json.dumps(c.get(f"/episodes/{eid}/digest").json())
    assert "shadow" not in body and "sh@1" not in body and "AFL" not in body
    pend = c.get("/shadow/pending").json()["items"]
    assert len(pend) == 1 and set(pend[0]) == {"run_id", "episode_id", "created_at"}     # model javobi yo'q


def test_broken_shadow_model_does_not_break_live_path(tmp_path):
    c, store = client(tmp_path, [broken_model(), shadow_model("SR", name="ok")])
    _, r = upload(c)
    assert r.json()["evidence"]["risk"] == "high"
    assert store.report()["runs"] == 1


def test_label_validation_and_report_counts(tmp_path):
    c, store = client(tmp_path, [shadow_model("AFL")])
    upload(c); upload(c)
    runs = [p["run_id"] for p in c.get("/shadow/pending").json()["items"]]
    assert c.post(f"/shadow/{runs[0]}/label", json={"actor": "dr", "rhythm": "XYZ"}).status_code == 422
    assert c.post("/shadow/999/label", json={"actor": "dr", "rhythm": "SR"}).status_code == 404
    assert c.post(f"/shadow/{runs[0]}/label", json={"actor": "dr", "rhythm": "AFL"}).status_code == 200
    assert c.post(f"/shadow/{runs[1]}/label", json={"actor": "dr", "rhythm": "AFIB"}).status_code == 200
    assert c.get("/shadow/pending").json()["items"] == []
    rep = c.get("/shadow/report").json()
    m = rep["models"]["sh@1"]
    # ulangan model ikkalasini AFIB dedi; shadow model ikkalasini titrash dedi
    assert m["live_model"]["sensitivity"] == 1.0 and m["live_model"]["fast_called_afib"] == 1.0
    assert m["shadow_model"]["sensitivity"] == 0.0 and m["shadow_model"]["fast_called_afib"] == 0.0
    assert m["rhythm_agreement"] == 0.5 and m["ready"] is False and rep["min_required"]["afib"] == MIN_AFIB


def test_live_abstain_and_other_label_are_excluded_from_report(tmp_path):
    c, store = client(tmp_path, [shadow_model("SR")], live_afib=0.5)     # noaniq zona → abstain
    upload(c)
    rid = c.get("/shadow/pending").json()["items"][0]["run_id"]
    c.post(f"/shadow/{rid}/label", json={"actor": "dr", "rhythm": "SR"})
    assert store.report()["models"] == {}


def test_shadow_disabled_by_default_routes_absent(tmp_path):
    e = ECGModel(ECG_CARD, lambda x: np.tile(np.array([0.95, 0.01, 0.1, 0.1, 0.1, 0.1], np.float32), (len(x), 1)))
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "a.db")), None, ecg_model=e))
    assert c.get("/shadow/report").status_code == 404


def test_bad_signal_is_recorded_as_abstained():
    m = shadow_model("SR")
    assert "abstained" in m.run(np.zeros((12, 1000), np.float32), 100, ("I", "II", "III", "AVR", "AVL", "AVF",
                                                                        "V1", "V2", "V3", "V4", "V5", "V6"))


def test_real_multisource_model_loads_as_shadow_only():
    if not (REAL / "ecg_afib_multi2.onnx").exists():
        return
    card = json.loads((REAL / "model_card.json").read_text(encoding="utf-8"))
    assert card["passed"] is False                      # ulanmagan — faqat shadow
    m = ShadowRhythmModel.from_dir(REAL)
    out = m.run(fake_ecg(fs=500), 500, ("I", "II", "III", "AVR", "AVL", "AVF", "V1", "V2", "V3", "V4", "V5", "V6"))
    assert out.get("top") in CLASSES or "abstained" in out
