"""Nomzod modelni INSON TASDIG'I bilan joriy qilish yoki orqaga qaytarish.

    python -m learning.promote --list
    python -m learning.promote --version v20261101-120000 --approved-by "Familiya I." --note "sabab"
    python -m learning.promote --rollback --approved-by "Familiya I." --note "sabab"

Faqat darvozalardan o'tgan nomzod tasdiqlanadi. Dastur qayta ishga tushirilgach yangi model yuklanadi.
Bu buyruq ataylab veb-API'da emas: kirish tizimi (autentifikatsiya) bo'lmaguncha, tasdiqlash tarmoq orqali ochilmaydi.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from learning.versions import ModelVersions, PromotionError


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", type=Path, default=Path("models/pcg"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--version")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--approved-by", default="")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    mv = ModelVersions(args.models_dir)
    if args.list or not (args.version or args.rollback):
        print(f"joriy: {mv.current() or 'bazaviy (weights/pcg)'}")
        for v in mv.list():
            print(f"  {v['version']}  darvozalardan o'tdi: {'ha' if v['passed'] else 'yo`q'}  "
                  f"{'[JORIY]' if v['current'] else ('[ilgari tasdiqlangan]' if v['ever_promoted'] else '')}")
        for h in mv.history(10):
            print(f"  · {h['at']}  {h['event']}  {h['version']}  {h['by']}  {h.get('note', '')}")
        return 0
    try:
        if args.rollback:
            restored = mv.rollback(args.approved_by, args.note)
            print(f"orqaga qaytarildi → {restored or 'bazaviy model (weights/pcg)'}")
        else:
            mv.promote(args.version, args.approved_by, args.note)
            print(f"{args.version} JORIY qilindi (tasdiqladi: {args.approved_by.strip()}). Dasturni qayta ishga tushiring.")
    except PromotionError as exc:
        print(f"RAD ETILDI: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
