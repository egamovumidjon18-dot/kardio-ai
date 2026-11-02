"""PCG modelini test to'plamida PRODUCTION yo'li orqali baholash (maqola jadvallari uchun).

    python -m research.evaluate_pcg --data-dir <circor> --weights weights/pcg

Har bir test bemori uchun screening.model.PCGModel.analyze chaqiriladi — ya'ni
ONNX, sifat tekshiruvi, oynalar kelishuvi va noaniq zona aynan platformadagidek.
Natija: weights/pcg/eval_report.{json,md} (bootstrap 95% CI, bola darajasida).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from research.train_pcg import auroc, read_patients, subject_groups
from screening.model import PCGModel, Recording


def run(model: PCGModel, patients: list[dict]) -> list[dict]:
    out = []
    for p in patients:
        # PhysioNet CirCor 1.0.3 documents Child (1–11 years), Adolescent (12–18).
        # Infant starts at 28 days, crossing our existing 29-day guard: exact age is required.
        # https://physionet.org/content/circor-heart-sound/1.0.3/
        bands = {"Child": (365, 12 * 366), "Adolescent": (12 * 365, 19 * 366)}
        ev = model.analyze([Recording(r["location"], r["path"]) for r in p["recordings"]],
                           age_days=p.get("age_days"), age_range_days=bands.get(p.get("age_group")))
        v = ev.value or {}
        out.append({"id": p["id"], "murmur": p["murmur"], "outcome": p["outcome"],
                    "p": v.get("p_murmur"), "p_abnormal": v.get("p_abnormal"),
                    "abstained": ev.abstained, "decision": None if ev.abstained else int(ev.risk.value == "moderate"),
                    "reason": ev.explanation[0] if ev.abstained else ""})
    return out


def metrics(rows: list[dict]) -> dict:
    lab = [r for r in rows if r["murmur"] in ("Present", "Absent") and r["p"] is not None]
    y = np.array([int(r["murmur"] == "Present") for r in lab])
    s = np.array([r["p"] for r in lab], dtype=float)
    dec = [r for r in lab if not r["abstained"]]
    yd = np.array([int(r["murmur"] == "Present") for r in dec])
    dd = np.array([r["decision"] for r in dec])
    tp, fn = int(((dd == 1) & (yd == 1)).sum()), int(((dd == 0) & (yd == 1)).sum())
    tn, fp = int(((dd == 0) & (yd == 0)).sum()), int(((dd == 1) & (yd == 0)).sum())
    n_lab = sum(r["murmur"] in ("Present", "Absent") for r in rows)
    return {
        "n": n_lab, "n_present": int(y.sum()),
        "auroc": auroc(y, s) if len(set(y)) == 2 else float("nan"),
        "abstain_rate": 1 - len(dec) / n_lab if n_lab else float("nan"),
        "sensitivity": tp / (tp + fn) if tp + fn else float("nan"),
        "specificity": tn / (tn + fp) if tn + fp else float("nan"),
        "ppv": tp / (tp + fp) if tp + fp else float("nan"),
        "npv": tn / (tn + fn) if tn + fn else float("nan"),
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
    }


def bootstrap(rows: list[dict], groups: dict[str, str], n: int = 1000, seed: int = 0) -> dict:
    """Bola (subject) darajasida qayta tanlash — bir bolaning ikki ID'si birga."""
    by_g = defaultdict(list)
    for r in rows:
        by_g[groups[r["id"]]].append(r)
    keys = list(by_g)
    rng = np.random.default_rng(seed)
    samples = defaultdict(list)
    for _ in range(n):
        pick = [r for k in rng.choice(keys, len(keys)) for r in by_g[k]]
        for k, v in metrics(pick).items():
            if isinstance(v, float) and not np.isnan(v):
                samples[k].append(v)
    return {k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) for k, v in samples.items()}


def fmt(m: dict, ci: dict, key: str) -> str:
    v = m[key]
    if isinstance(v, float) and np.isnan(v):
        return "—"
    lo, hi = ci.get(key, (float("nan"), float("nan")))
    return f"{v:.3f} ({lo:.3f}–{hi:.3f})" if not np.isnan(lo) else f"{v:.3f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--weights", type=Path, default=Path("weights/pcg"))
    ap.add_argument("--split", default="test")
    ap.add_argument("--bootstrap", type=int, default=1000)
    args = ap.parse_args()

    model = PCGModel.from_dir(args.weights)
    if model is None:
        raise SystemExit(f"{args.weights}/model_card.json topilmadi")
    ids = set(json.loads((args.weights / "split.json").read_text(encoding="utf-8"))[args.split])
    patients = [p for p in read_patients(args.data_dir) if p["id"] in ids]
    groups = {p["id"]: g[0]["id"] for g in subject_groups(patients) for p in g}
    meta = {r["Patient ID"]: r for r in csv.DictReader(open(args.data_dir / "training_data.csv", encoding="utf-8"))}

    rows = run(model, patients)
    overall, ci = metrics(rows), bootstrap(rows, groups, args.bootstrap)
    sub = {}
    for key in ("Age", "Campaign"):
        vals = sorted({meta[r["id"]][key] for r in rows})
        for v in vals:
            part = [r for r in rows if meta[r["id"]][key] == v]
            sub[f"{key}={v}"] = metrics(part)
    reasons = defaultdict(int)
    for r in rows:
        if r["abstained"]:
            key = next((k for k in ("oynalar kelishmadi", "noaniq zona", "sifatli yozuv yo'q") if k in r["reason"]),
                       r["reason"])
            reasons[key] += 1

    report = {"split": args.split, "model": model.card.to_dict(), "overall": overall, "ci95": ci,
              "subgroups": sub, "abstain_reasons": dict(reasons)}
    (args.weights / f"eval_report_{args.split}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=float), encoding="utf-8")

    lines = [f"# PCG modeli — {args.split} to'plami (production yo'li, bola darajasida bootstrap 95% CI)", "",
             f"Model: `{model.card.name}` v{model.card.version} · chegaralar: {model.card.thresholds}", "",
             "| Metrika | Qiymat (95% CI) |", "|---|---|"]
    for k in ("auroc", "sensitivity", "specificity", "ppv", "npv", "abstain_rate"):
        lines.append(f"| {k} | {fmt(overall, ci, k)} |")
    lines += ["", f"Bemorlar: {overall['n']} (shovqin bor: {overall['n_present']}); "
                  f"qaror qilinganlar: TP {overall['tp']}, FN {overall['fn']}, TN {overall['tn']}, FP {overall['fp']}",
              "", "## Kichik guruhlar", "| Guruh | n | AUROC | Sezgirlik | Spetsifiklik | Abstain |", "|---|---|---|---|---|---|"]
    for name, m in sub.items():
        f = lambda x: "—" if isinstance(x, float) and np.isnan(x) else f"{x:.3f}"  # noqa: E731
        lines.append(f"| {name} | {m['n']} | {f(m['auroc'])} | {f(m['sensitivity'])} | {f(m['specificity'])} | {f(m['abstain_rate'])} |")
    lines += ["", "## Abstain sabablari", *[f"- {k}: {v}" for k, v in reasons.items()]]
    (args.weights / f"eval_report_{args.split}.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
