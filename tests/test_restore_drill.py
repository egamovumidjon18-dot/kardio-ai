"""Avtomatik zaxira nusxa tiklash mashqi testlari (ISO 13485 / ISO 27001)."""
import os
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import create_app
from core import backup as backup_mod
from core.restore_drill import run_restore_drill
from core.store import SqliteEpisodeStore


def test_restore_drill_empty_dir(tmp_path):
    empty_dir = tmp_path / "empty_backups"
    empty_dir.mkdir()
    rep = run_restore_drill(empty_dir)
    assert not rep.success
    assert "topilmadi" in rep.error or "mavjud emas" in rep.error


def test_restore_drill_nonexistent_dir(tmp_path):
    rep = run_restore_drill(tmp_path / "does_not_exist")
    assert not rep.success
    assert "topilmadi" in rep.error


def test_restore_drill_successful_uncompressed(tmp_path):
    db_path = str(tmp_path / "orig.db")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = SqliteEpisodeStore(db_path)
    # Bir nechta hodisa va audit yozish
    store.log_event("admin", "test.action", {"key": "value"})

    # Zaxira olish (.db nusxa)
    bk_file = backup_mod.create_backup(db_path, backup_dir, keep=5)
    assert bk_file.exists()

    # Tiklash mashqini o'tkazish
    rep = run_restore_drill(backup_dir)
    assert rep.success
    assert rep.integrity_check == "ok"
    assert rep.audit_chain_valid is True
    assert rep.audit_count >= 1
    assert rep.backup_size_bytes > 0


def test_restore_drill_endpoint_and_health_integration(tmp_path):
    db_path = str(tmp_path / "app_orig.db")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = SqliteEpisodeStore(db_path)
    client = TestClient(create_app(store, None, backup_db=db_path, backup_dir=backup_dir))

    # Dastlabki zaxira yaratish
    r_bk = client.post("/backups")
    assert r_bk.status_code == 201

    # Deep health tekshiruvi: restore_drill_capable bo'lishi kerak
    r_h = client.get("/health/deep")
    assert r_h.status_code == 200
    assert r_h.json()["checks"]["backups"]["restore_drill_capable"] is True

    # Tiklash mashqini chaqirish
    r_drill = client.post("/backups/restore-drill")
    assert r_drill.status_code == 200
    data = r_drill.json()
    assert data["success"] is True
    assert data["integrity_check"] == "ok"
    assert data["audit_chain_valid"] is True
