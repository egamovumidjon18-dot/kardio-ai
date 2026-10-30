"""PTB-XL da yengil 1D-CNN: bo'lmachalar fibrillyatsiyasi (AFIB) + 5 ta asosiy toifa. ONNX eksport.

Ma'lumot:  https://physionet.org/content/ptb-xl/1.0.3/  (CC-BY 4.0)

    python -m research.train_ecg --data-dir <...>/ptb-xl-...-1.0.3 --out weights/ecg

Muhim tamoyillar:
  * bo'linish BEMOR darajasida: PTB-XL'ning `strat_fold` ustuni bir bemorning barcha
    yozuvlarini bitta foldga joylaydi. Train = 1–8, val = 9, test = 10 (rasmiy tavsiya;
    9 va 10-foldlar inson tomonidan tekshirilgan yorliqlar);
  * xususiyatlar inference bilan AYNAN bir xil funksiyalar orqali (ecg.signal);
  * chegaralar (low/high) faqat validatsiyada tanlanadi, test faqat bir marta baholanadi;
  * yorliqlar: AFIB (scp_codes'da AFIB bor; ritm yorliqlarida ishonch 0 yoziladi) va diagnostik superklasslar
    NORM / MI / STTC / CD / HYP (scp_statements.csv, ishonch ≥50).
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
import torch.nn.functional as F

from ecg.signal import LEADS_12, N_SAMPLES, TARGET_FS, preprocess, read_wfdb, select_leads
from research.train_pcg import auroc, choose_thresholds

CLASSES = ["AFIB", "NORM", "MI", "STTC", "CD", "HYP"]
TRAIN_FOLDS, VAL_FOLD, TEST_FOLD = set(range(1, 9)), 9, 10


# ---------------------------------------------------------------- ma'lumot
def read_labels(data_dir: Path) -> list[dict]:
    stm = {r[""]: r["diagnostic_class"] for r in csv.DictReader(open(data_dir / "scp_statements.csv", encoding="utf-8"))
           if r["diagnostic_class"]}
    rows = []
    for r in csv.DictReader(open(data_dir / "ptbxl_database.csv", encoding="utf-8")):
        scp = ast.literal_eval(r["scp_codes"])
        y = np.zeros(len(CLASSES), dtype=np.float32)
        if "AFIB" in scp:                                 # ritm yorliqlarida ehtimollik 0 bo'ladi — mavjudligi yetarli
            y[0] = 1
        for code, conf in scp.items():
            cls = stm.get(code)
            if cls in CLASSES and conf >= 50:
                y[CLASSES.index(cls)] = 1
        if y.sum() == 0:                                  # yorliqsiz yozuv — o'qitishga ham, baholashga ham kirmaydi
            continue
        rows.append({"id": int(r["ecg_id"]), "patient": int(float(r["patient_id"])), "fold": int(r["strat_fold"]),
                     "path": data_dir / r["filename_lr"], "y": y})
    return rows


def load_signals(rows: list[dict], cache: Path) -> np.ndarray:
    if cache.exists():
        x = np.load(cache)
        if len(x) == len(rows):
            return x
    x = np.zeros((len(rows), len(LEADS_12), N_SAMPLES), dtype=np.float16)
    for i, r in enumerate(rows):
        sig, fs, names = read_wfdb(r["path"])
        x[i] = preprocess(select_leads(sig, names, LEADS_12), fs)
        if i % 4000 == 0:
            print(f"  signal {i}/{len(rows)}", flush=True)
    np.save(cache, x)
    return x


# ---------------------------------------------------------------- model
class Block(nn.Module):
    def __init__(self, c_in: int, c_out: int, stride: int, k: int = 7) -> None:
        super().__init__()
        self.c1 = nn.Conv1d(c_in, c_out, k, stride, k // 2, bias=False)
        self.b1 = nn.BatchNorm1d(c_out)
        self.c2 = nn.Conv1d(c_out, c_out, k, 1, k // 2, bias=False)
        self.b2 = nn.BatchNorm1d(c_out)
        self.skip = None if (c_in == c_out and stride == 1) else nn.Sequential(
            nn.Conv1d(c_in, c_out, 1, stride, bias=False), nn.BatchNorm1d(c_out))

    def forward(self, x):
        h = F.relu(self.b1(self.c1(x)))
        h = self.b2(self.c2(h))
        return F.relu(h + (x if self.skip is None else self.skip(x)))


class ECGNet(nn.Module):
    """~0.4M parametr, kirish [N, 12, 1000], chiqish [N, 6] logit (multi-label)."""

    def __init__(self, width: int = 32, dropout: float = 0.3) -> None:
        super().__init__()
        w = width
        self.stem = nn.Sequential(nn.Conv1d(12, w, 15, 2, 7, bias=False), nn.BatchNorm1d(w), nn.ReLU(inplace=True))
        self.body = nn.Sequential(Block(w, w, 1), Block(w, 2 * w, 2), Block(2 * w, 2 * w, 1),
                                  Block(2 * w, 4 * w, 2), Block(4 * w, 4 * w, 1), Block(4 * w, 8 * w, 2))
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(16 * w, len(CLASSES))

    def forward(self, x):
        h = self.body(self.stem(x))
        h = torch.cat([h.mean(-1), h.amax(-1)], dim=1)           # avg + max pooling
        return self.head(self.drop(h))


def augment(x: torch.Tensor) -> torch.Tensor:
    """Yengil: amplituda masshtabi, tasodifiy siljish, gauss shovqin."""
    n = x.shape[0]
    x = x * (1 + 0.2 * (torch.rand(n, 1, 1, device=x.device) - 0.5))
    shift = int(torch.randint(-50, 51, (1,)))
    x = torch.roll(x, shift, dims=-1)
    return x + 0.03 * torch.randn_like(x)


@torch.no_grad()
def predict(model, x: np.ndarray, device, batch: int = 512) -> np.ndarray:
    model.eval()
    out = []
    for i in range(0, len(x), batch):
        xb = torch.from_numpy(x[i:i + batch].astype(np.float32)).to(device)
        out.append(torch.sigmoid(model(xb)).cpu().numpy())
    return np.concatenate(out)


# ---------------------------------------------------------------- baholash
def eval_afib(y: np.ndarray, p: np.ndarray, low: float, high: float) -> dict:
    """AFIB bo'yicha: p ≥ high → bor, p ≤ low → yo'q, oralig'i → abstain."""
    abstain = (p > low) & (p < high)
    dec, keep = p >= high, ~abstain
    tp = int(np.sum(dec & (y == 1) & keep)); fn = int(np.sum(~dec & (y == 1) & keep))
    tn = int(np.sum(~dec & (y == 0) & keep)); fp = int(np.sum(dec & (y == 0) & keep))
    return {"auroc": auroc(y, p), "abstain_rate": float(abstain.mean()),
            "sensitivity": tp / (tp + fn) if tp + fn else float("nan"),
            "specificity": tn / (tn + fp) if tn + fp else float("nan"),
            "ppv": tp / (tp + fp) if tp + fp else float("nan"),
            "npv": tn / (tn + fn) if tn + fn else float("nan"),
            "tp": tp, "fn": fn, "tn": tn, "fp": fp}


