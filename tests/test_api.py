import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import ModelCard
from core.store import SqliteEpisodeStore
from screening.model import PCGModel

CARD = ModelCard(name="pcg_test", version="0", task="t", dataset="CirCor DigiScope", weights="none")


@pytest.fixture
def client(tmp_path):
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.9, np.float32), np.full(len(x), 0.1, np.float32)))
    return TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "api.db")), model))


def new_episode(client):
    r = client.post("/episodes", json={"patient_ref": "PSV-001", "actor": "dr.a"})
    assert r.status_code == 201
    return r.json()["id"]


def test_full_screening_flow_with_pcg_and_handoff(client, wav_factory):
    eid = new_episode(client)
    r = client.post(f"/episodes/{eid}/screening",
                    data={"actor": "dr.a", "right_hand_spo2": "98", "foot_spo2": "97", "red_flags": ""},
                    files=[("recordings", ("1234_MV.wav", wav_factory(), "audio/wav")),
                           ("recordings", ("1234_AV_1.wav", wav_factory(seed=2), "audio/wav"))])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["final_risk"] == "moderate"
    assert body["concordance"]["status"] == "disagree"           # qoida LOW, AI MODERATE
    assert body["concordance"]["needs_discussion"] is True
    assert "YAKUNIY TASHXIS EMAS" in body["disclaimer"]

    r = client.post(f"/episodes/{eid}/transition", json={
        "from_stage": "screening", "to_stage": "workup", "author": "dr.a",
        "evidence_ids": body["evidence_ids"], "open_questions": ["ExoKG: DMJP?"]})
    assert r.status_code == 200 and r.json()["stage"] == "workup"

    r = client.post(f"/episodes/{eid}/screening", data={"actor": "dr.a"})
    assert r.status_code == 409

    actions = [a["action"] for a in client.get(f"/episodes/{eid}/audit").json()]
    assert actions == ["episode.create", "screening.triage", "episode.transition"]
    kinds = [e["kind"] for e in client.get(f"/episodes/{eid}").json()["evidence"]]
    assert kinds == ["screening.cchd", "screening.red_flags", "screening.rule", "screening.pcg", "screening.triage"]


def test_newborn_audio_goes_to_rules_only(client, wav_factory):
    eid = new_episode(client)
    r = client.post(f"/episodes/{eid}/screening",
                    data={"actor": "dr", "right_hand_spo2": "98", "foot_spo2": "98", "age_hours": "30"},
                    files=[("recordings", ("MV.wav", wav_factory(), "audio/wav"))]).json()
    assert r["concordance"]["status"] == "ai_abstained" and r["final_risk"] == "low"


def test_cchd_fail_without_audio(client):
    eid = new_episode(client)
    r = client.post(f"/episodes/{eid}/screening",
                    data={"actor": "dr.a", "right_hand_spo2": "88", "foot_spo2": "95"})
    assert r.json()["final_risk"] == "very_high"


def test_validation_errors(client, wav_factory):
    eid = new_episode(client)
    assert client.post(f"/episodes/{eid}/screening",
                       data={"actor": "x", "right_hand_spo2": "98"}).status_code == 422
    assert client.post(f"/episodes/{eid}/screening", data={"actor": "x"},
                       files=[("recordings", ("heart.wav", wav_factory(), "audio/wav"))]).status_code == 422
    assert client.post(f"/episodes/{eid}/screening", data={"actor": "x"},
                       files=[("recordings", ("MV.wav", b"not a wav", "audio/wav"))]).status_code == 422
    assert client.post(f"/episodes/{eid}/transition", json={
        "from_stage": "screening", "to_stage": "procedure", "author": "x"}).status_code == 409
    assert client.get("/episodes/missing").status_code == 404


def test_no_model_warns(tmp_path, wav_factory):
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "n.db")), None))
    eid = c.post("/episodes", json={"patient_ref": "P"}).json()["id"]
    r = c.post(f"/episodes/{eid}/screening", data={"actor": "x"},
               files=[("recordings", ("MV.wav", wav_factory(), "audio/wav"))])
    assert r.json()["concordance"]["status"] == "rule_only" and "warning" in r.json()
