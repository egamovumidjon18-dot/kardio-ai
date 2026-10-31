"""EchoNext (PhysioNet, shartnoma bilan): 12 tarmoqli EKG → past EF (LVEF ≤ 45%). ONNX eksport.

    python -m research.train_lowef --data-dir C:\\Users\\user\\data\\echonext --out weights/ecg_lowef

OLDINDAN BELGILANGAN QABUL MEZONLARI (natijani ko'rishdan OLDIN yozilgan, keyin o'zgartirilmaydi):
  1. test AUROC ≥ 0.85 va bemor-bootstrap 95% CI pastki chegarasi ≥ 0.82;
  2. EKG modeli faqat jadval belgilari (yosh, jins, yurak urishi, PR, QRS, QTc) bazasidan test'da ≥ 0.05 AUROC yaxshi;
  3. qaror qilingan holatlarda sezgirlik ≥ 0.85 (abstain chegaralari faqat val'da tanlanadi);
  4. abstain ulushi ≤ 0.50;
  5. har bir bo'lim (location_setting) ichida AUROC ≥ 0.75 (model faqat «shoshilinch/statsionar» belgisini o'rganmagan bo'lsin).
Bittasi bajarilmasa — model card'da passed=false va `ecg/low_ef.py` uni YUKLAMAYDI (abstain qoladi).

Tamoyillar: rasmiy split (val/test — har bemorning oxirgi EKG'si); bemor kesishmasi tekshiriladi; signal inference bilan
AYNAN bir xil `ecg.signal.preprocess` (250 Hz → 100 Hz, 10 s); test faqat bir marta baholanadi.
Cheklov: kattalar (≥18), bitta markaz (Columbia), AQSh aholisi. Bolalarga qo'llanmaydi.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from ecg.signal import LEADS_12, N_SAMPLES, TARGET_FS, preprocess
from research.train_ecg import ECGNet, augment, predict
from research.train_pcg import auroc, choose_thresholds

SRC_FS = 250
SPLITS = ("train", "val", "test")
TAB = ["age_at_ecg", "sex", "ventricular_rate", "atrial_rate", "pr_interval", "qrs_duration", "qt_corrected"]
GATES = {"auroc": 0.85, "auroc_ci_low": 0.82, "beats_tabular_by": 0.05, "sensitivity": 0.85, "max_abstain": 0.50,
         "min_auroc_per_location": 0.75}


def read_meta(data_dir: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {s: [] for s in SPLITS}
    with open(data_dir / "echonext_metadata_100k.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["split"] in out:
                out[r["split"]].append(r)
    return out


def to_leads_first(w: np.ndarray) -> np.ndarray:
    """[n, (1,) T, 12] yoki [n, 12, T] → [n, 12, T]."""
    w = np.asarray(w)
    if w.ndim == 4:
        w = w.reshape(w.shape[0], *[d for d in w.shape[1:] if d != 1])
    if w.shape[-1] == 12:
        w = np.swapaxes(w, 1, 2)
    assert w.shape[1] == 12, f"kutilmagan shakl {w.shape}"
    return w


def load_split(data_dir: Path, split: str, cache_dir: Path) -> np.ndarray:
    cache = cache_dir / f"lowef_{split}_100hz.npy"
    if cache.exists():
        return np.load(cache, mmap_mode="r")
    raw = np.load(data_dir / f"EchoNext_{split}_waveforms.npy", mmap_mode="r")
    print(f"{split}: xom shakl {raw.shape} {raw.dtype}", flush=True)
    tmp = cache.with_suffix(".tmp.npy")                      # yarim yozilgan kesh keyingi ishga tushishda ishlatilmasin
    out = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float16, shape=(raw.shape[0], 12, N_SAMPLES))
    for i in range(0, raw.shape[0], 2000):
        w = to_leads_first(raw[i:i + 2000])
        out[i:i + len(w)] = np.stack([preprocess(x, SRC_FS) for x in w]).astype(np.float16)
        print(f"  {split}: {i + len(w)}/{raw.shape[0]}", flush=True)
    out.flush()
    del out
    tmp.replace(cache)
    return np.load(cache, mmap_mode="r")


def tab_features(rows: list[dict]) -> np.ndarray:
    x = np.array([[(1.0 if r["sex"] == "male" else 0.0) if c == "sex" else float(r[c] or "nan") for c in TAB] for r in rows])
    return x


def labels(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    y = np.array([float(r["lvef_lte_45_flag"]) if r["lvef_lte_45_flag"] not in ("", "nan") else np.nan for r in rows])
    return y, ~np.isnan(y)


def boot(y, p, n=1000, seed=0):
    rng = np.random.default_rng(seed); v = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            v.append(auroc(y[i], p[i]))
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]


def decide(y, p, low, high) -> dict:
    ab = (p > low) & (p < high); dec = p >= high; k = ~ab
    tp = int(np.sum(dec & (y == 1) & k)); fn = int(np.sum(~dec & (y == 1) & k))
    tn = int(np.sum(~dec & (y == 0) & k)); fp = int(np.sum(dec & (y == 0) & k))
    return {"abstain_rate": round(float(ab.mean()), 4), "sensitivity": round(tp / max(1, tp + fn), 4),
            "specificity": round(tn / max(1, tn + fp), 4), "ppv": round(tp / max(1, tp + fp), 4),
            "npv": round(tn / max(1, tn + fn), 4), "tp": tp, "fn": fn, "tn": tn, "fp": fp}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("weights/ecg_lowef"))
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--audit-only", action="store_true")
    a = ap.parse_args()
    cache_dir = a.cache_dir or a.data_dir
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    meta = read_meta(a.data_dir)
    pk = {s: {r["patient_key"] for r in meta[s]} for s in SPLITS}
    audit = {"n": {s: len(meta[s]) for s in SPLITS},
             "patient_overlap": {"train_val": len(pk["train"] & pk["val"]), "train_test": len(pk["train"] & pk["test"]),
                                 "val_test": len(pk["val"] & pk["test"])}}
    ys = {s: labels(meta[s]) for s in SPLITS}
    audit["prevalence"] = {s: round(float(np.nanmean(ys[s][0])), 4) for s in SPLITS}
    audit["missing_label"] = {s: int((~ys[s][1]).sum()) for s in SPLITS}
    loc = {}
    for r in meta["train"]:
        if r["lvef_lte_45_flag"] not in ("", "nan"):
            d = loc.setdefault(r["location_setting"], [0, 0]); d[0] += 1; d[1] += int(float(r["lvef_lte_45_flag"]))
    audit["train_prevalence_by_location"] = {k: [n, round(p / n, 3)] for k, (n, p) in loc.items()}
    print(json.dumps(audit, indent=1, ensure_ascii=False), flush=True)
    assert all(v == 0 for v in audit["patient_overlap"].values()), "bemor bir nechta to'plamda!"

    # jadval bazasi (EKG to'lqinisiz): model shundan yaxshi bo'lishi SHART
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    tx = {s: tab_features(meta[s]) for s in SPLITS}
    base = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000))
    m_tr = ys["train"][1]
    base.fit(tx["train"][m_tr], ys["train"][0][m_tr])
    tab_auc = {s: round(auroc(ys[s][0][ys[s][1]], base.predict_proba(tx[s][ys[s][1]])[:, 1]), 4) for s in ("val", "test")}
    print("jadval bazasi AUROC:", tab_auc, flush=True)
    if a.audit_only:
        return

    t0 = time.time()
    X = {s: load_split(a.data_dir, s, cache_dir) for s in SPLITS}
    print(f"signallar tayyor: {time.time() - t0:.0f} s", flush=True)
    tr = np.where(ys["train"][1])[0]
    ytr = torch.from_numpy(ys["train"][0][tr].astype(np.float32))
    vi = np.where(ys["val"][1])[0]; yv = ys["val"][0][vi]

    model = ECGNet().to(dev)
    model.head = nn.Linear(model.head.in_features, 1).to(dev)
    pw = torch.tensor([(1 - ytr.mean()) / ytr.mean()], device=dev).clamp(max=10)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    steps = a.epochs * ((len(tr) + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps)
    scaler = torch.amp.GradScaler("cuda", enabled=dev.type == "cuda")
    crit = nn.BCEWithLogitsLoss(pos_weight=pw)
    best, best_state = -1.0, None
    for ep in range(1, a.epochs + 1):
        model.train(); perm = np.random.permutation(len(tr)); tot = 0.0
        for i in range(0, len(perm), a.batch):
            b = np.sort(tr[perm[i:i + a.batch]])
            xb = torch.from_numpy(np.asarray(X["train"][b], dtype=np.float32)).to(dev)
            yb = torch.from_numpy(ys["train"][0][b].astype(np.float32)).to(dev)
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                loss = crit(model(augment(xb)).float().squeeze(1), yb)
            opt.zero_grad(set_to_none=True); scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sched.step()
            tot += loss.item() * len(b)
        pv = predict(model, np.asarray(X["val"][vi]), dev)[:, 0]
        sc = auroc(yv, pv)
        print(f"epoch {ep:2d} loss {tot / len(tr):.4f} val AUROC {sc:.4f}", flush=True)
        if sc > best:
            best, best_state = sc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)

    pv = predict(model, np.asarray(X["val"][vi]), dev)[:, 0]
    low, high = choose_thresholds(yv.astype(int), pv, 0.90, 0.90)
    ti = np.where(ys["test"][1])[0]; yt = ys["test"][0][ti]
    pt = predict(model, np.asarray(X["test"][ti]), dev)[:, 0]          # test — bir marta
    rows_t = [meta["test"][i] for i in ti]
    by_loc = {}
    for l in sorted({r["location_setting"] for r in rows_t}):
        m = np.array([r["location_setting"] == l for r in rows_t])
        if 0 < yt[m].sum() < m.sum():
            by_loc[l] = {"n": int(m.sum()), "pos": int(yt[m].sum()), "auroc": round(auroc(yt[m], pt[m]), 4)}
    by_sex = {s: round(auroc(yt[np.array([r["sex"] == s for r in rows_t])], pt[np.array([r["sex"] == s for r in rows_t])]), 4)
              for s in ("male", "female")}
    test = {"n": int(len(yt)), "pos": int(yt.sum()), "auroc": round(auroc(yt, pt), 4), "auroc_ci95": boot(yt, pt),
            "tabular_baseline_auroc": tab_auc["test"], **decide(yt, pt, low, high), "by_location": by_loc, "by_sex": by_sex}
    val = {"n": int(len(yv)), "auroc": round(best, 4), **decide(yv, pv, low, high)}
    checks = {
        "auroc": test["auroc"] >= GATES["auroc"],
        "auroc_ci_low": test["auroc_ci95"][0] >= GATES["auroc_ci_low"],
        "beats_tabular": test["auroc"] - tab_auc["test"] >= GATES["beats_tabular_by"],
        "sensitivity": test["sensitivity"] >= GATES["sensitivity"],
        "abstain": test["abstain_rate"] <= GATES["max_abstain"],
        "per_location": all(v["auroc"] >= GATES["min_auroc_per_location"] for v in by_loc.values()),
    }
    passed = all(checks.values())
    print(json.dumps({"val": val, "test": test, "checks": checks, "passed": passed}, indent=1, ensure_ascii=False), flush=True)

    a.out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.save(model.state_dict(), a.out / "ecg_lowef.pt")
    torch.onnx.export(model, torch.zeros(1, 12, N_SAMPLES), a.out / "ecg_lowef.onnx", input_names=["ecg"],
                      output_names=["logit"], dynamic_axes={"ecg": {0: "n"}, "logit": {0: "n"}}, opset_version=17, dynamo=False)
    card = {"name": "ecg_lowef_echonext", "version": time.strftime("%Y.%m.%d"),
            "task": "12 tarmoqli EKG (10 s, 100 Hz) → LVEF ≤ 45% ehtimoli (kattalar)", "dataset": "EchoNext",
            "weights": "ecg_lowef.onnx", "passed": passed, "gates": GATES, "checks": checks,
            "thresholds": {"low": low, "high": high, "fs": TARGET_FS, "n_samples": N_SAMPLES, "leads": list(LEADS_12),
                           "min_age_years": 18},
            "metrics": {"val": val, "test": test}, "audit": audit,
            "training": {"seed": a.seed, "epochs": a.epochs, "split": "EchoNext rasmiy split (val/test: bemorning oxirgi EKG'si)"}}
    (a.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saqlandi:", a.out, "| QABUL:", "O'TDI" if passed else "O'TMADI")


if __name__ == "__main__":
    main()
