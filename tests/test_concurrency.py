"""Bir bemorni ikki shifokor bir vaqtda o'zgartirsa, hech bir natija jimgina yo'qolmasligi kerak."""
import threading

from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.store import SqliteEpisodeStore
try:
    from core.store import EpisodeConflict
except ImportError:          # tuzatishdan oldin
    class EpisodeConflict(Exception):
        pass


def ev(kind):
    return Evidence(kind=kind, value=1, source=Source.CLINICIAN, provenance=Provenance(name="t"), risk=RiskLevel.LOW)


def test_second_writer_with_stale_copy_gets_conflict_not_silent_loss(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "c.db"))
    ep = Episode(patient_ref="C-1")
    store.save(ep, "dr", "create")
    a, b = store.get(ep.id), store.get(ep.id)          # ikki shifokor bir xil nusxani o'qidi
    a.add(ev("ecg.afib")); store.save(a, "dr_a", "ecg")
    b.add(ev("risk.euroscore2"))
    try:
        store.save(b, "dr_b", "risk")
        raise AssertionError("eskirgan nusxa jimgina yozib yubordi")
    except EpisodeConflict:
        pass
    kinds = [e.kind for e in store.get(ep.id).evidence]
    assert kinds == ["ecg.afib"]                        # A natijasi saqlangan, B ga qayta urinish aytiladi
    assert [x["action"] for x in store.audit(ep.id)] == ["create", "ecg"]   # muvaffaqiyatsiz yozuv jurnalga tushmaydi


def test_same_object_can_be_saved_repeatedly(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "s.db"))
    ep = Episode(patient_ref="C-2")
    store.save(ep, "dr", "create")
    ep.add(ev("a")); store.save(ep, "dr", "a")
    ep.add(ev("b")); store.save(ep, "dr", "b")          # bitta so'rov ichida bir necha marta saqlash (EKG + past EF + SHD)
    assert [e.kind for e in store.get(ep.id).evidence] == ["a", "b"]


def test_parallel_api_writes_never_lose_evidence(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "p.db"))
    c = TestClient(create_app(store, None))
    eid = c.post("/episodes", json={"patient_ref": "C-3", "actor": "dr"}).json()["id"]
    codes, lock = [], threading.Lock()

    def worker(i):
        r = c.post(f"/episodes/{eid}/echo-diagnosis", json={"actor": f"dr{i}", "diagnosis": "VSD"})
        with lock:
            codes.append(r.status_code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    [t.start() for t in threads]; [t.join() for t in threads]
    saved = sum(e["kind"] == "workup.echo_dx" for e in c.get(f"/episodes/{eid}").json()["evidence"])
    assert set(codes) <= {200, 409}
    assert saved == codes.count(200)                    # har bir «muvaffaqiyatli» javob haqiqatan saqlangan
