"""Bemorlar bazasining zaxira nusxasi: ishlab turgan bazadan ham izchil (SQLite backup API), tekshirilgan, eski nusxalar o'chiriladi.

    python -m core.backup create  [--db cardiopath.db] [--dir backups]
    python -m core.backup list    [--dir backups]
    python -m core.backup restore <nusxa.db> [--db cardiopath.db]     # server TO'XTATILGAN bo'lishi kerak

Baza bitta faylda: bemorlar, audit jurnali, ogohlantirishlar, foydalanuvchilar va shadow yozuvlari — hammasi nusxaga kiradi.
Muhim: nusxani boshqa diskka yoki fleshkaga ham ko'chirib turing — bitta disk buzilsa, ikkalasi ham yo'qoladi.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import time
from pathlib import Path

PREFIX = "cardiopath-"


def create_backup(db_path: str | Path, out_dir: str | Path, keep: int = 14) -> Path:
    """Izchil nusxa oladi, butunligini tekshiradi, eng yangi `keep` tadan eskilarini o'chiradi. Nusxa yo'lini qaytaradi."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{PREFIX}{time.strftime('%Y%m%d-%H%M%S')}.db"
    n = 2
    while target.exists():
        target = target.with_name(f"{PREFIX}{time.strftime('%Y%m%d-%H%M%S')}-{n}.db"); n += 1
    tmp = target.with_suffix(".tmp")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(tmp))
    try:
        src.backup(dst)                       # ishlab turgan bazadan ham to'g'ri nusxa (yozuvlar o'rtasida uzilmaydi)
        ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dst.close(); src.close()
    if ok != "ok":
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"zaxira nusxa butunlik tekshiruvidan o'tmadi: {ok}")
    tmp.replace(target)
    for old in list_backups(out_dir)[keep:]:
        Path(old["path"]).unlink(missing_ok=True)
    return target


def list_backups(out_dir: str | Path) -> list[dict]:
    """Eng yangisi birinchi."""
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return []
    files = sorted(out_dir.glob(f"{PREFIX}*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "path": str(p), "size_bytes": p.stat().st_size,
             "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))} for p in files]


def restore_backup(backup: str | Path, db_path: str | Path) -> Path:
    """Nusxani tiklaydi. Avvalgi baza «.before-restore» nomi bilan saqlanadi (adashib tiklansa, qaytarish mumkin)."""
    backup, db_path = Path(backup), Path(db_path)
    con = sqlite3.connect(str(backup))
    try:
        ok = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    if ok != "ok":
        raise RuntimeError(f"nusxa buzilgan, tiklanmadi: {ok}")
    kept = db_path.with_name(db_path.name + f".before-restore-{time.strftime('%Y%m%d-%H%M%S')}")
    if db_path.exists():
        shutil.copy2(db_path, kept)
    shutil.copy2(backup, db_path)
    return kept


def main() -> None:
    ap = argparse.ArgumentParser(description="CardioPath bazasining zaxira nusxalari")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--db", default="cardiopath.db"); c.add_argument("--dir", default="backups"); c.add_argument("--keep", type=int, default=14)
    l = sub.add_parser("list"); l.add_argument("--dir", default="backups")
    r = sub.add_parser("restore"); r.add_argument("backup"); r.add_argument("--db", default="cardiopath.db")
    a = ap.parse_args()
    if a.cmd == "create":
        print("nusxa olindi:", create_backup(a.db, a.dir, a.keep))
    elif a.cmd == "list":
        for b in list_backups(a.dir):
            print(f"{b['created_at']}  {b['size_bytes'] / 1e6:6.1f} MB  {b['name']}")
    else:
        print("tiklandi; avvalgi baza saqlandi:", restore_backup(a.backup, a.db))


if __name__ == "__main__":
    main()
