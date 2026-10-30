"""SurgWound (CC BY-SA 4.0) → rasm fayllari + yorliqlar jadvali + SIZIB CHIQISH tekshiruvi.

Kirish: HF «Sonulee/SurgWound» (repo ichidagi *_question.json; rasm base64). Chiqish: <out>/images/*.jpg, <out>/labels.json, <out>/audit.json.
Maqola va README raqamlari mos kelmagani uchun (697/686/722) split'lar o'rtasida bir xil rasm borligini ALOHIDA tekshiramiz:
nom bo'yicha ham, rasm baytlari xeshi bo'yicha ham (turli nomli bir xil rasm).

    python -m research.surgwound_prepare --src C:\\Users\\user\\data\\surgwound\\hf --out C:\\Users\\user\\data\\surgwound\\prep
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

SPLITS = ("train", "val", "test")


def prepare(src: Path, out: Path) -> dict:
    (out / "images").mkdir(parents=True, exist_ok=True)
    rows: dict[str, dict] = {}                 # image_name -> {fields..., sha, splits:set}
    by_hash: dict[str, set] = defaultdict(set)
    for sp in SPLITS:
        for item in json.loads((src / f"{sp}_question.json").read_text(encoding="utf-8")):
            name, raw = item["image_name"], None
            r = rows.setdefault(name, {"labels": {}, "splits": set(), "sha": None})
            r["splits"].add(sp)
            r["labels"][item["field"]] = item["answer"]
            if r["sha"] is None:
                raw = base64.b64decode(item["image"])
                r["sha"] = hashlib.sha256(raw).hexdigest()
                by_hash[r["sha"]].add(name)
                path = out / "images" / f"{Path(name).stem}.jpg"
                if not path.exists():
                    path.write_bytes(raw)
    name_multi = {n: sorted(r["splits"]) for n, r in rows.items() if len(r["splits"]) > 1}
    hash_multi = {h: sorted(ns) for h, ns in by_hash.items() if len(ns) > 1}
    audit = {
        "n_images": len(rows), "n_unique_bytes": len(by_hash),
        "same_name_in_multiple_splits": len(name_multi), "examples_name": dict(list(name_multi.items())[:5]),
        "different_names_same_bytes": len(hash_multi), "examples_hash": list(hash_multi.values())[:5],
        "per_split_names": {sp: sum(1 for r in rows.values() if sp in r["splits"]) for sp in SPLITS},
        "fields": {f: dict(Counter(r["labels"].get(f) for r in rows.values())) for f in sorted({k for r in rows.values() for k in r["labels"]})},
    }
    labels = {n: {"labels": r["labels"], "splits": sorted(r["splits"]), "sha": r["sha"], "file": f"images/{Path(n).stem}.jpg"} for n, r in rows.items()}
    (out / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    return audit


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(prepare(a.src, a.out), ensure_ascii=False, indent=1))
