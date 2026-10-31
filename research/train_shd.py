"""EchoNext: 12 tarmoqli EKG → tuzilmaviy yurak kasalliklari (ko'p yorliqli). ONNX eksport.

    python -m research.train_shd --data-dir C:\\Users\\user\\data\\echonext --out weights/ecg_shd

Kardioxirurgiya uchun muhim yorliqlar: aorta stenozi, mitral/aorta/trikuspidal regurgitatsiya, o'ng qorincha disfunksiyasi,
o'pka gipertenziyasi (PASP ≥ 45), chap qorincha devori qalinligi ≥ 13 mm, perikard suyuqligi, umumiy SHD. LVEF ≤ 45% yordamchi
yorliq sifatida o'qitiladi, lekin alohida modelda (ecg/low_ef.py) ishlatiladi.

OLDINDAN BELGILANGAN QABUL MEZONLARI — HAR BIR YORLIQ UCHUN ALOHIDA (natijadan OLDIN yozilgan):
  1. test'da musbat holatlar ≥ 30 (aks holda «ma'lumot yetarli emas» — yoqilmaydi);
  2. test AUROC ≥ 0.80 va bootstrap 95% CI pastki chegarasi ≥ 0.75;
  3. jadval belgilari (yosh, jins, yurak urishi, PR, QRS, QTc) bazasidan ≥ 0.03 yaxshi;
  4. ≥ 10 musbatli har bir bo'lim (location_setting) ichida AUROC ≥ 0.70.
Faqat o'tgan yorliqlar model card'da `enabled` ro'yxatiga kiradi; qolganlari ishlatilmaydi (abstain).
Signal keshi train_lowef bilan umumiy (`lowef_{split}_100hz.npy`), split va bemor tekshiruvi o'sha.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from ecg.signal import LEADS_12, N_SAMPLES, TARGET_FS
from research.train_ecg import ECGNet, augment, predict
from research.train_lowef import SPLITS, boot, load_split, read_meta, tab_features
from research.train_pcg import auroc, choose_thresholds

LABELS = {
    "shd": "shd_moderate_or_greater_flag",
    "aortic_stenosis": "aortic_stenosis_moderate_or_greater_flag",
    "aortic_regurgitation": "aortic_regurgitation_moderate_or_greater_flag",
    "mitral_regurgitation": "mitral_regurgitation_moderate_or_greater_flag",
    "tricuspid_regurgitation": "tricuspid_regurgitation_moderate_or_greater_flag",
    "pulmonary_regurgitation": "pulmonary_regurgitation_moderate_or_greater_flag",
    "rv_dysfunction": "rv_systolic_dysfunction_moderate_or_greater_flag",
    "pericardial_effusion": "pericardial_effusion_moderate_large_flag",
    "pulmonary_hypertension": "pasp_gte_45_flag",
    "tr_velocity": "tr_max_gte_32_flag",
    "lv_wall_thickness": "lvwt_gte_13_flag",
    "lvef_le_45": "lvef_lte_45_flag",            # yordamchi; ecg/low_ef.py da alohida
}
AUX = {"lvef_le_45"}
GATES = {"min_test_pos": 30, "auroc": 0.80, "auroc_ci_low": 0.75, "beats_tabular_by": 0.03,
         "min_auroc_per_location": 0.70, "min_pos_per_location": 10}


def label_matrix(rows: list[dict]) -> np.ndarray:
    return np.array([[float(r[c]) for c in LABELS.values()] for r in rows], dtype=np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("weights/ecg_shd"))
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    names = list(LABELS)

    meta = read_meta(a.data_dir)
    pk = {s: {r["patient_key"] for r in meta[s]} for s in SPLITS}
    assert not (pk["train"] & pk["val"]) and not (pk["train"] & pk["test"]) and not (pk["val"] & pk["test"]), "bemor kesishmasi!"
    Y = {s: label_matrix(meta[s]) for s in SPLITS}
    print("test musbatlari:", dict(zip(names, Y["test"].sum(0).astype(int).tolist())), flush=True)

    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    tx = {s: tab_features(meta[s]) for s in SPLITS}
    tab_auc = {}
    for j, n in enumerate(names):
        base = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000))
        base.fit(tx["train"], Y["train"][:, j])
        tab_auc[n] = round(auroc(Y["test"][:, j], base.predict_proba(tx["test"])[:, 1]), 4)
    print("jadval bazasi (test):", tab_auc, flush=True)

    X = {s: load_split(a.data_dir, s, a.data_dir) for s in SPLITS}
    ntr = len(Y["train"])
    yt = torch.from_numpy(Y["train"])
    pw = ((1 - yt.mean(0)) / yt.mean(0).clamp(min=1e-3)).clamp(max=20).to(dev)
    model = ECGNet().to(dev)
    model.head = nn.Linear(model.head.in_features, len(names)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    steps = a.epochs * ((ntr + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps)
    scaler = torch.amp.GradScaler("cuda", enabled=dev.type == "cuda")
    crit = nn.BCEWithLogitsLoss(pos_weight=pw)
    xv = np.asarray(X["val"])
    best, best_state = -1.0, None
    for ep in range(1, a.epochs + 1):
        model.train(); perm = np.random.permutation(ntr); tot = 0.0
        for i in range(0, ntr, a.batch):
            b = np.sort(perm[i:i + a.batch])
            xb = torch.from_numpy(np.asarray(X["train"][b], dtype=np.float32)).to(dev)
            yb = torch.from_numpy(Y["train"][b]).to(dev)
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                loss = crit(model(augment(xb)).float(), yb)
            opt.zero_grad(set_to_none=True); scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sched.step()
            tot += loss.item() * len(b)
        pv = predict(model, xv, dev)
        aucs = [auroc(Y["val"][:, j], pv[:, j]) for j in range(len(names))]
        sc = float(np.nanmean(aucs))
        print(f"epoch {ep:2d} loss {tot / ntr:.4f} val o'rtacha AUROC {sc:.4f}", flush=True)
        if sc > best:
            best, best_state = sc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)

    pv = predict(model, xv, dev)
    pt = predict(model, np.asarray(X["test"]), dev)                          # test — bir marta
    locs = np.array([r["location_setting"] for r in meta["test"]])
    per, enabled, thresholds = {}, [], {}
    for j, n in enumerate(names):
        y, p = Y["test"][:, j], pt[:, j]
        low, high = choose_thresholds(Y["val"][:, j].astype(int), pv[:, j], 0.90, 0.90)
        thresholds[n] = {"low": low, "high": high}
        by_loc = {}
        for l in sorted(set(locs)):
            m = locs == l
            if y[m].sum() >= GATES["min_pos_per_location"] and (y[m] == 0).sum() >= 10:
                by_loc[l] = round(auroc(y[m], p[m]), 4)
        a_ = round(auroc(y, p), 4)
        ci = boot(y, p)
        checks = {"enough_positives": int(y.sum()) >= GATES["min_test_pos"], "auroc": a_ >= GATES["auroc"],
                  "auroc_ci_low": ci[0] >= GATES["auroc_ci_low"], "beats_tabular": a_ - tab_auc[n] >= GATES["beats_tabular_by"],
                  "per_location": all(v >= GATES["min_auroc_per_location"] for v in by_loc.values())}
        ok = all(checks.values())
        per[n] = {"test_pos": int(y.sum()), "auroc": a_, "auroc_ci95": ci, "tabular_auroc": tab_auc[n],
                  "val_auroc": round(auroc(Y["val"][:, j], pv[:, j]), 4), "by_location": by_loc, "checks": checks, "passed": ok}
        if ok and n not in AUX:
            enabled.append(n)
    print(json.dumps(per, indent=1, ensure_ascii=False), flush=True)
    print("YOQILADI:", enabled, flush=True)

    a.out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.save(model.state_dict(), a.out / "ecg_shd.pt")
    torch.onnx.export(model, torch.zeros(1, 12, N_SAMPLES), a.out / "ecg_shd.onnx", input_names=["ecg"], output_names=["logits"],
                      dynamic_axes={"ecg": {0: "n"}, "logits": {0: "n"}}, opset_version=17, dynamo=False)
    card = {"name": "ecg_shd_echonext", "version": time.strftime("%Y.%m.%d"),
            "task": "12 tarmoqli EKG (10 s, 100 Hz) → tuzilmaviy yurak kasalliklari (o'rta yoki og'ir), kattalar",
            "dataset": "EchoNext", "weights": "ecg_shd.onnx", "passed": bool(enabled), "gates": GATES,
            "thresholds": {"labels": names, "enabled": enabled, "per_label": thresholds, "fs": TARGET_FS,
                           "n_samples": N_SAMPLES, "leads": list(LEADS_12), "min_age_years": 18},
            "metrics": {"test": per, "val_mean_auroc": round(best, 4)},
            "training": {"seed": a.seed, "epochs": a.epochs, "split": "EchoNext rasmiy split"}}
    (a.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saqlandi:", a.out)


if __name__ == "__main__":
    main()