def bootstrap_ci(y: np.ndarray, p: np.ndarray, patients: np.ndarray, low: float, high: float,
                 n: int = 1000, seed: int = 0) -> dict:
    """Bemor darajasida qayta tanlash (bir bemorning bir nechta yozuvi birga)."""
    uniq = np.unique(patients)
    idx_by = {u: np.where(patients == u)[0] for u in uniq}
    rng = np.random.default_rng(seed)
    acc: dict[str, list] = {}
    for _ in range(n):
        pick = np.concatenate([idx_by[u] for u in rng.choice(uniq, len(uniq))])
        for k, v in eval_afib(y[pick], p[pick], low, high).items():
            if isinstance(v, float) and not np.isnan(v):
                acc.setdefault(k, []).append(v)
    return {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
            for k, v in acc.items()}


def full_report(y: np.ndarray, p: np.ndarray, patients: np.ndarray, low: float, high: float) -> dict:
    r = {"n_records": int(len(y)), "n_patients": int(len(np.unique(patients))),
         "afib": {k: round(v, 4) if isinstance(v, float) else v for k, v in eval_afib(y[:, 0], p[:, 0], low, high).items()},
         "afib_ci95": bootstrap_ci(y[:, 0], p[:, 0], patients, low, high), "n_afib": int(y[:, 0].sum())}
    r["auroc"] = {c: round(auroc(y[:, i], p[:, i]), 4) for i, c in enumerate(CLASSES)}
    # superklass AUROC uchun bootstrap CI
    uniq = np.unique(patients)
    idx_by = {u: np.where(patients == u)[0] for u in uniq}
    rng = np.random.default_rng(1)
    acc = {c: [] for c in CLASSES}
    for _ in range(500):
        pick = np.concatenate([idx_by[u] for u in rng.choice(uniq, len(uniq))])
        for i, c in enumerate(CLASSES):
            a = auroc(y[pick, i], p[pick, i])
            if not np.isnan(a):
                acc[c].append(a)
    r["auroc_ci95"] = {c: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
                       for c, v in acc.items() if v}
    return r


