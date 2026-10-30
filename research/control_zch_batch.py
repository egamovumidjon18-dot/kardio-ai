"""Salbiy nazorat: ZCHSound'da yozuv-sharoit («blok») izi bormi?

ZCHSound fayllari tashxis bo'yicha ketma-ket yozilgan: normal ZCH0001–0533, ASD 0534–0652, PDA 0653–0684,
PFO 0685–0754, VSD 0755–0941 (fayl raqami bilan tashxis AUROC 1.0). Agar yozuv kuni/xonasi/qurilmasi vaqt bilan
biroz o'zgargan bo'lsa, model kasallikni emas, shu izni o'rganishi mumkin.

Tekshiruv: FAQAT SOG' bolalar ichida (tibbiy farq yo'q) modelga «erta blokdanmi yoki kech blokdanmi?» deb o'rgatiladi.
AUROC ≈ 0.5 bo'lsa — iz yo'q; ≫ 0.5 bo'lsa — yozuvlarda sharoit izi bor va tashxis bo'yicha AUROC'ga ishonib bo'lmaydi.

    python -m research.control_zch_batch --zch-dir <...>/ZCHSound
Natija (2026-10-30): sog'lar ichida erta-vs-kech AUROC ≈ 0.67 (faqat yosh bilan 0.55) → iz bor.
"""
from __future__ import annotations

import argparse
import random
import re
import warnings
from pathlib import Path

import numpy as np
import torch

from research.train_multisite import fit, load_zch
from research.train_pcg import IGNORE, auroc, patient_scores


def _num(item: dict) -> int:
    return int(re.search(r"(\d+)", item["pid"]).group(1))


def _split(items: list[dict], seed: int) -> tuple[list, list, list]:
    rng = random.Random(seed)
    items = items[:]
    rng.shuffle(items)
    n = len(items)
    return items[: int(.6 * n)], items[int(.6 * n): int(.75 * n)], items[int(.75 * n):]


def main() -> None:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--zch-dir", type=Path, required=True)
    ap.add_argument("--seeds", default="7,8,9")
    ap.add_argument("--epochs", type=int, default=25)
    args = ap.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    items, _, _, _ = load_zch(args.zch_dir, 42)
    normals = [it for part in items.values() for it in part if it["dx"] == "NORMAL"]
    cut = int(np.median([_num(it) for it in normals]))
    early = [it for it in normals if _num(it) <= cut]
    late = [it for it in normals if _num(it) > cut]
    ages = np.array([it["age_days"] for it in early + late], dtype=float)
    ya = np.array([0] * len(early) + [1] * len(late))
    a = auroc(ya, np.nan_to_num(ages, nan=np.nanmedian(ages)))
    print(f"sog'lar n={len(normals)}: erta (≤ZCH{cut}) n={len(early)}, kech n={len(late)}; "
          f"«faqat yosh» erta-vs-kech AUROC {max(a, 1 - a):.3f}")

    res = []
    for seed in (int(s) for s in args.seeds.split(",")):
        parts = {"train": [], "val": [], "test": []}
        for grp, y in ((early, 0), (late, 1)):
            for name, part in zip(("train", "val", "test"), _split(grp, seed)):
                parts[name] += [dict(it, murmur=y, outcome=IGNORE) for it in part]
        labels = {it["pid"]: it["murmur"] for p in parts.values() for it in p}
        model, _ = fit(parts["train"], parts["val"], labels, device, args.epochs, seed, log=lambda m: None)
        sc = patient_scores(model, parts["test"], device)
        ids = list(sc)
        res.append(auroc(np.array([labels[i] for i in ids]), np.array([sc[i]["p_murmur"] for i in ids])))
        print(f"  urug' {seed}: sog'lar ichida erta-vs-kech TEST AUROC {res[-1]:.3f} (n={len(ids)})", flush=True)
    print(f"O'RTACHA AUROC {np.mean(res):.3f}  (0.5 = iz yo'q; >0.8 = kuchli sharoit izi)")


if __name__ == "__main__":
    main()
