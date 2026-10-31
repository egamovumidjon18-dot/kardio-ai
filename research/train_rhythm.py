"""Ritm modeli: Chapman–Shaoxing (Xitoy, CC0) da o'qitiladi, PTB-XL (Germaniya, CC-BY 4.0) da TASHQI tekshiriladi.

    python -m research.train_rhythm --chapman C:\\Users\\user\\data\\chapman --ptbxl <ptb-xl papkasi> --out weights/ecg_rhythm

Sabab: PTB-XL'da o'qitilgan AFIB modeli Chapman'da SVT va bo'lmachalar titrashini AFIB deb belgiladi (o'ziga xoslik 0.844,
docs/experiments/ecg_chapman_external.md). Bu model shu tez ritmlarni ALOHIDA sinf sifatida o'rganadi.
Sinflar: SR (sinus, sinus aritmiyasi), SBRAD, STACH, AFIB, AFL (titrash), SVT (SVT, AT, AVNRT, AVRT).

OLDINDAN BELGILANGAN MEZONLAR (PTB-XL tashqi to'plamida; natijadan OLDIN yozilgan):
  1. AFIB'ni qolganlardan ajratish AUROC ≥ 0.95;
  2. Chapman val'da tanlangan AFIB chegarasida (val sezgirligi ≥ 0.95): PTB-XL sezgirligi ≥ 0.85 va o'ziga xosligi ≥ 0.92;
  3. PTB-XL'dagi AFL + SVT + STACH holatlarining AFIB deb belgilangani ≤ 25%;
  4. ≥ 30 holatli har bir sinf uchun bir-qolganlarga qarshi AUROC ≥ 0.85.
Hammasi bajarilsa passed=true. Aks holda model ulanmaydi.
PTB-XL yorlig'i: scp_codes ustuvorligi AFIB > AFLT > SVTAC/PSVT > STACH > SBRAD > SR/SARRH; PACE, BIGU, TRIGU bo'lsa chiqariladi.
"""
from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from ecg.signal import LEADS_12, N_SAMPLES, TARGET_FS, preprocess, read_wfdb, select_leads
from research.train_ecg import ECGNet, augment, predict
from research.train_lowef import boot
from research.train_pcg import auroc

CLASSES = ["SR", "SBRAD", "STACH", "AFIB", "AFL", "SVT"]
CHAPMAN_MAP = {"SR": "SR", "SA": "SR", "SB": "SBRAD", "ST": "STACH", "AFIB": "AFIB", "AF": "AFL",
               "SVT": "SVT", "AT": "SVT", "AVNRT": "SVT", "AVRT": "SVT", "SAAWR": "SVT"}
PTB_PRIORITY = [("AFIB", "AFIB"), ("AFLT", "AFL"), ("SVTAC", "SVT"), ("PSVT", "SVT"), ("STACH", "STACH"),
                ("SBRAD", "SBRAD"), ("SR", "SR"), ("SARRH", "SR")]
PTB_EXCLUDE = {"PACE", "BIGU", "TRIGU"}
GATES = {"afib_auroc": 0.95, "afib_sensitivity": 0.85, "afib_specificity": 0.92, "max_fast_called_afib": 0.25,
         "min_class_auroc": 0.85, "min_class_n": 30}


