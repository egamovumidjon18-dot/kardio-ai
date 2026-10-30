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


def _auroc(y: list[int], s: list[float]) -> float:
    """Rang asosidagi AUROC (teng qiymatlar o'rtacha rang bilan)."""
    n_pos = sum(y)
    n_neg = len(y) - n_pos
    order = sorted(range(len(s)), key=lambda i: s[i])
    ranks = [0.0] * len(s)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and s[order[j + 1]] == s[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return (sum(r for r, v in zip(ranks, y) if v) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def collection_confound(children: dict[str, tuple[str, str, str]], min_n: int = 20, min_class: int = 5):
    """Yig'ish tartibi tashxisni «bashorat qilib» qo'ymayaptimi? (ZCHSound'dagi xato takrorlanmasin.)

    children: epizod → (yaratilgan vaqt ISO, tashxis, stetoskop modeli).
    Ikkita belgi: (1) yozuv TARTIBI bilan tashxis AUROC'i; (2) har bir qurilma faqat bitta sinfdan iboratmi.
    Model sinflarni yurak tovushidan emas, yozilgan kun yoki qurilma izidan ajratib olishi mumkin.
    Yetarli ma'lumot bo'lmasa — None.
    """
    pos = sum(dx != "NORMAL" for _, dx, _ in children.values())
    if len(children) < min_n or min(pos, len(children) - pos) < min_class:
        return None
    ordered = sorted(children.values(), key=lambda t: t[0])
    y = [int(dx != "NORMAL") for _, dx, _ in ordered]
    a = _auroc(y, [float(i) for i in range(len(y))])
    a = max(a, 1 - a)
    by_dev: dict[str, list[int]] = {}
    for _, dx, dev in children.values():
        if dev:
            by_dev.setdefault(dev, []).append(int(dx != "NORMAL"))
    big = {d: v for d, v in by_dev.items() if len(v) >= min_class}
    pure = {d: round(max(sum(v), len(v) - sum(v)) / len(v), 2) for d, v in big.items()}
    majority = {d: sum(v) * 2 > len(v) for d, v in big.items()}
    device_split = len(big) >= 2 and all(p >= 0.95 for p in pure.values()) and len(set(majority.values())) == 2
    return {"order_auroc": round(a, 3), "n": len(children), "order_warn": a >= 0.85,
            "device_purity": pure, "device_warn": device_split}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--recordings", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    csv_name, wav_dir, _ = SUBSETS["clean"]
    (args.out / wav_dir).mkdir(parents=True, exist_ok=True)
    store = SqliteEpisodeStore(args.db)
    rows, skipped, children = [], Counter(), {}
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
            children[eid] = (ep.created_at, dx.value, rec.value.get("device", ""))
    with open(args.out / csv_name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["fileName", "gender", "age(days)", "diagnosis", "subject", "location", "device"])
        w.writeheader()
        w.writerows(rows)
    subjects = {r["subject"] for r in rows}
    print(f"{len(rows)} yozuv, {len(subjects)} bola → {args.out}")
    print("tashxislar (bola):", dict(Counter({r['subject']: r['diagnosis'] for r in rows}.values())))
    if skipped:
        print("o'tkazib yuborildi:", dict(skipped))
    check = collection_confound(children)
    if check is None:
        print("yig'ish tartibi tekshiruvi: ma'lumot yetarli emas (kamida 20 bola, har sinfdan 5 tadan)")
    else:
        print(f"yig'ish tartibi tekshiruvi: tartib bilan tashxis AUROC {check['order_auroc']:.2f} (≥0.85 — xavfli); "
              f"qurilma sofligi {check['device_purity'] or '—'}")
        if check["order_warn"]:
            print("DIQQAT: yozuvlar tashxis bo'yicha deyarli ketma-ket yig'ilgan. Model kasallikni emas, yozilgan kun yoki "
                  "sharoit izini o'rganib olishi mumkin (ZCHSound'da shunday bo'lgan). Sog'lar va kasallarni bir xil "
                  "kunlarda, aralash tartibda yozing; bu ma'lumotdagi natijalarga ishonmang.")
        if check["device_warn"]:
            print("DIQQAT: har bir stetoskop faqat bitta sinfni yozgan (sog' yoki kasal). Model qurilmani o'rganishi "
                  "mumkin. Ikkala sinfni bir xil qurilmalarda yozing.")


if __name__ == "__main__":
    main()
