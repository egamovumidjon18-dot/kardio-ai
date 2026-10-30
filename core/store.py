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

    def save(self, ep: Episode, actor: str, action: str, detail: Optional[dict] = None) -> None:
        now = utcnow()
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
