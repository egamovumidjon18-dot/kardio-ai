"""PostgreSQL saqlash qatlami (Enterprise / Multi-server deployment).

`core.store.EpisodeStore` interfeysining to'liq realizatsiyasi.
psycopg (v3) yoki psycopg2 kutubxonasi orqali PostgreSQL bazasiga ulanadi.

Afzalliklari:
  * Yirik kardiologiya markazlari va viloyat filiallari uchun ko'p foydalanuvchili yuqori yuklama;
  * JSONB formatida indekslangan hujjatlar;
  * Optimistik blokirovka (`rev` versiya tekshiruvi — EpisodeConflict);
  * Atomik tranzaksiyalar (epizod + signal + audit);
  * Kriptografik xesh-zanjirli (tamper-evident) audit logi.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Optional

from core.episode import Episode, Stage
from core.evidence import utcnow
from core.handoff import Handoff
from core.identity import effective_actor
from core.store import (
    AlertAckError,
    EpisodeConflict,
    EpisodeStore,
    episode_from_dict,
    episode_summary,
    episode_to_dict,
)

log = logging.getLogger("cardiopath.postgres")


def _get_pg_driver() -> Any:
    """psycopg (v3) yoki psycopg2 ni aniqlaydi; bo'lmasa xushmuomala xatolik beradi."""
    try:
        import psycopg
        return psycopg
    except ImportError:
        try:
            import psycopg2
            return psycopg2
        except ImportError:
            raise ImportError(
                "PostgreSQL adapteri uchun 'psycopg' kutubxonasi topilmadi. "
                "O'rnatish uchun buyruqni bajaring: pip install \"psycopg[binary]\""
            ) from None


