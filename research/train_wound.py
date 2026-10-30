"""Yara rasmi: «infeksiya xavfi o'rta/yuqori» (SurgWound) — 5-qatlamli o'zaro tekshiruv + SHORTCUT/konfaund tekshiruvlari.

Yorliq: Infection Risk Assessment ∈ {Medium, High} → 1 (113 ta), Low → 0 (573 ta). Barcha 686 rasm bitta jadvalda,
5 qatlamli stratifikatsiyalangan CV; har rasm FAQAT o'zi tegmagan qatlamda baholanadi (OOF).
Tekshiruvlar (o'qitishdan KEYIN emas, SHU YERDA, natijaga qaramasdan):
  1. metadata-baza: faqat rasm o'lchami/fayl hajmi/joylashuv bilan AUROC (manba-konfaund: ijtimoiy tarmoq vs klinika);
  2. aralashtirilgan yorliq nazorati (≈0.5 bo'lishi kerak);
  3. bootstrap 95% CI;
  4. joylashuv (Wound Location) bo'yicha qatlamlar.
Eslatma: bemor/manba identifikatori yo'q, shuning uchun bir bemorning yaqin rasmlari turli qatlamlarga tushishi mumkin — natija
OPTIMISTIK chegara hisoblanadi. Sternotomiya rasmlari yo'q (qorin, to'piq, yuz va h.k.).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

POS = {"Medium", "High"}
SIZE = 288


def _auroc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    r = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def boot_ci(y, p, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    y, p, vals = np.asarray(y), np.asarray(p), []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            vals.append(_auroc(y[i], p[i]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def load(prep: Path):
    from PIL import Image
    lab = json.loads((prep / "labels.json").read_text(encoding="utf-8"))
    names = sorted(lab)
    y = np.array([int(lab[n]["labels"].get("Infection Risk Assessment") in POS) for n in names])
    imgs, meta = [], []
    for n in names:
        f = prep / lab[n]["file"]
        im = Image.open(f).convert("RGB")
        meta.append([im.width, im.height, im.width / im.height, f.stat().st_size, f.stat().st_size / (im.width * im.height)])
        imgs.append(np.asarray(im.resize((SIZE, SIZE), Image.BILINEAR)))
    loc = [lab[n]["labels"].get("Wound Location") or "null" for n in names]
    return names, y, np.stack(imgs), np.array(meta, dtype=float), loc


def metadata_baseline(y, meta, loc, folds):
    """Rasm ichidagi mazmunsiz: o'lcham/hajm + joylashuv. Agar bu yuqori bo'lsa — model shortcut'ga tayanishi mumkin."""
    from sklearn.ensemble import GradientBoostingClassifier
    cats = sorted(set(loc))
    X = np.hstack([meta, np.array([[l == c for c in cats] for l in loc], dtype=float)])
    oof = np.zeros(len(y))
    for tr, te in folds:
        m = GradientBoostingClassifier(random_state=0).fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    return _auroc(y, oof)


