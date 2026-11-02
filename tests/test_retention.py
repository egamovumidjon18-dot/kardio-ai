"""Tibbiy ma'lumotlar arxivi va saqlash muddati testlari (ISO 27799)."""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode, Handoff, Stage
from core.retention import archive_closed_episodes
from core.store import SqliteEpisodeStore


def test_archive_closed_episodes_selection(tmp_path):
    db_path = str(tmp_path / "retention_test.db")
    store = SqliteEpisodeStore(db_path)

    # 1. Faol (ochiq) epizod
    ep_active = Episode(patient_ref="P-ACTIVE", stage=Stage.WORKUP)
    store.save(ep_active, "dr", "init")

    # 2. Yaqinda yopilgan epizod (5 kun oldin)
    ep_recent = Episode(patient_ref="P-RECENT", stage=Stage.CLOSED)
    t_recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    ep_recent.handoffs.append(Handoff(from_stage="guardian_30d", to_stage="closed", author="dr", created_at=t_recent))
    store.save(ep_recent, "dr", "close")

    # 3. Ancha oldin yopilgan epizod (45 kun oldin)
    ep_old = Episode(patient_ref="P-OLD", stage=Stage.CLOSED)
    t_old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    ep_old.handoffs.append(Handoff(from_stage="guardian_30d", to_stage="closed", author="dr", created_at=t_old))
    store.save(ep_old, "dr", "close")

    # Arxivlash: 30 kundan eski yopilgan epizodlar
    archived = archive_closed_episodes(store, actor="admin", older_than_days=30)
    assert ep_old.id in archived
    assert ep_recent.id not in archived
    assert ep_active.id not in archived


def test_archive_api_endpoint(tmp_path):
    db_path = str(tmp_path / "retention_api.db")
    store = SqliteEpisodeStore(db_path)
    client = TestClient(create_app(store, None))

    # Oldin yopilgan epizod
    ep = Episode(patient_ref="P-OLD-API", stage=Stage.CLOSED)
    t_old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    ep.handoffs.append(Handoff(from_stage="guardian_30d", to_stage="closed", author="dr", created_at=t_old))
    store.save(ep, "dr", "close")

    r = client.post("/episodes/archive", json={"actor": "admin", "older_than_days": 30})
    assert r.status_code == 200
    data = r.json()
    assert data["archived_count"] == 1
    assert ep.id in data["episode_ids"]