class PostgresEpisodeStore(EpisodeStore):
    SYSTEM_ID = "system"
    _ALERT_COLS = "id, episode_id, patient_ref, level, source, reasons, created_at, ack_by, ack_at, ack_note, message, delivery, attempts, delivered_at, last_attempt_at"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pg = _get_pg_driver()
        self._init_schema()

    def _connect(self):
        return self.pg.connect(self.dsn)

    def _init_schema(self) -> None:
        """Jadvallar va indekslarni yaratish."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    doc JSONB NOT NULL,
                    updated_at TIMESTAMPTZ,
                    rev INT NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    seq BIGSERIAL PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail JSONB,
                    at TIMESTAMPTZ NOT NULL,
                    prev_hash TEXT,
                    hash TEXT
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id BIGSERIAL PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    patient_ref TEXT NOT NULL,
                    level TEXT NOT NULL,
                    source TEXT,
                    reasons JSONB,
                    created_at TIMESTAMPTZ NOT NULL,
                    ack_by TEXT,
                    ack_at TIMESTAMPTZ,
                    ack_note TEXT,
                    message TEXT,
                    delivery TEXT DEFAULT 'none',
                    attempts INT DEFAULT 0,
                    delivered_at TIMESTAMPTZ,
                    last_attempt_at TIMESTAMPTZ
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_open ON alerts (ack_at, level, created_at);
                CREATE INDEX IF NOT EXISTS idx_alerts_episode ON alerts (episode_id);
                CREATE INDEX IF NOT EXISTS idx_audit_episode ON audit_log (episode_id);
                """)
            conn.commit()

    def _insert_audit(self, cur, episode_id: str, actor: str, action: str, detail_str: str, at: str) -> str:
        cur.execute("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1")
        last = cur.fetchone()
        prev_h = last[0] if (last and last[0]) else "GENESIS"
        raw = f"{prev_h}|{episode_id}|{actor}|{action}|{detail_str}|{at}"
        entry_h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        cur.execute(
            "INSERT INTO audit_log (episode_id, actor, action, detail, at, prev_hash, hash) "
            "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)",
            (episode_id, actor, action, detail_str, at, prev_h, entry_h)
        )
        return entry_h

    def save(self, ep: Episode, actor: str, action: str, detail: Optional[dict] = None) -> None:
        now = utcnow()
        actor = effective_actor(actor)
        doc_json = json.dumps(episode_to_dict(ep), ensure_ascii=False)
        rev = getattr(ep, "_rev", None)

        with self._connect() as conn:
            with conn.cursor() as cur:
                if rev is None:
                    cur.execute(
                        "INSERT INTO episodes (id, doc, updated_at, rev) VALUES (%s, %s::jsonb, %s, 1) "
                        "ON CONFLICT (id) DO NOTHING",
                        (ep.id, doc_json, now)
                    )
                    if cur.rowcount == 0:
                        raise EpisodeConflict(f"epizod {ep.id} allaqachon mavjud")
                else:
                    cur.execute(
                        "UPDATE episodes SET doc = %s::jsonb, updated_at = %s, rev = rev + 1 "
                        "WHERE id = %s AND rev = %s",
                        (doc_json, now, ep.id, rev)
                    )
                    if cur.rowcount == 0:
                        raise EpisodeConflict("bemor yozuvini boshqa foydalanuvchi hozirgina o'zgartirdi — qayta urining")

                ep._rev = (rev or 0) + 1
                self._insert_audit(cur, ep.id, actor, action, json.dumps(detail or {}, ensure_ascii=False), now)
            conn.commit()

    def save_with_alert(self, ep: Episode, actor: str, action: str,
                        level: Optional[str] = None,
                        reasons: Optional[list[str]] = None,
                        message: str = "",
                        delivered: Optional[bool] = None) -> Optional[dict]:
        now = utcnow()
        actor = effective_actor(actor)
        doc_json = json.dumps(episode_to_dict(ep), ensure_ascii=False)
        rev = getattr(ep, "_rev", None)
        created_alert = None

        with self._connect() as conn:
            with conn.cursor() as cur:
                if rev is None:
                    cur.execute(
                        "INSERT INTO episodes (id, doc, updated_at, rev) VALUES (%s, %s::jsonb, %s, 1) "
                        "ON CONFLICT (id) DO NOTHING",
                        (ep.id, doc_json, now)
                    )
                    if cur.rowcount == 0:
                        raise EpisodeConflict(f"epizod {ep.id} allaqachon mavjud")
                else:
                    cur.execute(
                        "UPDATE episodes SET doc = %s::jsonb, updated_at = %s, rev = rev + 1 "
                        "WHERE id = %s AND rev = %s",
                        (doc_json, now, ep.id, rev)
                    )
                    if cur.rowcount == 0:
                        raise EpisodeConflict("bemor yozuvini boshqa foydalanuvchi hozirgina o'zgartirdi — qayta urining")

                ep._rev = (rev or 0) + 1

                if level in ("red", "amber"):
                    delivery = "none" if delivered is None else ("sent" if delivered else "failed")
                    cur.execute(
                        "INSERT INTO alerts (episode_id, patient_ref, level, source, reasons, created_at, message, delivery, attempts, "
                        "delivered_at, last_attempt_at) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s) RETURNING id",
                        (ep.id, ep.patient_ref, level, action, json.dumps(reasons or [], ensure_ascii=False), now, message, delivery,
                         0 if delivered is None else 1, now if delivered else None, None if delivered is None else now)
                    )
                    alert_id = cur.fetchone()[0]
                    cur.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = %s", (alert_id,))
                    created_alert = self._alert_row(cur.fetchone())

                detail = {"alert": level, "notified": bool(delivered),
                          "alert_id": created_alert["id"] if created_alert else None}
                self._insert_audit(cur, ep.id, actor, action, json.dumps(detail, ensure_ascii=False), now)
            conn.commit()

        return created_alert

    def get(self, episode_id: str) -> Optional[Episode]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT doc, rev FROM episodes WHERE id = %s", (episode_id,))
                row = cur.fetchone()
        if not row:
            return None
        doc = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        ep = episode_from_dict(doc)
        ep._rev = row[1]
        return ep

    def audit(self, episode_id: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT actor, action, detail, at FROM audit_log WHERE episode_id = %s ORDER BY seq",
                    (episode_id,)
                )
                rows = cur.fetchall()
        return [{"actor": a, "action": b, "detail": (c if isinstance(c, dict) else json.loads(c)), "at": str(d)} for a, b, c, d in rows]

    def ids(self) -> list[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM episodes ORDER BY updated_at")
                return [r[0] for r in cur.fetchall()]

    def log_event(self, actor: str, action: str, detail: Optional[dict] = None) -> None:
        now = utcnow()
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._insert_audit(cur, self.SYSTEM_ID, actor, action, json.dumps(detail or {}, ensure_ascii=False), now)
            conn.commit()

    def security_events(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT actor, action, detail, at FROM audit_log WHERE episode_id = %s ORDER BY seq DESC LIMIT %s",
                    (self.SYSTEM_ID, limit)
                )
                rows = cur.fetchall()
        return [{"actor": a, "action": b, "detail": (c if isinstance(c, dict) else json.loads(c)), "at": str(d)} for a, b, c, d in rows]

    def verify_audit_integrity(self) -> tuple[bool, Optional[str]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT seq, episode_id, actor, action, detail, at, prev_hash, hash FROM audit_log ORDER BY seq ASC")
                rows = cur.fetchall()
        exp = "GENESIS"
        for seq, ep_id, actor, action, detail, at, prev_h, entry_h in rows:
            if prev_h is None or entry_h is None:
                continue
            if prev_h != exp:
                return False, f"Audit zanjiri uzilgan: seq={seq}, kutilgan={exp}, kelgan={prev_h}"
            detail_str = json.dumps(detail, ensure_ascii=False) if isinstance(detail, (dict, list)) else str(detail)
            raw = f"{prev_h}|{ep_id}|{actor}|{action}|{detail_str}|{at}"
            calc_h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if calc_h != entry_h:
                return False, f"Audit yozuvi o'zgartirilgan: seq={seq}, hisoblangan={calc_h} != saqlangan={entry_h}"
            exp = entry_h
        return True, None

    def _alert_row(self, r) -> Optional[dict]:
        if not r:
            return None
        reasons = r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]")
        return {
            "id": r[0], "episode_id": r[1], "patient_ref": r[2], "level": r[3], "source": r[4],
            "reasons": reasons, "created_at": str(r[6]), "ack_by": r[7], "ack_at": str(r[8]) if r[8] else None,
            "ack_note": r[9], "message": r[10], "delivery": r[11], "attempts": r[12],
            "delivered_at": str(r[13]) if r[13] else None, "last_attempt_at": str(r[14]) if r[14] else None,
        }

    def add_alert(self, episode_id: str, patient_ref: str, level: str, source: str, reasons: list[str],
                  message: str = "", delivered: Optional[bool] = None) -> dict:
        now = utcnow()
        delivery = "none" if delivered is None else ("sent" if delivered else "failed")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alerts (episode_id, patient_ref, level, source, reasons, created_at, message, delivery, attempts, "
                    "delivered_at, last_attempt_at) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (episode_id, patient_ref, level, source, json.dumps(reasons or [], ensure_ascii=False), now, message, delivery,
                     0 if delivered is None else 1, now if delivered else None, None if delivered is None else now)
                )
                aid = cur.fetchone()[0]
                cur.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = %s", (aid,))
                row = self._alert_row(cur.fetchone())
            conn.commit()
        return row

    def undelivered_alerts(self, max_attempts: int = 10) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {self._ALERT_COLS} FROM alerts WHERE ack_at IS NULL AND delivery = 'failed' "
                    "AND attempts < %s ORDER BY created_at",
                    (max_attempts,)
                )
                rows = cur.fetchall()
        return [self._alert_row(r) for r in rows if r]

    def mark_delivery(self, alert_id: int, ok: bool) -> Optional[dict]:
        now = utcnow()
        with self._connect() as conn:
            with conn.cursor() as cur:
                if ok:
                    cur.execute(
                        "UPDATE alerts SET delivery = 'sent', attempts = attempts + 1, delivered_at = %s, last_attempt_at = %s WHERE id = %s",
                        (now, now, alert_id)
                    )
                else:
                    cur.execute(
                        "UPDATE alerts SET delivery = 'failed', attempts = attempts + 1, last_attempt_at = %s WHERE id = %s",
                        (now, alert_id)
                    )
                cur.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = %s", (alert_id,))
                row = self._alert_row(cur.fetchone())
            conn.commit()
        return row

    def alerts(self, status: str = "open", level: Optional[str] = None, episode_id: Optional[str] = None,
               limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
        where, args = [], []
        if status == "open":
            where.append("ack_at IS NULL")
        elif status == "acknowledged":
            where.append("ack_at IS NOT NULL")
        if level:
            where.append("level = %s")
            args.append(level)
        if episode_id:
            where.append("episode_id = %s")
            args.append(episode_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        order = "ORDER BY CASE level WHEN 'red' THEN 0 WHEN 'amber' THEN 1 ELSE 2 END, created_at DESC" if status == "open" else "ORDER BY created_at DESC"

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM alerts {clause}", args)
                total = cur.fetchone()[0]
                cur.execute(f"SELECT {self._ALERT_COLS} FROM alerts {clause} {order} LIMIT %s OFFSET %s", [*args, limit, offset])
                rows = cur.fetchall()
        return total, [self._alert_row(r) for r in rows if r]

    def ack_alert(self, alert_id: int, actor: str, note: str = "") -> Optional[dict]:
        now = utcnow()
        actor = effective_actor(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ack_at FROM alerts WHERE id = %s", (alert_id,))
                row = cur.fetchone()
                if not row:
                    return None
                if row[0] is not None:
                    raise AlertAckError("signal allaqachon qabul qilingan")
                cur.execute(
                    "UPDATE alerts SET ack_by = %s, ack_at = %s, ack_note = %s WHERE id = %s",
                    (actor, now, note.strip(), alert_id)
                )
                cur.execute(f"SELECT {self._ALERT_COLS} FROM alerts WHERE id = %s", (alert_id,))
                res = self._alert_row(cur.fetchone())
            conn.commit()
        return res

    def summaries(self, stage: Optional[str] = None, q: Optional[str] = None,
                  limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
        where, args = [], []
        if stage:
            where.append("doc->>'stage' = %s")
            args.append(stage)
        if q:
            where.append("lower(doc->>'patient_ref') LIKE %s")
            args.append(f"%{q.lower()}%")
        clause = ("WHERE " + " AND ".join(where)) if where else ""

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM episodes {clause}", args)
                total = cur.fetchone()[0]
                cur.execute(
                    f"SELECT doc, updated_at FROM episodes {clause} ORDER BY updated_at DESC, id LIMIT %s OFFSET %s",
                    [*args, limit, offset]
                )
                rows = cur.fetchall()

        items = [episode_summary(r[0] if isinstance(r[0], dict) else json.loads(r[0]), str(r[1]) if r[1] else None) for r in rows]
        return total, items
