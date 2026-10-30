"""Bemorlar (epizodlar) ro'yxati: tartib, filtr, qidiruv, sahifalash va xavfsizlik."""
import time

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode
from core.store import SqliteEpisodeStore


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "list.db")), None))


def make(client, ref, spo2=None):
    eid = client.post("/episodes", json={"patient_ref": ref, "actor": "dr"}).json()["id"]
    if spo2:
        client.post(f"/episodes/{eid}/screening", data={"actor": "dr", "right_hand_spo2": str(spo2[0]), "foot_spo2": str(spo2[1])})
    return eid


def test_empty_list(client):
    assert client.get("/episodes").json() == {"total": 0, "limit": 50, "offset": 0, "items": []}


def test_newest_first_and_summary_fields(client):
    a = make(client, "SAM-001")
    time.sleep(0.01)
    b = make(client, "SAM-002", spo2=(85, 95))             # CCHD FAIL → very_high
    body = client.get("/episodes").json()
    assert body["total"] == 2 and [i["id"] for i in body["items"]] == [b, a]
    top = body["items"][0]
    assert top["patient_ref"] == "SAM-002" and top["stage"] == "screening" and top["population"] == "pediatric"
    assert top["screening_risk"] == "very_high" and top["n_evidence"] >= 3 and top["n_handoffs"] == 0
    assert body["items"][1]["screening_risk"] is None       # skrining hali o'tkazilmagan
    assert "evidence" not in top                            # ro'yxatda to'liq hujjat yo'q


def test_activity_moves_episode_to_top(client):
    a = make(client, "OLD")
    time.sleep(0.01)
    make(client, "NEW")
    time.sleep(0.01)
    client.post(f"/episodes/{a}/echo-diagnosis", json={"actor": "dr", "diagnosis": "NORMAL"})
    assert client.get("/episodes").json()["items"][0]["id"] == a


def test_stage_filter(client):
    a, b = make(client, "A-1"), make(client, "B-1")
    client.post(f"/episodes/{a}/transition", json={"from_stage": "screening", "to_stage": "workup", "author": "dr"})
    assert [i["id"] for i in client.get("/episodes", params={"stage": "workup"}).json()["items"]] == [a]
    assert [i["id"] for i in client.get("/episodes", params={"stage": "screening"}).json()["items"]] == [b]
    assert client.get("/episodes", params={"stage": "closed"}).json()["total"] == 0
    assert client.get("/episodes", params={"stage": "mars"}).status_code == 422


def test_search_is_case_insensitive_and_literal(client):
    make(client, "SAM-001"); make(client, "sam-002"); make(client, "XYZ_100"); make(client, "ABC-100")
    refs = lambda q: sorted(i["patient_ref"] for i in client.get("/episodes", params={"q": q}).json()["items"])
    assert refs("sam") == ["SAM-001", "sam-002"]
    assert refs("-100") == ["ABC-100"]
    assert refs("_100") == ["XYZ_100"]            # "_" LIKE belgisi emas, oddiy belgi
    assert refs("%") == [] and refs("\\") == []   # maxsus belgilar hammasini qaytarmaydi
    assert refs("yo'q") == []
    assert client.get("/episodes", params={"q": "x" * 65}).status_code == 422


def test_search_cannot_inject_sql(client):
    make(client, "SAM-001")
    r = client.get("/episodes", params={"q": "' OR 1=1 --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/episodes").json()["total"] == 1       # jadval butun


def test_pagination(client):
    ids = [make(client, f"P-{i:02d}") for i in range(5)]
    first = client.get("/episodes", params={"limit": 2}).json()
    rest = client.get("/episodes", params={"limit": 2, "offset": 2}).json()
    last = client.get("/episodes", params={"limit": 2, "offset": 4}).json()
    assert first["total"] == rest["total"] == last["total"] == 5
    got = [i["id"] for i in first["items"] + rest["items"] + last["items"]]
    assert sorted(got) == sorted(ids) and len(set(got)) == 5       # takrorsiz va to'liq
    assert client.get("/episodes", params={"limit": 0}).status_code == 422
    assert client.get("/episodes", params={"limit": 201}).status_code == 422
    assert client.get("/episodes", params={"offset": -1}).status_code == 422


def test_store_summaries_direct(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "s.db"))
    ep = Episode(patient_ref="DIRECT")
    store.save(ep, "t", "create")
    total, rows = store.summaries(q="direct")
    assert total == 1 and rows[0]["patient_ref"] == "DIRECT" and rows[0]["updated_at"]
