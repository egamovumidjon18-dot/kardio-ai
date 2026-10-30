"""Mahalliy yig'ilgan ma'lumotni eksport qilish (moslashtirish / fine-tuning uchun).

Faqat (1) rozilik bilan saqlangan yozuvi va (2) ExoKG tashxisi bor epizodlar olinadi.
Chiqish ZCHSound "clean" tuzilishida, shuning uchun research/adapt_zchsound.py
uni o'zgarishsiz o'qiydi (bitta bolaning yozuvlari `subject` ustuni orqali birga qoladi):

    python -m research.export_local --db cardiopath.db --recordings <papka> --out <eksport>
    python -m research.adapt_zchsound --data-dir <eksport> --base <circor_base> --out docs/experiments/local
"""
from __future__ import annotations

import argparse
import csv
import shutil
from collections import Counter
from pathlib import Path

from core.store import SqliteEpisodeStore
from research.external_zchsound import SUBSETS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--recordings", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    csv_name, wav_dir, _ = SUBSETS["clean"]
    (args.out / wav_dir).mkdir(parents=True, exist_ok=True)
    store = SqliteEpisodeStore(args.db)
    rows, skipped = [], Counter()
    for eid in store.ids():
        ep = store.get(eid)
        rec, dx = ep.latest("research.recordings"), ep.latest("workup.echo_dx")
        if rec is None:
            continue
        if dx is None:
            skipped["ExoKG tashxisi yo'q"] += 1
            continue
        for f in rec.value["files"]:
            src = args.recordings / eid / f["file"]
            if not src.exists():
                skipped["fayl topilmadi"] += 1
                continue
            name = f"{eid[:12]}_{f['file']}"
            shutil.copyfile(src, args.out / wav_dir / name)
            age = rec.value.get("age_days")
            rows.append({"fileName": name, "gender": "", "age(days)": "" if age is None else round(age),
                         "diagnosis": dx.value, "subject": eid, "location": f["location"],
                         "device": rec.value.get("device", "")})
    with open(args.out / csv_name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["fileName", "gender", "age(days)", "diagnosis", "subject", "location", "device"])
        w.writeheader()
        w.writerows(rows)
    subjects = {r["subject"] for r in rows}
    print(f"{len(rows)} yozuv, {len(subjects)} bola → {args.out}")
    print("tashxislar (bola):", dict(Counter({r['subject']: r['diagnosis'] for r in rows}.values())))
    if skipped:
        print("o'tkazib yuborildi:", dict(skipped))


if __name__ == "__main__":
    main()