def train_fold(imgs, y, tr, te, epochs, seed, arch):
    import timm
    import torch
    import torch.nn.functional as F
    torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = timm.create_model(arch, pretrained=True, num_classes=1).to(dev)
    cfg = model.pretrained_cfg
    mean = torch.tensor(cfg["mean"], device=dev).view(1, 3, 1, 1); std = torch.tensor(cfg["std"], device=dev).view(1, 3, 1, 1)

    def prep(batch, train):
        x = torch.from_numpy(batch).to(dev).permute(0, 3, 1, 2).float() / 255
        if train:                                                    # rang o'zgartirilmaydi (eritema rangi — belgi)
            if random.random() < 0.5: x = x.flip(3)
            if random.random() < 0.5: x = x.flip(2)
            k = random.choice([0, 1, 2, 3]); x = torch.rot90(x, k, (2, 3))
            s = random.uniform(0.7, 1.0); c = int(SIZE * s); i, j = random.randint(0, SIZE - c), random.randint(0, SIZE - c)
            x = F.interpolate(x[:, :, i:i + c, j:j + c], size=(SIZE, SIZE), mode="bilinear", align_corners=False)
        return (x - mean) / std

    opt = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-2)
    steps = epochs * ((len(tr) + 31) // 32); sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-4, total_steps=steps)
    pw = torch.tensor((y[tr] == 0).sum() / max(1, (y[tr] == 1).sum()), device=dev)
    scaler = torch.amp.GradScaler(enabled=dev == "cuda")
    for _ in range(epochs):
        model.train(); order = np.random.permutation(tr)
        for b in range(0, len(order), 32):
            idx = order[b:b + 32]
            if len(idx) < 2: continue
            with torch.autocast(dev, enabled=dev == "cuda"):
                loss = F.binary_cross_entropy_with_logits(model(prep(imgs[idx], True)).squeeze(1), torch.from_numpy(y[idx]).float().to(dev), pos_weight=pw)
            opt.zero_grad(); scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sched.step()
    model.eval(); out = []
    with torch.no_grad():
        for b in range(0, len(te), 64):
            xb = prep(imgs[te[b:b + 64]], False)
            with torch.autocast(dev, enabled=dev == "cuda"):
                p = (model(xb).squeeze(1).float().sigmoid() + model(xb.flip(3)).squeeze(1).float().sigmoid()) / 2
            out.append(p.cpu().numpy())
    return np.concatenate(out), model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arch", default="efficientnet_b0")
    ap.add_argument("--epochs", type=int, default=12)
    a = ap.parse_args()
    from sklearn.model_selection import StratifiedKFold
    a.out.mkdir(parents=True, exist_ok=True)
    names, y, imgs, meta, loc = load(a.prep)
    folds = list(StratifiedKFold(5, shuffle=True, random_state=0).split(np.zeros(len(y)), y))
    res = {"n": int(len(y)), "n_pos": int(y.sum()), "arch": a.arch, "epochs": a.epochs}
    res["metadata_baseline_auroc"] = metadata_baseline(y, meta, loc, folds)
    print("metadata-baza AUROC:", round(res["metadata_baseline_auroc"], 3), flush=True)
    oof = np.zeros(len(y))
    for k, (tr, te) in enumerate(folds):
        oof[te], _ = train_fold(imgs, y, tr, te, a.epochs, k, a.arch)
        print(f"qatlam {k}: AUROC {_auroc(y[te], oof[te]):.3f}", flush=True)
    res["oof_auroc"], res["oof_auroc_ci95"] = _auroc(y, oof), boot_ci(y, oof)
    rng = np.random.default_rng(1); ys = y.copy(); rng.shuffle(ys)                    # aralashtirilgan yorliq nazorati
    ctrl = np.zeros(len(y))
    for k, (tr, te) in enumerate(folds):
        ctrl[te], _ = train_fold(imgs, ys, tr, te, a.epochs, 10 + k, a.arch)
    res["shuffled_label_auroc"] = _auroc(ys, ctrl)
    res["by_location"] = {}
    for l in sorted(set(loc)):
        m = np.array([x == l for x in loc])
        if y[m].sum() >= 5 and (y[m] == 0).sum() >= 5:
            res["by_location"][l] = {"n": int(m.sum()), "pos": int(y[m].sum()), "auroc": _auroc(y[m], oof[m])}
    order = np.argsort(-oof); res["operating_points"] = []
    for sens_t in (0.95, 0.90, 0.80):
        thr = np.sort(oof[y == 1])[int(np.floor((1 - sens_t) * y.sum()))]
        pred = oof >= thr
        res["operating_points"].append({"target_sensitivity": sens_t, "threshold": float(thr), "sensitivity": float(pred[y == 1].mean()),
                                        "specificity": float((~pred[y == 0]).mean()), "flagged_share": float(pred.mean())})
    np.save(a.out / "oof.npy", oof)
    (a.out / "wound_cv_results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
