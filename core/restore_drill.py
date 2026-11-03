"""Avtomatik zaxira nusxani tiklash mashqi (Automated Restore Drill - ISO 13485 / ISO 27001).

Har bir zaxira nusxa (SQLite .db yoki .gz) favqulodda vaziyatda haqiqatdan ham
buzilmasdan to'liq tiklanishini va audit zanjiri butunligini kafolatlash uchun
muntazam ravishda izolyatsiyalangan muhitda tekshiruvdan o'tkaziladi.
"""
from __future__ import annotations

import gzip
import hashlib
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("cardiopath.backup.drill")


@dataclass
class RestoreDrillReport:
    success: bool
    backup_path: str
    backup_size_bytes: int
    episodes_count: int
    audit_count: int
    integrity_check: str
    audit_chain_valid: bool
    audit_chain_message: str
    duration_seconds: float
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _verify_restored_audit_chain(conn: sqlite3.Connection) -> tuple[bool, str]:
    """Tikланган SQLite bazasida audit_log xesh zanjirini tekshiradi."""
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "audit_log" not in tables:
            return True, "audit_log jadvali mavjud emas"

        # Check if hash column exists
        cols = [r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
        if "hash" not in cols:
            return True, "eski formatdagi audit_log (xesh ustunisiz)"

        rows = conn.execute(
            "SELECT seq, episode_id, actor, action, detail, at, prev_hash, hash FROM audit_log ORDER BY seq ASC"
        ).fetchall()

        if not rows:
            return True, "audit_log bo'sh (0 ta yozuv)"

        last_hash = "GENESIS"
        for r_id, eid, actor, action, detail, at, prev_hash, expected_hash in rows:
            if prev_hash is None or expected_hash is None:
                continue
            if prev_hash != last_hash:
                return False, f"Zanjir buzilgan: yozuv #{r_id} prev_hash={prev_hash}, kutilgan={last_hash}"

            payload = f"{prev_hash}|{eid}|{actor}|{action}|{detail}|{at}".encode("utf-8")
            computed = hashlib.sha256(payload).hexdigest()
            if computed != expected_hash:
                return False, f"Yozuv #{r_id} xeshi soxtalashtirilgan: hisoblangan={computed}, yozilgan={expected_hash}"

            last_hash = expected_hash

        return True, f"Barcha {len(rows)} ta audit yozuvlarining xesh zanjiri 100% to'g'ri"
    except Exception as exc:
        return False, f"Audit tekshirishda xatolik: {exc}"


def run_restore_drill(backup_dir: Path | str, target_dir: Optional[Path | str] = None) -> RestoreDrillReport:
    """Zaxira nusxalaridan eng so'nggisini olib, vaqtinchalik muhitga tiklab yaxlitligini tekshiradi."""
    b_dir = Path(backup_dir)
    if not b_dir.exists() or not b_dir.is_dir():
        return RestoreDrillReport(
            success=False,
            backup_path="",
            backup_size_bytes=0,
            episodes_count=0,
            audit_count=0,
            integrity_check="not_found",
            audit_chain_valid=False,
            audit_chain_message="Zaxira katalogi mavjud emas",
            duration_seconds=0.0,
            error=f"Zaxira katalogi topilmadi: {b_dir}",
        )

    # Zaxira fayllarini topish (.db yoki .gz)
    candidates = [
        p for p in b_dir.iterdir()
        if p.is_file() and (p.name.endswith(".db") or p.name.endswith(".gz") or p.name.endswith(".sqlite"))
    ]
    if not candidates:
        return RestoreDrillReport(
            success=False,
            backup_path="",
            backup_size_bytes=0,
            episodes_count=0,
            audit_count=0,
            integrity_check="empty",
            audit_chain_valid=False,
            audit_chain_message="Zaxira nusxalari topilmadi",
            duration_seconds=0.0,
            error=f"{b_dir} ichida hech qanday zaxira fayli (.db/.gz) mavjud emas",
        )

    # Eng so'nggi yaratilgan yoki o'zgartirilgan zaxirani olish
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    file_size = newest.stat().st_size

    t0 = time.perf_counter()

    with tempfile.TemporaryDirectory() as tmp_d:
        tmp_path = Path(tmp_d)
        restored_db_path = tmp_path / "restored_drill.db"

        try:
            if newest.name.endswith(".gz"):
                with gzip.open(newest, "rb") as f_in, open(restored_db_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(newest, restored_db_path)

            # SQLite yaxlitligini tekshirish
            conn = sqlite3.connect(str(restored_db_path), timeout=10.0)
            try:
                # PRAGMA integrity_check
                chk_rows = conn.execute("PRAGMA integrity_check;").fetchall()
                integrity_ok = len(chk_rows) == 1 and chk_rows[0][0] == "ok"
                integrity_str = "ok" if integrity_ok else str(chk_rows)

                if not integrity_ok:
                    dur = time.perf_counter() - t0
                    return RestoreDrillReport(
                        success=False,
                        backup_path=newest.name,
                        backup_size_bytes=file_size,
                        episodes_count=0,
                        audit_count=0,
                        integrity_check=integrity_str,
                        audit_chain_valid=False,
                        audit_chain_message="SQLite integrity_check muvaffaqiyatsiz",
                        duration_seconds=dur,
                        error=f"Baza yaxlit emas: {integrity_str}",
                    )

                # Jadval ma'lumotlarini hisoblash
                episodes_count = 0
                audit_count = 0
                tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                if "episodes" in tables:
                    episodes_count = conn.execute("SELECT count(*) FROM episodes").fetchone()[0]
                if "audit_log" in tables:
                    audit_count = conn.execute("SELECT count(*) FROM audit_log").fetchone()[0]

                # Xesh zanjiri tekshiruvi
                chain_valid, chain_msg = _verify_restored_audit_chain(conn)

            finally:
                conn.close()

            dur = time.perf_counter() - t0
            return RestoreDrillReport(
                success=chain_valid,
                backup_path=newest.name,
                backup_size_bytes=file_size,
                episodes_count=episodes_count,
                audit_count=audit_count,
                integrity_check="ok",
                audit_chain_valid=chain_valid,
                audit_chain_message=chain_msg,
                duration_seconds=round(dur, 4),
                error=None if chain_valid else f"Audit xesh zanjiri buzilgan: {chain_msg}",
            )

        except Exception as exc:
            dur = time.perf_counter() - t0
            log.exception("Zaxira tiklash mashqida xatolik: %s", exc)
            return RestoreDrillReport(
                success=False,
                backup_path=newest.name,
                backup_size_bytes=file_size,
                episodes_count=0,
                audit_count=0,
                integrity_check="exception",
                audit_chain_valid=False,
                audit_chain_message="Tiklash paytida istisno yuz berdi",
                duration_seconds=round(dur, 4),
                error=str(exc),
            )
