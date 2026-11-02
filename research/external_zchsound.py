"""Tashqi validatsiya: ZCHSound (Zhejiang Univ. bolalar shifoxonasi) — haqiqiy TYN tashxislari.

Jia W et al. ZCHSound: Open-Source ZJU Paediatric Heart Sound Database With Congenital
Heart Disease. IEEE TBME 2024;71(8):2278-2286. doi:10.1109/TBME.2023.3348800
Ma'lumot: https://github.com/WeiJieOvO/ZCHSound-Dataset (ZCHSound.zip)

    python -m research.external_zchsound --data-dir <...>/ZCHSound --weights weights/pcg

CirCor'da SHOVQIN aniqlashga o'qitilgan model hech qanday qayta o'qitishsiz,
production yo'li (PCGModel.analyze) orqali TYN vs NORMAL ga qo'llanadi.
Toza va shovqinli to'plamlar alohida baholanadi (abstain sinovi).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from research.metrics import auroc
from screening.model import PCGModel, Recording

SUBSETS = {
    "clean": ("Clean Heartsound Data Details.csv", "clean Heartsound Data", ","),
    "noisy": ("Noise Heartsound Data Details.csv", "Noise Heartsound Data Details", ";"),
}


def read_subset(data_dir: Path, subset: str) -> list[dict]:
    csv_name, wav_dir, delim = SUBSETS[subset]
    rows = list(csv.DictReader(open(data_dir / csv_name, encoding="utf-8-sig"), delimiter=delim))
    out = []
    for r in rows:
        path = data_dir / wav_dir / r["fileName"].strip()
        if path.exists():
            out.append({"id": r["fileName"].strip(), "dx": r["diagnosis"].strip().upper(),
                        "subject": (r.get("subject") or r["fileName"]).strip(),   # mahalliy eksport: bola ID
                        "age_days": float(r["age(days)"]) if r["age(days)"].strip() else None, "path": path})
    return out


def age_band(days: float | None) -> str:
    if days is None:
        return "noma'lum"
    if days <= 28:
        return "neonat (≤28 kun)"
    if days < 365:
        return "go'dak (<1 yosh)"
    return "bola (≥1 yosh)"


def evaluate(model: PCGModel, items: list[dict]) -> list[dict]:
    rows = []
    for it in items:
        try:
            ev = model.analyze([Recording("UNK", it["path"])], age_days=it.get("age_days"))
        except ValueError as exc:                     # buzilgan WAV
            rows.append({**it, "p": None, "abstained": True, "decision": None, "reason": str(exc)})
            continue
        v = ev.value or {}
        rows.append({**it, "p": v.get("p_murmur"), "abstained": ev.abstained,
                     "decision": None if ev.abstained else int(ev.risk.value == "moderate"),
                     "reason": ev.explanation[0] if ev.abstained else ""})
    return rows


def summarize(rows: list[dict], positive: set[str], n_boot: int = 1000, seed: int = 0) -> dict:
    rows = [r for r in rows if r["dx"] in positive or r["dx"] == "NORMAL"]
    y_all = np.array([int(r["dx"] in positive) for r in rows])
    scored = [r for r in rows if r["p"] is not None]
    y = np.array([int(r["dx"] in positive) for r in scored])
    s = np.array([r["p"] for r in scored], dtype=float)
    dec = [r for r in rows if not r["abstained"]]
    yd = np.array([int(r["dx"] in positive) for r in dec])
    dd = np.array([r["decision"] for r in dec])

    def stats(yv, sv, ydv, ddv):
        tp, fn = int(((ddv == 1) & (ydv == 1)).sum()), int(((ddv == 0) & (ydv == 1)).sum())
        tn, fp = int(((ddv == 0) & (ydv == 0)).sum()), int(((ddv == 1) & (ydv == 0)).sum())
        return {"auroc": auroc(yv, sv) if len(set(yv.tolist())) == 2 else float("nan"),
                "sensitivity": tp / (tp + fn) if tp + fn else float("nan"),
                "specificity": tn / (tn + fp) if tn + fp else float("nan"),
                "tp": tp, "fn": fn, "tn": tn, "fp": fp}

    out = stats(y, s, yd, dd)
    out.update(n=len(rows), n_positive=int(y_all.sum()),
               abstain_rate=1 - len(dec) / len(rows) if rows else float("nan"))
    rng = np.random.default_rng(seed)
    boots = defaultdict(list)
    idx_s, idx_d = np.arange(len(scored)), np.arange(len(dec))
    for _ in range(n_boot):
        bs, bd = rng.choice(idx_s, len(idx_s)), rng.choice(idx_d, len(idx_d))
        b = stats(y[bs], s[bs], yd[bd], dd[bd])
        for k in ("auroc", "sensitivity", "specificity"):
            if not np.isnan(b[k]):
                boots[k].append(b[k])
    out["ci95"] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in boots.items()}
    return out


def per_dx(rows: list[dict]) -> dict:
    res = {}
    for dx in sorted({r["dx"] for r in rows}):
        part = [r for r in rows if r["dx"] == dx]
        dec = [r for r in part if not r["abstained"]]
        flagged = sum(r["decision"] == 1 for r in dec)
        res[dx] = {"n": len(part), "abstained": len(part) - len(dec), "flagged": flagged,
                   "flag_rate": flagged / len(dec) if dec else float("nan"),
                   "median_p": float(np.median([r["p"] for r in part if r["p"] is not None])) if part else float("nan")}
    return res


def f(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def ci(m: dict, k: str) -> str:
    lo_hi = m["ci95"].get(k)
    return f"{f(m[k])} ({lo_hi[0]:.3f}–{lo_hi[1]:.3f})" if lo_hi else f(m[k])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--weights", type=Path, default=Path("weights/pcg"))
    ap.add_argument("--bootstrap", type=int, default=1000)
    args = ap.parse_args()
    model = PCGModel.from_dir(args.weights)
    if model is None:
        raise SystemExit(f"{args.weights}/model_card.json topilmadi")

    chd_all = {"ASD", "VSD", "PDA", "PFO"}
    chd_no_pfo = {"ASD", "VSD", "PDA"}
    report, lines = {"model": model.card.to_dict()}, [
        "# Tashqi validatsiya — ZCHSound (Xitoy, haqiqiy TYN tashxislari)", "",
        f"Model: `{model.card.name}` v{model.card.version}, CirCor'da o'qitilgan, **qayta o'qitishsiz**. "
        f"Chegaralar: {model.card.thresholds}", ""]
    for subset in ("clean", "noisy"):
        rows = evaluate(model, read_subset(args.data_dir, subset))
        main_m = summarize(rows, chd_all, args.bootstrap)
        nopfo = summarize(rows, chd_no_pfo, args.bootstrap)
        by_dx = per_dx(rows)
        by_age = {band: summarize([r for r in rows if age_band(r["age_days"]) == band], chd_all, 0)
                  for band in sorted({age_band(r["age_days"]) for r in rows})}
        reasons = defaultdict(int)
        for r in rows:
            if r["abstained"]:
                reasons[next((k for k in ("oynalar kelishmadi", "noaniq zona", "sifatli yozuv yo'q", "WAV")
                              if k in r["reason"]), r["reason"][:40])] += 1
        report[subset] = {"chd_vs_normal": main_m, "chd_without_pfo": nopfo, "per_diagnosis": by_dx,
                          "by_age": by_age, "abstain_reasons": dict(reasons)}
        lines += [f"## {'Toza' if subset == 'clean' else 'Shovqinli'} to'plam ({len(rows)} bola)", "",
                  "| Taqqoslash | n (TYN) | AUROC (95% CI) | Sezgirlik (95% CI) | Spetsifiklik (95% CI) | Abstain |",
                  "|---|---|---|---|---|---|"]
        for name, m in (("Barcha TYN vs normal", main_m), ("TYN (PFO'siz) vs normal", nopfo)):
            lines.append(f"| {name} | {m['n']} ({m['n_positive']}) | {ci(m, 'auroc')} | {ci(m, 'sensitivity')} | "
                         f"{ci(m, 'specificity')} | {f(m['abstain_rate'])} |")
        lines += ["", "| Tashxis | n | Abstain | 'Shovqin bor' deb belgilangan | Median p |", "|---|---|---|---|---|"]
        for dx, d in by_dx.items():
            lines.append(f"| {dx} | {d['n']} | {d['abstained']} | {d['flagged']} ({f(d['flag_rate'])}) | {f(d['median_p'])} |")
        lines += ["", "| Yosh | n (TYN) | AUROC | Sezgirlik | Spetsifiklik | Abstain |", "|---|---|---|---|---|---|"]
        for band, m in by_age.items():
            lines.append(f"| {band} | {m['n']} ({m['n_positive']}) | {f(m['auroc'])} | {f(m['sensitivity'])} | "
                         f"{f(m['specificity'])} | {f(m['abstain_rate'])} |")
        lines += ["", "Abstain sabablari: " + (", ".join(f"{k}: {v}" for k, v in reasons.items()) or "—"), ""]

    (args.weights / "external_zchsound.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=float),
                                                         encoding="utf-8")
    (args.weights / "external_zchsound.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