# ---------------------------------------------------------------- asosiy
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("weights/ecg"))
    ap.add_argument("--cache", type=Path, default=None, help="oldindan tayyorlangan signal .npy")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-sens", type=float, default=0.95)
    ap.add_argument("--min-spec", type=float, default=0.95)
    ap.add_argument("--max-records", type=int, default=0, help="smoke test uchun")
    args = ap.parse_args()

    torch.manual_seed(args.seed); np.random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"
    print(f"qurilma: {device}")

    rows = read_labels(args.data_dir)
    if args.max_records:
        rows = rows[:args.max_records]
    t0 = time.time()
    cache = args.cache or (args.data_dir.parent / "ptbxl_lr_preprocessed.npy")
    x = load_signals(rows, cache if not args.max_records else Path("_smoke.npy"))
    print(f"{len(rows)} yozuv, signal tayyor {time.time() - t0:.0f} s")
    y = np.stack([r["y"] for r in rows])
    fold = np.array([r["fold"] for r in rows])
    pat = np.array([r["patient"] for r in rows])
    tr, va, te = np.isin(fold, list(TRAIN_FOLDS)), fold == VAL_FOLD, fold == TEST_FOLD
    # bemor leakage'ga qarshi tekshiruv
    assert not (set(pat[tr]) & set(pat[va])) and not (set(pat[tr]) & set(pat[te])) and not (set(pat[va]) & set(pat[te])), \
        "bemor bir nechta to'plamda!"
    print({"train": int(tr.sum()), "val": int(va.sum()), "test": int(te.sum())}, "yozuv;",
          "AFIB:", int(y[tr, 0].sum()), int(y[va, 0].sum()), int(y[te, 0].sum()))

    xt, yt = torch.from_numpy(x[tr]), torch.from_numpy(y[tr])
    pos_w = torch.tensor(((1 - yt.mean(0)) / yt.mean(0).clamp(min=1e-3)).clamp(max=10).numpy(), device=device)
    model = ECGNet().to(device)
    print("parametrlar:", sum(p.numel() for p in model.parameters()))
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-2)
    steps = args.epochs * ((len(xt) + args.batch - 1) // args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    crit = nn.BCEWithLogitsLoss(pos_weight=pos_w)

    best, best_state = -1.0, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = torch.randperm(len(xt))
        total = 0.0
        for i in range(0, len(perm), args.batch):
            b = perm[i:i + args.batch]
            xb, yb = xt[b].float().to(device), yt[b].to(device)
            with torch.autocast(device.type, enabled=use_amp):
                loss = crit(model(augment(xb)).float(), yb)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update(); sched.step()
            total += loss.item() * len(b)
        pv = predict(model, x[va], device)
        aucs = [auroc(y[va, i], pv[:, i]) for i in range(len(CLASSES))]
        score = float(np.nanmean(aucs))
        print(f"epoch {epoch:3d} loss {total / len(xt):.4f} val AUROC AFIB {aucs[0]:.4f} o'rtacha {score:.4f}", flush=True)
        if score > best:
            best, best_state = score, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)

    pv = predict(model, x[va], device)
    low, high = choose_thresholds(y[va, 0].astype(int), pv[:, 0], args.min_sens, args.min_spec)
    # sinf bo'yicha oddiy chegara (valda Youden) — "NORM/MI/..." uchun ma'lumot, abstain yo'q
    youden = {}
    for i, c in enumerate(CLASSES):
        ts = np.unique(pv[:, i])
        best_t, best_j = 0.5, -1
        for t in ts[::max(1, len(ts) // 200)]:
            pr = pv[:, i] >= t
            j = (pr[y[va, i] == 1].mean() if (y[va, i] == 1).any() else 0) - (pr[y[va, i] == 0].mean() if (y[va, i] == 0).any() else 0)
            if j > best_j:
                best_t, best_j = float(t), j
        youden[c] = round(best_t, 4)

    metrics = {"val": full_report(y[va], pv, pat[va], low, high),
               "test": full_report(y[te], predict(model, x[te], device), pat[te], low, high)}
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    args.out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.save(model.state_dict(), args.out / "ecg.pt")
    torch.onnx.export(model, torch.zeros(1, 12, N_SAMPLES), args.out / "ecg.onnx",
                      input_names=["ecg"], output_names=["logits"], dynamic_axes={"ecg": {0: "n"}, "logits": {0: "n"}},
                      opset_version=17, dynamo=False)
    card = {
        "name": "ecg_cnn_ptbxl", "version": time.strftime("%Y.%m.%d"),
        "task": "12 tarmoqli EKG (10 s, 100 Hz): AFIB + NORM/MI/STTC/CD/HYP",
        "dataset": "PTB-XL", "weights": "ecg.onnx",
        "thresholds": {"afib_low": low, "afib_high": high, "class_thresholds": youden,
                       "classes": CLASSES, "fs": TARGET_FS, "n_samples": N_SAMPLES, "leads": list(LEADS_12)},
        "metrics": metrics,
        "training": {"seed": args.seed, "epochs": args.epochs, "split": "strat_fold: train 1-8, val 9, test 10",
                     "min_sens": args.min_sens, "min_spec": args.min_spec, "device": str(device)},
    }
    (args.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saqlandi: {args.out}")


if __name__ == "__main__":
    main()
