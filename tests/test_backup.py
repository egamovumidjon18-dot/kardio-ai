"""Bazaning zaxira nusxasi: izchil, tekshirilgan, eski nusxalar o'chadi, tiklashda avvalgi baza saqlanadi."""
import sqlite3
import time

from fastapi.testclient import TestClient

from api.main import create_app
from core.backup import create_backup, list_backups, restore_backup
from core.store import SqliteEpisodeStore


def test_backup_contains_data_and_retention(tmp_path):
    db = str(tmp_path / "live.db")
    store = SqliteEpisodeStore(db)
    c = TestClient(create_app(store, None))
    eid = c.post("/episodes", json={"patient_ref": "B-1", "actor": "dr"}).json()["id"]
    paths = []
    for _ in range(4):
        paths.append(create_backup(db, tmp_path / "bk", keep=3)); time.sleep(0.02)
    items = list_backups(tmp_path / "bk")
    assert len(items) == 3 and items[0]["name"] == paths[-1].name           # eng yangisi birinchi, 4-chi o'chirildi
    assert SqliteEpisodeStore(str(paths[-1])).get(eid).patient_ref == "B-1"
    assert not list((tmp_path / "bk").glob("*.tmp"))


def test_restore_keeps_previous_database(tmp_path):
    db = tmp_path / "live.db"
    store = SqliteEpisodeStore(str(db))
    TestClient(create_app(store, None)).post("/episodes", json={"patient_ref": "B-2", "actor": "dr"})
    snap = create_backup(db, tmp_path / "bk")
    TestClient(create_app(store, None)).post("/episodes", json={"patient_ref": "B-3", "actor": "dr"})
    del store
    kept = restore_backup(snap, db)
    refs = {r[0] for r in sqlite3.connect(str(db)).execute("SELECT json_extract(doc, '$.patient_ref') FROM episodes")}
    assert refs == {"B-2"} and kept.exists()                               # B-3 tiklashdan oldingi faylda saqlangan
    assert {r[0] for r in sqlite3.connect(str(kept)).execute("SELECT json_extract(doc, '$.patient_ref') FROM episodes")} == {"B-2", "B-3"}


def test_corrupt_backup_is_refused(tmp_path):
    bad = tmp_path / "cardiopath-bad.db"; bad.write_bytes(b"not a database" * 100)
    db = tmp_path / "live.db"; SqliteEpisodeStore(str(db))
    try:
        restore_backup(bad, db)
        raise AssertionError("buzilgan nusxa tiklandi")
    except Exception as exc:
        assert "AssertionError" not in type(exc).__name__


def test_api_backup_now_and_list(tmp_path):
    db = str(tmp_path / "a.db")
    c = TestClient(create_app(SqliteEpisodeStore(db), None, backup_db=db, backup_dir=tmp_path / "bk", backup_every_h=0))
    r = c.post("/backups")
    assert r.status_code == 201 and r.json()["name"].startswith("cardiopath-")
    assert len(c.get("/backups").json()["items"]) == 1


def test_restore_missing_backup_raises_and_does_not_replace(tmp_path):
    db = tmp_path / "live.db"
    SqliteEpisodeStore(str(db))
    non_existent = tmp_path / "does_not_exist.db"
    import pytest
    with pytest.raises(FileNotFoundError):
        restore_backup(non_existent, db)
    # Target database must remain intact and non_existent must not be created
    assert db.exists() and not non_existent.exists()


def test_restore_empty_sqlite_db_rejected(tmp_path):
    db = tmp_path / "live.db"
    store = SqliteEpisodeStore(str(db))
    store.save(store.get(store.ids()[0]) if store.ids() else None or __import__("core.episode", fromlist=["Episode"]).Episode("P1"), "dr", "init")
    empty_db = tmp_path / "empty.db"
    sqlite3.connect(str(empty_db)).close()
    import pytest
    with pytest.raises(ValueError, match="kerakli jadvallar yo'q"):
        restore_backup(empty_db, db)


def test_create_backup_missing_db_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        create_backup(tmp_path / "nonexistent.db", tmp_path / "bk")
