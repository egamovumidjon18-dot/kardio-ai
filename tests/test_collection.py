"""Mahalliy ma'lumot yig'ish: rozilik → saqlash → ExoKG tashxisi → eksport → moslashtirish o'qiydi."""
import csv
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import ModelCard
from core.store import SqliteEpisodeStore
from screening.model import PCGModel

CARD = ModelCard(name="pcg_test", version="0", task="t", dataset="CirCor DigiScope", weights="none")


@pytest.fixture
def env(tmp_path):
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.1, np.float32), np.zeros(len(x), np.float32)))
    db, rec = tmp_path / "c.db", tmp_path / "recordings"
    client = TestClient(create_app(SqliteEpisodeStore(str(db)), model, recordings_dir=rec))
    return client, db, rec, tmp_path


def screen(client, wav_factory, consent: bool, ref="LOC-1"):
    eid = client.post("/episodes", json={"patient_ref": ref}).json()["id"]
    r = client.post(f"/episodes/{eid}/screening",
                    data={"actor": "dr", "age_days": "900", "research_consent": str(consent).lower(),
                          "device": "TestScope v1"},
                    files=[("recordings", ("MV.wav", wav_factory(seed=1), "audio/wav")),
                           ("recordings", ("AV.wav", wav_factory(seed=2), "audio/wav"))])
    assert r.status_code == 200, r.text
    return eid, r.json()


def test_recordings_saved_only_with_consent(env, wav_factory):
    client, _, rec, _ = env
    eid, body = screen(client, wav_factory, consent=False)
    assert body["saved_for_research"] is False and not (rec / eid).exists()
    eid, body = screen(client, wav_factory, consent=True)
    assert body["saved_for_research"] is True
    assert sorted(p.name for p in (rec / eid).iterdir()) == ["AV.wav", "MV.wav"]
    ev = [e for e in client.get(f"/episodes/{eid}").json()["evidence"] if e["kind"] == "research.recordings"][0]
    assert ev["value"]["device"] == "TestScope v1" and ev["value"]["age_days"] == 900


def test_consent_without_storage_configured_is_rejected(tmp_path, wav_factory):
    client = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "x.db")), None))
    eid = client.post("/episodes", json={"patient_ref": "P"}).json()["id"]
    r = client.post(f"/episodes/{eid}/screening", data={"actor": "dr", "research_consent": "true"},
                    files=[("recordings", ("MV.wav", wav_factory(), "audio/wav"))])
    assert r.status_code == 409


def test_echo_diagnosis_validation(env, wav_factory):
    client, *_ = env
    eid, _ = screen(client, wav_factory, consent=False)
    assert client.post(f"/episodes/{eid}/echo-diagnosis", json={"actor": "dr", "diagnosis": "xyz"}).status_code == 422
    r = client.post(f"/episodes/{eid}/echo-diagnosis", json={"actor": "dr", "diagnosis": "vsd", "notes": "perimembranoz"})
    assert r.status_code == 200 and r.json()["value"] == "VSD"


def test_export_and_adaptation_reader_keep_child_together(env, wav_factory, monkeypatch):
    client, db, rec, tmp = env
    eid_a, _ = screen(client, wav_factory, consent=True, ref="A")
    eid_b, _ = screen(client, wav_factory, consent=True, ref="B")
    screen(client, wav_factory, consent=True, ref="C-no-echo")              # tashxissiz — eksportga kirmaydi
    client.post(f"/episodes/{eid_a}/echo-diagnosis", json={"actor": "dr", "diagnosis": "VSD"})
    client.post(f"/episodes/{eid_b}/echo-diagnosis", json={"actor": "dr", "diagnosis": "NORMAL"})

    from research import export_local
    out = tmp / "export"
    monkeypatch.setattr(sys, "argv", ["x", "--db", str(db), "--recordings", str(rec), "--out", str(out)])
    export_local.main()
    rows = list(csv.DictReader(open(out / "Clean Heartsound Data Details.csv", encoding="utf-8")))
    assert len(rows) == 4 and {r["subject"] for r in rows} == {eid_a, eid_b}
    assert {r["diagnosis"] for r in rows if r["subject"] == eid_a} == {"VSD"}

    pytest.importorskip("torch")
    from research.adapt_zchsound import by_subject, load_items, stratified_split
    subjects = by_subject(load_items(out))
    assert sorted(len(g) for g in subjects) == [2, 2]
    test, pool = stratified_split(subjects, 0.5, seed=0)
    assert all(len(g) == 2 for g in test + pool)                           # bola bo'linmaydi