def load_chapman(d: Path, cache: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import pandas as pd
    diag = pd.read_excel(d / "Diagnostics.xlsx").set_index("FileName")
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        return z["x"], z["y"], z["age"]
    zf = zipfile.ZipFile(d / "ECGData.zip")
    xs, ys, ages = [], [], []
    for name in zf.namelist():
        fid = Path(name).stem
        if not name.endswith(".csv") or fid not in diag.index or diag.loc[fid, "Rhythm"] not in CHAPMAN_MAP:
            continue
        x = pd.read_csv(io.BytesIO(zf.read(name))).to_numpy(dtype=np.float32).T / 1000.0
        if not np.isfinite(x).all() or np.abs(x).max() == 0:
            continue
        xs.append(preprocess(x, 500).astype(np.float16))
        ys.append(CLASSES.index(CHAPMAN_MAP[diag.loc[fid, "Rhythm"]])); ages.append(float(diag.loc[fid, "PatientAge"]))
    x, y, age = np.stack(xs), np.array(ys), np.array(ages)
    np.savez(cache, x=x, y=y, age=age)
    return x, y, age


def load_ptbxl(d: Path, cache: Path) -> tuple[np.ndarray, np.ndarray]:
    if cache.exists():
        z = np.load(cache)
        return z["x"], z["y"]
    xs, ys = [], []
    for r in csv.DictReader(open(d / "ptbxl_database.csv", encoding="utf-8")):
        codes = set(ast.literal_eval(r["scp_codes"]))
        if codes & PTB_EXCLUDE:
            continue
        lab = next((c for k, c in PTB_PRIORITY if k in codes), None)
        if lab is None:
            continue
        sig, fs, names = read_wfdb(d / r["filename_lr"])
        xs.append(preprocess(select_leads(sig, names, LEADS_12), fs).astype(np.float16)); ys.append(CLASSES.index(lab))
    x, y = np.stack(xs), np.array(ys)
    np.savez(cache, x=x, y=y)
    return x, y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapman", type=Path, required=True)
    ap.add_argument("--ptbxl", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("weights/ecg_rhythm"))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    xc, yc, _ = load_chapman(a.chapman, a.chapman / "rhythm_chapman_100hz.npz")
    xp, yp = load_ptbxl(a.ptbxl, a.ptbxl.parent / "rhythm_ptbxl_100hz.npz")
    print("Chapman:", np.bincount(yc, minlength=6).tolist(), "| PTB-XL:", np.bincount(yp, minlength=6).tolist(), flush=True)

    rng = np.random.default_rng(a.seed)                    # Chapman: har bemorda bitta EKG → stratifikatsiyalangan 85/15
    va = np.concatenate([rng.choice(np.where(yc == k)[0], max(1, int(0.15 * (yc == k).sum())), replace=False) for k in range(6)])
    tr = np.setdiff1d(np.arange(len(yc)), va)
    xt, yt = torch.from_numpy(xc[tr].astype(np.float32)), torch.from_numpy(yc[tr])
    w = torch.tensor(len(tr) / (6 * np.bincount(yc[tr], minlength=6).clip(min=1)), dtype=torch.float32).clamp(max=10).to(dev)
    model = ECGNet().to(dev)
    model.head = nn.Linear(model.head.in_features, len(CLASSES)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    steps = a.epochs * ((len(tr) + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps)
    crit = nn.CrossEntropyLoss(weight=w)

    def probs(x):                                           # softmax ehtimolliklar
        lg = predict(model, x, dev)                         # predict sigmoid qaytaradi → logit'ga qaytaramiz
        lg = np.log(np.clip(lg, 1e-7, 1 - 1e-7) / np.clip(1 - lg, 1e-7, 1))
        e = np.exp(lg - lg.max(1, keepdims=True))
        return e / e.sum(1, keepdims=True)

    best, best_state = -1.0, None
    for ep in range(1, a.epochs + 1):
        model.train(); perm = torch.randperm(len(tr))
        for i in range(0, len(perm), a.batch):
            b = perm[i:i + a.batch]
            loss = crit(model(augment(xt[b].to(dev))).float(), yt[b].to(dev))
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sched.step()
        pv = probs(xc[va].astype(np.float32))
        sc = float(np.mean([auroc((yc[va] == k).astype(int), pv[:, k]) for k in range(6)]))
        print(f"epoch {ep:2d} Chapman val o'rtacha AUROC {sc:.4f}", flush=True)
        if sc > best:
            best, best_state = sc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)

    pv = probs(xc[va].astype(np.float32))
    af_v = pv[:, 3][yc[va] == 3]
    thr = float(np.sort(af_v)[int(np.floor(0.05 * len(af_v)))])           # val sezgirligi ≥ 0.95
    pe = probs(xp.astype(np.float32))                                      # PTB-XL — bir marta
    y_af = (yp == 3).astype(int); called = pe[:, 3] >= thr
    fast = np.isin(yp, [CLASSES.index(c) for c in ("AFL", "SVT", "STACH")])
    per_class = {c: {"n": int((yp == k).sum()), "auroc": round(auroc((yp == k).astype(int), pe[:, k]), 4)}
                 for k, c in enumerate(CLASSES) if 0 < (yp == k).sum() < len(yp)}
    ext = {"n": int(len(yp)), "n_afib": int(y_af.sum()), "afib_auroc": round(auroc(y_af, pe[:, 3]), 4),
           "afib_auroc_ci95": boot(y_af, pe[:, 3]), "afib_threshold": thr,
           "afib_sensitivity": round(float(called[y_af == 1].mean()), 4), "afib_specificity": round(float((~called[y_af == 0]).mean()), 4),
           "fast_rhythms_called_afib": round(float(called[fast].mean()), 4), "n_fast": int(fast.sum()),
           "called_afib_by_true_class": {c: f"{int(called[yp == k].sum())}/{int((yp == k).sum())}" for k, c in enumerate(CLASSES)},
           "per_class": per_class,
           "confusion": {c: dict(zip(CLASSES, np.bincount(pe[yp == k].argmax(1), minlength=6).tolist())) for k, c in enumerate(CLASSES)}}
    checks = {"afib_auroc": ext["afib_auroc"] >= GATES["afib_auroc"],
              "afib_sensitivity": ext["afib_sensitivity"] >= GATES["afib_sensitivity"],
              "afib_specificity": ext["afib_specificity"] >= GATES["afib_specificity"],
              "fast_called_afib": ext["fast_rhythms_called_afib"] <= GATES["max_fast_called_afib"],
              "per_class": all(v["auroc"] >= GATES["min_class_auroc"] for v in per_class.values() if v["n"] >= GATES["min_class_n"])}
    passed = all(checks.values())
    print(json.dumps({"external_ptbxl": ext, "checks": checks, "passed": passed}, indent=1, ensure_ascii=False), flush=True)

    a.out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.save(model.state_dict(), a.out / "ecg_rhythm.pt")
    torch.onnx.export(model, torch.zeros(1, 12, N_SAMPLES), a.out / "ecg_rhythm.onnx", input_names=["ecg"], output_names=["logits"],
                      dynamic_axes={"ecg": {0: "n"}, "logits": {0: "n"}}, opset_version=17, dynamo=False)
    card = {"name": "ecg_rhythm_chapman", "version": time.strftime("%Y.%m.%d"),
            "task": "12 tarmoqli EKG (10 s, 100 Hz) → ritm: SR / SBRAD / STACH / AFIB / AFL / SVT", "dataset": "Chapman-Shaoxing",
            "weights": "ecg_rhythm.onnx", "passed": passed, "gates": GATES, "checks": checks,
            "thresholds": {"classes": CLASSES, "afib_threshold": thr, "fs": TARGET_FS, "n_samples": N_SAMPLES, "leads": list(LEADS_12)},
            "metrics": {"chapman_val_mean_auroc": round(best, 4), "external_ptbxl": ext},
            "training": {"seed": a.seed, "epochs": a.epochs, "split": "Chapman 85/15 stratifikatsiyalangan; tashqi: PTB-XL to'liq"}}
    (a.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saqlandi:", a.out, "| QABUL:", "O'TDI" if passed else "O'TMADI")


if __name__ == "__main__":
    main()
