"""Tests for tamper-evident hash-chained audit log in core/store.py."""
import pytest
import sqlite3

from core.episode import Episode, Stage
from core.store import SqliteEpisodeStore


def test_audit_hash_chain_valid(tmp_path):
    db_path = str(tmp_path / "chain.db")
    store = SqliteEpisodeStore(db_path)

    ep = Episode(patient_ref="PSV-100", population="adult")
    store.save(ep, "dr.smith", "episode.create")

    # Add alert
    store.save_with_alert(ep, "dr.smith", "screening.triage", level="amber", reasons=["SpO2 low"])

    # Log security event
    store.log_event("admin", "user.login", {"ip": "127.0.0.1"})

    # Check integrity
    ok, err = store.verify_audit_integrity()
    assert ok is True
    assert err is None


def test_audit_hash_chain_tamper_detected(tmp_path):
    db_path = str(tmp_path / "tamper.db")
    store = SqliteEpisodeStore(db_path)

    ep = Episode(patient_ref="PSV-200", population="adult")
    store.save(ep, "dr.smith", "episode.create")
    store.save(ep, "dr.smith", "workup.echo_dx", {"dx": "VSD"})
    store.log_event("admin", "backup.create")

    ok, err = store.verify_audit_integrity()
    assert ok is True

    # Maliciously modify the database row directly via separate connection
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE audit_log SET actor = 'malicious_actor' WHERE seq = 2")
    conn.commit()
    conn.close()

    ok_tamper, err_tamper = store.verify_audit_integrity()
    assert ok_tamper is False
    assert "o'zgartirilgan" in err_tamper or "uzilgan" in err_tamper


def test_sms_notifier_env(monkeypatch):
    from guardian.escalation import SmsNotifier, build_notifier_from_env

    # 1. When not configured
    monkeypatch.delenv("CARDIOPATH_SMS_URL", raising=False)
    monkeypatch.delenv("CARDIOPATH_SMS_PHONE", raising=False)
    assert SmsNotifier.from_env() is None

    # 2. When configured
    monkeypatch.setenv("CARDIOPATH_SMS_URL", "https://sms.example.com/api/send")
    monkeypatch.setenv("CARDIOPATH_SMS_PHONE", "+998901234567")
    notifier = SmsNotifier.from_env()
    assert notifier is not None
    assert notifier.is_external is True
    assert notifier.phone == "+998901234567"
