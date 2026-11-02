"""Jarrohga xabar yetkazish: yetkazilmasa signal yo'qolmaydi, navbatda qoladi va qayta yuboriladi."""
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.alerts import retry_deliveries
from api.main import create_app
from core.store import SqliteEpisodeStore
from tests.test_ai_api import to_guardian


class FlakyNotifier:
    """Internet yo'q (ok=False) yoki bor (ok=True)."""

    def __init__(self, ok=False):
        self.ok, self.sent = ok, []

    def send(self, text):
        self.sent.append(text)
        return self.ok


def red_checkin(tmp_path, notifier):
    store = SqliteEpisodeStore(str(tmp_path / "d.db"))
    c = TestClient(create_app(store, None, notifier=notifier))
    eid = c.post("/episodes", json={"patient_ref": "TG-1", "actor": "dr", "population": "adult"}).json()["id"]
    to_guardian(c, eid)
    r = c.post(f"/episodes/{eid}/guardian/checkin", json={"actor": "p", "symptoms": ["syncope"]})
    assert r.status_code == 200 and r.json()["escalation"]["alert"] == "red"
    return store, c, r.json()


def test_failed_delivery_is_kept_open_and_visible(tmp_path):
    n = FlakyNotifier(ok=False)
    store, c, body = red_checkin(tmp_path, n)
    assert body["escalation"]["notified"] is False and len(n.sent) == 1
    a = c.get("/alerts").json()["items"][0]
    assert a["delivery"] == {"status": "failed", "attempts": 1, "delivered_at": None, "last_attempt_at": a["delivery"]["last_attempt_at"]}
    assert store.undelivered_alerts()[0]["message"].startswith("🔴 SHOSHILINCH")


def test_retry_with_backoff_then_success(tmp_path):
    n = FlakyNotifier(ok=False)
    store, c, _ = red_checkin(tmp_path, n)
    assert retry_deliveries(store, n) == 0 and len(n.sent) == 1          # 60 s kutish hali o'tmagan
    later = datetime.now(timezone.utc) + timedelta(seconds=61)
    assert retry_deliveries(store, n, now=later) == 0 and len(n.sent) == 2   # urinildi, yana muvaffaqiyatsiz
    n.ok = True
    assert retry_deliveries(store, n, now=later + timedelta(seconds=121)) == 1
    a = c.get("/alerts").json()["items"][0]
    assert a["delivery"]["status"] == "sent" and a["delivery"]["attempts"] == 3 and "kechikkan xabar" in n.sent[-1]
    assert not a["acknowledged"]                                           # yetkazildi ≠ jarroh ko'rdi
    assert store.undelivered_alerts() == []


def test_acknowledged_alert_leaves_the_queue_and_manual_resend(tmp_path):
    n = FlakyNotifier(ok=False)
    store, c, _ = red_checkin(tmp_path, n)
    aid = c.get("/alerts").json()["items"][0]["id"]
    n.ok = True
    r = c.post(f"/alerts/{aid}/resend")
    assert r.status_code == 200 and r.json()["delivery"]["status"] == "sent"
    assert c.post(f"/alerts/{aid}/resend").status_code == 409               # allaqachon yetkazilgan
    assert c.post(f"/alerts/{aid}/ack", json={"actor": "dr"}).status_code == 200


def test_green_checkin_creates_no_alert_and_sends_nothing(tmp_path):
    n = FlakyNotifier(ok=True)
    store = SqliteEpisodeStore(str(tmp_path / "g.db"))
    c = TestClient(create_app(store, None, notifier=n))
    eid = c.post("/episodes", json={"patient_ref": "TG-2", "actor": "dr"}).json()["id"]
    to_guardian(c, eid)
    assert c.post(f"/episodes/{eid}/guardian/checkin", json={"actor": "p", "weight_kg": 70}).json()["escalation"]["alert"] == "green"
    assert n.sent == [] and c.get("/alerts").json()["total"] == 0


def test_old_database_gets_delivery_columns(tmp_path):
    db = str(tmp_path / "old.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id TEXT NOT NULL, patient_ref TEXT, level TEXT NOT NULL, "
                "source TEXT, reasons TEXT, created_at TEXT, ack_by TEXT, ack_at TEXT, ack_note TEXT)")
    con.execute("INSERT INTO alerts (episode_id, patient_ref, level, source, reasons, created_at) VALUES ('e', 'p', 'red', 's', '[]', '2026-10-01T00:00:00+00:00')")
    con.commit(); con.close()
    _, items = SqliteEpisodeStore(db).alerts()
    assert items[0]["delivery"]["status"] == "none"


def test_conflict_during_checkin_creates_no_orphan_alert(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "c.db"))
    c = TestClient(create_app(store, None, notifier=FlakyNotifier(ok=True)))
    eid = c.post("/episodes", json={"patient_ref": "TG-3", "actor": "dr", "population": "adult"}).json()["id"]
    to_guardian(c, eid)

    ep = store.get(eid)
    ep._rev = 999
    import pytest
    from core.store import EpisodeConflict
    with pytest.raises(EpisodeConflict):
        store.save_with_alert(ep, "p", "guardian.checkin", level="red", reasons=["test"], message="msg", delivered=True)

    total, items = store.alerts()
    assert total == 0 and len(items) == 0


def test_log_notifier_marks_delivery_as_none(tmp_path):
    from guardian.escalation import LogNotifier
    n = LogNotifier()
    store = SqliteEpisodeStore(str(tmp_path / "log_notif.db"))
    c = TestClient(create_app(store, None, notifier=n))
    eid = c.post("/episodes", json={"patient_ref": "LN-1", "actor": "dr", "population": "adult"}).json()["id"]
    to_guardian(c, eid)
    r = c.post(f"/episodes/{eid}/guardian/checkin", json={"actor": "p", "symptoms": ["syncope"]})
    assert r.status_code == 200
    a = c.get("/alerts").json()["items"][0]
    # LogNotifier is local console only; delivery status must be 'none', never falsely 'sent'
    assert a["delivery"]["status"] == "none"
