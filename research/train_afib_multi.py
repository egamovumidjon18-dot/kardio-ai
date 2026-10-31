"""Ko'p manbali AFIB / ritm modeli: PTB-XL (Germaniya) + Chapman (Xitoy) + Ningbo (Xitoy) birga o'qitiladi,
ikki TASHQI to'plamda bir marta tekshiriladi: CPSC 2018 (Xitoy, 11 shifoxona) va Georgia (AQSh).

    python -m research.train_afib_multi --ptbxl <ptb-xl> --chapman <chapman> --ningbo <ningbo> --cpsc <cpsc2018> --georgia <georgia>

Sabab: bitta to'plamda o'qitilgan AFIB modeli boshqa mamlakatda yomonlashdi (AUROC: PTB-XL 0.981, Chapman 0.950, Georgia 0.930;
docs/experiments/ecg_georgia_combined.md). Sinflar train_rhythm bilan bir xil: SR, SBRAD, STACH, AFIB, AFL, SVT.

Bo'linish: PTB-XL — rasmiy strat_fold 10 val (bemor darajasida), qolgani o'qitish; Chapman va Ningbo — sinf bo'yicha
stratifikatsiyalangan 85/15. AFIB chegarasi birlashgan val'da sezgirlik ≥ 0.95 bo'ladigan qilib tanlanadi.
CPSC 2018 va Georgia o'qitishda, model tanlashda va chegara tanlashda ISHLATILMAYDI.
Georgia avval faqat eski modellarni baholash uchun ko'rilgan; bu modelga ta'sir qilmagan.

OLDINDAN BELGILANGAN MEZONLAR (natijadan OLDIN yozilgan):
  CPSC 2018 (barcha o'qilgan yozuvlar; AFIB 164889003 bor/yo'q):
    1. AFIB AUROC ≥ 0.95 va bootstrap 95% CI pastki chegarasi ≥ 0.93;
    2. val chegarasida sezgirlik ≥ 0.90 va o'ziga xoslik ≥ 0.92;
    3. AUROC hozirgi ulangan modeldan (weights/ecg) past emas.
  Georgia (ritm yorlig'i bor, stimulyatorsiz yozuvlar; external_georgia_rhythm bilan bir xil yorliq):
    4. AFIB AUROC ≥ 0.95;
    5. sezgirlik ≥ 0.85 va o'ziga xoslik ≥ 0.92;
    6. AFL + SVT + STACH holatlarining AFIB deb belgilangani ≤ 15%.
Hammasi bajarilsa passed=true va model AFIB qarori uchun ulanishi mumkin. Aks holda ulanmaydi.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from ecg.model import ECGModel
from ecg.signal import LEADS_12, N_SAMPLES, TARGET_FS, preprocess, select_leads
from research.external_georgia_rhythm import label as georgia_label, read_record
from research.train_ecg import ECGNet, augment
from research.train_lowef import boot
from research.train_pcg import auroc
from research.train_rhythm import CLASSES, PTB_EXCLUDE, PTB_PRIORITY, load_chapman, load_ptbxl

AF = CLASSES.index("AFIB")
FAST = [CLASSES.index(c) for c in ("AFL", "SVT", "STACH")]
GATES = {"cpsc_auroc": 0.95, "cpsc_auroc_ci_low": 0.93, "cpsc_sensitivity": 0.90, "cpsc_specificity": 0.92,
         "georgia_auroc": 0.95, "georgia_sensitivity": 0.85, "georgia_specificity": 0.92, "georgia_max_fast_called_afib": 0.15}


def ptbxl_folds(d: Path) -> np.ndarray:
    """load_ptbxl bilan aynan bir xil tartibda strat_fold."""
    folds = []
    for r in csv.DictReader(open(d / "ptbxl_database.csv", encoding="utf-8")):
        codes = set(ast.literal_eval(r["scp_codes"]))
        if codes & PTB_EXCLUDE or next((c for k, c in PTB_PRIORITY if k in codes), None) is None:
            continue
        folds.append(int(r["strat_fold"]))
    return np.array(folds)


def load_wfdb_dir(d: Path, cache: Path, labeled: bool) -> dict:
    """Challenge 2021 .hea/.mat papkasi → 100 Hz signal + yorliq. labeled=True: faqat ritm yorlig'i borlar (Georgia qoidasi)."""
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        return {k: z[k] for k in z.files}
    xs, ys, af, ids = [], [], [], []
    for hea in sorted(d.rglob("*.hea")):
        try:
            x, fs, leads, _, dx = read_record(hea)
            x12 = select_leads(x, leads, LEADS_12)
        except Exception:
            continue
        lab = georgia_label(dx)
        if labeled and lab is None:
            continue
        xs.append(preprocess(x12, fs).astype(np.float16))
        ys.append(CLASSES.index(lab) if lab else -1); af.append("164889003" in dx); ids.append(hea.stem)
    out = {"x": np.stack(xs), "y": np.array(ys), "afib": np.array(af), "ids": np.array(ids)}
    np.savez(cache, **out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    for k in ("ptbxl", "chapman", "ningbo", "cpsc", "georgia"):
        ap.add_argument(f"--{k}", type=Path, required=True)
    ap.add_argument("--current", type=Path, default=Path("weights/ecg"))
    ap.add_argument("--out", type=Path, default=Path("weights/ecg_afib_multi"))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rng = np.random.default_rng(a.seed)

    xp, yp = load_ptbxl(a.ptbxl, a.ptbxl.parent / "rhythm_ptbxl_100hz.npz")
    fp = ptbxl_folds(a.ptbxl); assert len(fp) == len(yp)
    xc, yc, _ = load_chapman(a.chapman, a.chapman / "rhythm_chapman_100hz.npz")
    nb = load_wfdb_dir(a.ningbo, a.ningbo / "rhythm_ningbo_100hz.npz", labeled=True)
    xn, yn = nb["x"], nb["y"]

    def split85(y):
        va = np.concatenate([rng.choice(np.where(y == k)[0], int(round(0.15 * (y == k).sum())), replace=False)
                             for k in range(len(CLASSES)) if (y == k).sum() > 0])
        return np.setdiff1d(np.arange(len(y)), va), va

    c_tr, c_va = split85(yc); n_tr, n_va = split85(yn)
    X = np.concatenate([xp[fp != 10], xc[c_tr], xn[n_tr]]); Y = np.concatenate([yp[fp != 10], yc[c_tr], yn[n_tr]])
    XV = np.concatenate([xp[fp == 10], xc[c_va], xn[n_va]]); YV = np.concatenate([yp[fp == 10], yc[c_va], yn[n_va]])
    src_v = np.array(["ptbxl"] * int((fp == 10).sum()) + ["chapman"] * len(c_va) + ["ningbo"] * len(n_va))
    print("o'qitish:", np.bincount(Y, minlength=6).tolist(), "| val:", np.bincount(YV, minlength=6).tolist(), flush=True)

    w = torch.tensor(len(Y) / (6 * np.bincount(Y, minlength=6).clip(min=1)), dtype=torch.float32).clamp(max=10).to(dev)
    model = ECGNet().to(dev)
    model.head = nn.Linear(model.head.in_features, len(CLASSES)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    steps = a.epochs * ((len(Y) + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps)
    crit = nn.CrossEntropyLoss(weight=w)

    @torch.no_grad()
    def probs(x: np.ndarray) -> np.ndarray:
        model.eval(); out = []
        for i in range(0, len(x), 1024):
            out.append(torch.softmax(model(torch.from_numpy(x[i:i + 1024].astype(np.float32)).to(dev)).float(), 1).cpu().numpy())
        return np.concatenate(out)

    best, best_state = -1.0, None
    for ep in range(1, a.epochs + 1):
        model.train(); perm = rng.permutation(len(Y))
        for i in range(0, len(perm), a.batch):
            b = np.sort(perm[i:i + a.batch])
            xb = torch.from_numpy(X[b].astype(np.float32)).to(dev)
            loss = crit(model(augment(xb)).float(), torch.from_numpy(Y[b]).to(dev))
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sched.step()
        pv = probs(XV)
        sc = float(np.mean([auroc((YV == k).astype(int), pv[:, k]) for k in range(6)]))
        print(f"epoch {ep:2d} val o'rtacha AUROC {sc:.4f} | AFIB {auroc((YV == AF).astype(int), pv[:, AF]):.4f}", flush=True)
        if sc > best:
            best, best_state = sc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)

    pv = probs(XV)
    af_v = np.sort(pv[:, AF][YV == AF])
    thr = float(af_v[int(np.floor(0.05 * len(af_v)))])                     # birlashgan val sezgirligi ≥ 0.95
    val = {"mean_auroc": round(best, 4), "afib_auroc": round(auroc((YV == AF).astype(int), pv[:, AF]), 4),
           "afib_auroc_by_source": {s: round(auroc((YV[src_v == s] == AF).astype(int), pv[src_v == s, AF]), 4)
                                    for s in ("ptbxl", "chapman", "ningbo")}}
    print("val:", val, "chegara:", round(thr, 4), flush=True)

    # --- tashqi to'plamlar: bir marta ---
    cur = ECGModel.from_dir(a.current); assert cur is not None
    cur_af = cur.classes.index("AFIB")

    cp = load_wfdb_dir(a.cpsc, a.cpsc / "afib_cpsc_100hz.npz", labeled=False)
    pc = probs(cp["x"])[:, AF]; yc_af = cp["afib"].astype(int)
    p_cur = cur.backend(cp["x"].astype(np.float32))[:, cur_af]
    called = pc >= thr
    cpsc = {"n": int(len(yc_af)), "n_afib": int(yc_af.sum()), "auroc": round(auroc(yc_af, pc), 4), "auroc_ci95": boot(yc_af, pc),
            "sensitivity": round(float(called[yc_af == 1].mean()), 4), "specificity": round(float((~called[yc_af == 0]).mean()), 4),
            "current_model_auroc": round(auroc(yc_af, p_cur), 4),
            "current_model_sensitivity": round(float((p_cur >= cur.high)[yc_af == 1].mean()), 4),
            "current_model_specificity": round(float((p_cur < cur.high)[yc_af == 0].mean()), 4)}

    ga = load_wfdb_dir(a.georgia, a.georgia / "rhythm_georgia_100hz.npz", labeled=True)
    pg = probs(ga["x"]); yg = ga["y"]; yg_af = (yg == AF).astype(int); cg = pg[:, AF] >= thr
    fast = np.isin(yg, FAST)
    georgia = {"n": int(len(yg)), "n_afib": int(yg_af.sum()), "auroc": round(auroc(yg_af, pg[:, AF]), 4),
               "auroc_ci95": boot(yg_af, pg[:, AF]),
               "sensitivity": round(float(cg[yg_af == 1].mean()), 4), "specificity": round(float((~cg[yg_af == 0]).mean()), 4),
               "fast_called_afib": round(float(cg[fast].mean()), 4),
               "called_afib_by_true_class": {c: f"{int(cg[yg == k].sum())}/{int((yg == k).sum())}" for k, c in enumerate(CLASSES)},
               "per_class_auroc": {c: round(auroc((yg == k).astype(int), pg[:, k]), 4) for k, c in enumerate(CLASSES)
                                   if 0 < (yg == k).sum() < len(yg)},
               "current_model_auroc": round(auroc(yg_af, cur.backend(ga["x"].astype(np.float32))[:, cur_af]), 4)}

    checks = {"cpsc_auroc": cpsc["auroc"] >= GATES["cpsc_auroc"], "cpsc_auroc_ci_low": cpsc["auroc_ci95"][0] >= GATES["cpsc_auroc_ci_low"],
              "cpsc_sensitivity": cpsc["sensitivity"] >= GATES["cpsc_sensitivity"],
              "cpsc_specificity": cpsc["specificity"] >= GATES["cpsc_specificity"],
              "cpsc_not_worse_than_current": cpsc["auroc"] >= cpsc["current_model_auroc"],
              "georgia_auroc": georgia["auroc"] >= GATES["georgia_auroc"],
              "georgia_sensitivity": georgia["sensitivity"] >= GATES["georgia_sensitivity"],
              "georgia_specificity": georgia["specificity"] >= GATES["georgia_specificity"],
              "georgia_fast_called_afib": georgia["fast_called_afib"] <= GATES["georgia_max_fast_called_afib"]}
    passed = all(checks.values())
    print(json.dumps({"cpsc2018": cpsc, "georgia": georgia, "checks": checks, "passed": passed}, indent=1, ensure_ascii=False), flush=True)

    a.out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.save(model.state_dict(), a.out / "ecg_afib_multi.pt")
    torch.onnx.export(model, torch.zeros(1, 12, N_SAMPLES), a.out / "ecg_afib_multi.onnx", input_names=["ecg"], output_names=["logits"],
                      dynamic_axes={"ecg": {0: "n"}, "logits": {0: "n"}}, opset_version=17, dynamo=False)
    card = {"name": "ecg_afib_multi", "version": time.strftime("%Y.%m.%d"),
            "task": "12 tarmoqli EKG (10 s, 100 Hz) → ritm: SR / SBRAD / STACH / AFIB / AFL / SVT (softmax)",
            "dataset": "PTB-XL + Chapman-Shaoxing + Ningbo (PhysioNet Challenge 2021)", "dataset_license": "CC-BY-4.0 / CC0",
            "weights": "ecg_afib_multi.onnx", "passed": passed, "gates": GATES, "checks": checks,
            "thresholds": {"classes": CLASSES, "afib_threshold": thr, "fs": TARGET_FS, "n_samples": N_SAMPLES, "leads": list(LEADS_12)},
            "metrics": {"val": val, "external_cpsc2018": cpsc, "external_georgia": georgia},
            "training": {"seed": a.seed, "epochs": a.epochs, "n_train": int(len(Y)), "n_val": int(len(YV)),
                         "split": "PTB-XL fold 10 val; Chapman/Ningbo 85/15 stratifikatsiyalangan; CPSC 2018 va Georgia — faqat tashqi"}}
    (a.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saqlandi:", a.out, "| QABUL:", "O'TDI" if passed else "O'TMADI")


if __name__ == "__main__":
    main()
