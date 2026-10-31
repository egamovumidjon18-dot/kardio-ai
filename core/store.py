"""Saqlash qatlami — repository interfeysi + stdlib sqlite3 realizatsiyasi.

Epizod hujjat (JSON) sifatida saqlanadi; audit alohida jadvalda (faqat qo'shiladi).
Postgres adapteri keyinroq shu `EpisodeStore` interfeysiga ulanadi.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from typing import Optional

from core.episode import Episode, Stage
from core.identity import effective_actor
from core.evidence import Evidence, utcnow
from core.handoff import Handoff


def episode_to_dict(ep: Episode) -> dict:
    return {
        "id": ep.id,
        "patient_ref": ep.patient_ref,
        "population": ep.population,
        "stage": ep.stage.value,
        "created_at": ep.created_at,
        "evidence": [e.to_dict() for e in ep.evidence],
        "handoffs": [h.to_dict() for h in ep.handoffs],
    }


def episode_from_dict(d: dict) -> Episode:
    return Episode(
        id=d["id"], patient_ref=d["patient_ref"], population=d["population"],
        stage=Stage(d["stage"]), created_at=d["created_at"],
        evidence=[Evidence.from_dict(e) for e in d["evidence"]],
        handoffs=[Handoff(**h) for h in d["handoffs"]],
    )


class EpisodeStore(ABC):
    @abstractmethod
    def save(self, ep: Episode, actor: str, action: str, detail: Optional[dict] = None) -> None: ...

    @abstractmethod
    def get(self, episode_id: str) -> Optional[Episode]: ...

    @abstractmethod
    def audit(self, episode_id: str) -> list[dict]: ...

    @abstractmethod
    def ids(self) -> list[str]: ...

    @abstractmethod
    def summaries(self, stage: Optional[str] = None, q: Optional[str] = None,
                  limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
        """Epizodlar qisqa ro'yxati (yangisi birinchi): (jami soni, sahifa)."""

    @abstractmethod
    def log_event(self, actor: str, action: str, detail: Optional[dict] = None) -> None: ...

    @abstractmethod
    def security_events(self, limit: int = 100) -> list[dict]: ...

    @abstractmethod
    def add_alert(self, episode_id: str, patient_ref: str, level: str, source: str, reasons: list[str],
                  message: str = "", delivered: Optional[bool] = None) -> dict: ...

    @abstractmethod
    def undelivered_alerts(self, max_attempts: int = 10) -> list[dict]:
        """Ochiq, lekin jarrohga yetkazilmagan signallar (qayta yuborish navbati)."""

    @abstractmethod
    def mark_delivery(self, alert_id: int, ok: bool) -> Optional[dict]: ...

    @abstractmethod
    def alerts(self, status: str = "open", level: Optional[str] = None, episode_id: Optional[str] = None,
               limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
        """Signallar: `status` open | acknowledged | all. Ochiqlari: avval qizil, keyin eng yangisi."""

    @abstractmethod
    def ack_alert(self, alert_id: int, actor: str, note: str = "") -> Optional[dict]:
        """Signalni qabul qilingan deb belgilaydi. Yo'q signal → None; allaqachon qabul qilingan → AlertAckError."""


class AlertAckError(ValueError):
    pass


def episode_summary(doc: dict, updated_at: Optional[str]) -> dict:
    """Ro'yxat qatori: to'liq hujjatsiz, faqat tanlash va ustuvorlik uchun kerakli ma'lumot."""
    triage = next((e for e in reversed(doc["evidence"]) if e["kind"] == "screening.triage"), None)
    return {
        "id": doc["id"], "patient_ref": doc["patient_ref"], "population": doc["population"],
        "stage": doc["stage"], "created_at": doc["created_at"], "updated_at": updated_at,
        "n_evidence": len(doc["evidence"]), "n_handoffs": len(doc["handoffs"]),
        "screening_risk": triage["risk"] if triage else None,
    }


def _like(term: str) -> str:
    """LIKE uchun maxsus belgilarni (%, _, \\) oddiy matn qilish."""
    return "%" + term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class SqliteEpisodeStore(EpisodeStore):
    def __init__(self, path: str = "cardiopath.db") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS episodes (id TEXT PRIMARY KEY, doc TEXT NOT NULL, updated_at TEXT)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS audit_log (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                "episode_id TEXT, actor TEXT, action TEXT, detail TEXT, at TEXT)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id TEXT NOT NULL, "
                "patient_ref TEXT, level TEXT NOT NULL, source TEXT, reasons TEXT, created_at TEXT, "
                "ack_by TEXT, ack_at TEXT, ack_note TEXT)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS alerts_open ON alerts (ack_at, level, created_at)")
            # yetkazish holati (eski bazalarga ustun qo'shiladi): none | sent | failed
            have = {r[1] for r in self._conn.execute("PRAGMA table_info(alerts)")}
            for col, ddl in (("message", "TEXT"), ("delivery", "TEXT DEFAULT 'none'"), ("attempts", "INTEGER DEFAULT 0"),
                             ("delivered_at", "TEXT"), ("last_attempt_at", "TEXT")):
                if col not in have:
                    self._conn.execute(f"ALTER TABLE alerts ADD COLUMN {col} {ddl}")
            self._conn.execute("CREATE INDEX IF NOT EXISTS alerts_episode ON alerts (episode_id)")

    def save(self, ep: Episode, actor: str, action: str, detail: Optional[dict] = None) -> None:
        now = utcnow()
        actor = effective_actor(actor)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO episodes (id, doc, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET doc = excluded.doc, updated_at = excluded.updated_at",
                (ep.id, json.dumps(episode_to_dict(ep), ensure_ascii=False), now))
            self._conn.execute(
                "INSERT INTO audit_log (episode_id, actor, action, detail, at) VALUES (?, ?, ?, ?, ?)",
                (ep.id, actor, action, json.dumps(detail or {}, ensure_ascii=False), now))

    def get(self, episode_id: str) -> Optional[Episode]:
        with self._lock:
            row = self._conn.execute("SELECT doc FROM episodes WHERE id = ?", (episode_id,)).fetchone()
        return episode_from_dict(json.loads(row[0])) if row else None

    def audit(self, episode_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT actor, action, detail, at FROM audit_log WHERE episode_id = ? ORDER BY seq",
                (episode_id,)).fetchall()
        return [{"actor": a, "action": b, "detail": json.loads(c), "at": d} for a, b, c, d in rows]

    def ids(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self._conn.execute("SELECT id FROM episodes ORDER BY updated_at")]

    # ---- tizim (xavfsizlik) hodisalari: kirish, chiqish, foydalanuvchilar boshqaruvi. Parol va tokenlar HECH QACHON yozilmaydi.
    SYSTEM_ID = "system"

    def log_event(self, actor: str, action: str, detail: Optional[dict] = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO audit_log (episode_id, actor, action, detail, at) VALUES (?, ?, ?, ?, ?)",
                (self.SYSTEM_ID, actor, action, json.dumps(detail or {}, ensure_ascii=False), utcnow()))

    def security_events(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT actor, action, detail, at FROM audit_log WHERE episode_id = ? ORDER BY seq DESC LIMIT ?",
                (self.SYSTEM_ID, limit)).fetchall()
        return [{"actor": a, "action": b, "detail": json.loads(c), "at": d} for a, b, c, d in rows]

    def summaries(self, stage: Optional[str] = None, q: Optional[str] = None,
                  limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
        where, args = [], []
        if stage:
            where.append("json_extract(doc, '$.stage') = ?")
            args.append(stage)
        if q:
            where.append("lower(json_extract(doc, '$.patient_ref')) LIKE ? ESCAPE '\\'")
            args.append(_like(q))
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        with self._lock:
            total = self._conn.execute(f"SELECT count(*) FROM episodes {clause}", args).fetchone()[0]
            rows = self._conn.execute(
                f"SELECT doc, updated_at FROM episodes {clause} ORDER BY updated_at DESC, id LIMIT ? OFFSET ?",
                [*args, limit, offset]).fetchall()
        items = [episode_summary(json.loads(doc), upd) for doc, upd in rows]
        # ochiq (qabul qilinmagan) signallar: bir so'rovda hamma qatorlar uchun
        by_ep: dict[str, dict[str, int]] = {}
        if items:
            marks = ",".join("?" * len(items))
            with self._lock:
                for ep_id, lvl, n in self._conn.execute(
                        f"SELECT episode_id, level, count(*) FROM alerts WHERE ack_at IS NULL "
                        f"AND episode_id IN ({marks}) GROUP BY episode_id, level", [i["id"] for i in items]):
                    by_ep.setdefault(ep_id, {})[lvl] = n
        for it in items:
            lv = by_ep.get(it["id"], {})
            it["open_alerts"] = sum(lv.values())
            it["open_alert_level"] = "red" if lv.get("red") else ("amber" if lv.get("amber") else None)
        return total, items

    # ---- signallar
    @staticmethod
    def _alert_row(r) -> dict:
        return {"id": r[0], "episode_id": r[1], "patient_ref": r[2], "level": r[3], "source": r[4],
                "reasons": json.loads(r[5] or "[]"), "created_at": r[6], "acknowledged": r[8] is not None,
                "ack_by": r[7], "ack_at": r[8], "ack_note": r[9],
                "delivery": {"status": r[10] or "none", "attempts": r[11] or 0, "delivered_at": r[12], "last_attempt_at": r[13]}}

    _ALERT_COLS = ("id, episode_id, patient_ref, level, source, reasons, created_at, ack_by, ack_at, ack_note, "
                   "delivery, attempts, delivered_at, last_attempt_at")

    def add_alert(self, episode_id: str, patient_ref: str, level: str, source: str, reasons: list[str],
                  message: str = "", delivered: Optional[bool] = None) -> dict:
        now = utcnow()
        delivery = "none" if delivered is None else ("sent" if delivered else "failed")
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO alerts (episode_id, patient_ref, level, source, reasons, created_at, message, delivery, attempts, "
                "delivered_at, last_attempt_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (episode_id, patient_ref, level, source, json.dumps(reasons, ensure_ascii=False), now, message, delivery,
                 0 if delivered is None else 1, now if delivered else None, None if delivered is None else now))
            row = self._conn.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._alert_row(row)

    def undelivered_alerts(self, max_attempts: int = 10) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {self._ALERT_COLS}, message FROM alerts WHERE ack_at IS NULL AND delivery = 'failed' AND attempts < ? "
                "ORDER BY CASE level WHEN 'red' THEN 0 ELSE 1 END, created_at", (max_attempts,)).fetchall()
        return [{**self._alert_row(r), "message": r[14]} for r in rows]

    def mark_delivery(self, alert_id: int, ok: bool) -> Optional[dict]:
        now = utcnow()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE alerts SET attempts = attempts + 1, last_attempt_at = ?, delivery = ?, "
                "delivered_at = CASE WHEN ? THEN ? ELSE delivered_at END WHERE id = ?",
                (now, "sent" if ok else "failed", ok, now, alert_id))
            row = self._conn.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return self._alert_row(row) if row else None

    def alerts(self, status: str = "open", level: Optional[str] = None, episode_id: Optional[str] = None,
               limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
        where, args = [], []
        if status == "open":
            where.append("ack_at IS NULL")
        elif status == "acknowledged":
            where.append("ack_at IS NOT NULL")
        if level:
            where.append("level = ?"); args.append(level)
        if episode_id:
            where.append("episode_id = ?"); args.append(episode_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        with self._lock:
            total = self._conn.execute(f"SELECT count(*) FROM alerts {clause}", args).fetchone()[0]
            rows = self._conn.execute(
                f"SELECT {self._ALERT_COLS} FROM alerts {clause} "
                "ORDER BY (ack_at IS NOT NULL), CASE level WHEN 'red' THEN 0 ELSE 1 END, created_at DESC, id DESC "
                "LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
        return total, [self._alert_row(r) for r in rows]

    def ack_alert(self, alert_id: int, actor: str, note: str = "") -> Optional[dict]:
        now = utcnow()
        actor = effective_actor(actor)
        with self._lock, self._conn:
            row = self._conn.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if row is None:
                return None
            if row[8] is not None:
                raise AlertAckError(f"signal allaqachon qabul qilingan ({row[7]}, {row[8]})")
            self._conn.execute("UPDATE alerts SET ack_by = ?, ack_at = ?, ack_note = ? WHERE id = ?",
                               (actor, now, note, alert_id))
            self._conn.execute(
                "INSERT INTO audit_log (episode_id, actor, action, detail, at) VALUES (?, ?, ?, ?, ?)",
                (row[1], actor, "alert.ack", json.dumps({"alert_id": alert_id, "level": row[3], "note": note},
                                                        ensure_ascii=False), now))
            row = self._conn.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return self._alert_row(row)
