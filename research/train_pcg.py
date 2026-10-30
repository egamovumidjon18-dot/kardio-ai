"""CirCor DigiScope (PhysioNet) da PCG shovqin + natija modelini o'qitish va ONNX eksport.

Ma'lumot:  https://physionet.org/content/circor-heart-sound/1.0.3/  (ODC-By 1.0)
    wget -r -N -c -np https://physionet.org/files/circor-heart-sound/1.0.3/

Ishga tushirish (loyiha ildizidan):
    python -m research.train_pcg --data-dir <...>/circor-heart-sound/1.0.3 --out weights/pcg

Muhim tamoyillar:
  * bo'linish BEMOR darajasida (bir bolaning yozuvlari ikki to'plamga tushmaydi);
  * xususiyatlar inference bilan AYNAN bir xil funksiyalar orqali (screening.pcg / features);
  * chegaralar (low/high) faqat validatsiyada tanlanadi, test faqat bir marta baholanadi;
  * yozuv darajasidagi shovqin yorlig'i = bemor "Present" VA nuqta "Murmur locations" ichida.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from screening.features import N_MELS, log_mel
from screening.model import LOCATIONS
from screening.pcg import TARGET_SR, WIN_S, assess_quality, load_wav, preprocess, windows

IGNORE = -100   # "Unknown" shovqinli bemorlar — murmur boshi uchun maskalanadi


# ---------------------------------------------------------------- ma'lumot
def read_patients(data_dir: Path) -> list[dict]:
    rows = list(csv.DictReader(open(data_dir / "training_data.csv", encoding="utf-8")))
    patients = []
    for r in rows:
        pid = r["Patient ID"].strip()
        murmur = r["Murmur"].strip()                     # Present / Absent / Unknown
        locs = {x for x in r.get("Murmur locations", "").replace("nan", "").split("+") if x}
        recs = []
        for wav in sorted((data_dir / "training_data").glob(f"{pid}_*.wav")):
            loc = next((t for t in wav.stem.split("_")[1:] if t in LOCATIONS), None)
            if loc is None:
                continue
            if murmur == "Present":
                m = 1 if loc in locs else 0
            elif murmur == "Absent":
                m = 0
            else:
                m = IGNORE
            recs.append({"path": wav, "location": loc, "murmur": m})
        extra = (r.get("Additional ID") or "").strip()
        patients.append({"id": pid, "murmur": murmur, "outcome": int(r["Outcome"].strip() == "Abnormal"),
                         "additional_id": extra if extra not in ("", "nan") else None, "recordings": recs})
    return [p for p in patients if p["recordings"]]


def subject_groups(patients: list[dict]) -> list[list[dict]]:
    """Bir bola ikki kampaniyada ikki xil ID bilan bo'lishi mumkin ("Additional ID").
    Ularni bitta guruhga birlashtiramiz — aks holda train/test leakage."""
    parent = {p["id"]: p["id"] for p in patients}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in patients:
        if p["additional_id"] in parent:
            parent[find(p["id"])] = find(p["additional_id"])
    groups = defaultdict(list)
    for p in patients:
        groups[find(p["id"])].append(p)
    return list(groups.values())


def split_patients(patients: list[dict], seed: int, frac=(0.70, 0.15, 0.15)) -> dict[str, list[dict]]:
    """Bola (subject) darajasida, (Murmur, Outcome) bo'yicha stratifikatsiyalangan bo'linish."""
    rng = random.Random(seed)
    strata = defaultdict(list)
    for g in subject_groups(patients):
        # guruh yorlig'i: guruhda shovqin "Present" bo'lsa — Present, aks holda birinchi a'zoniki
        murmur = "Present" if any(p["murmur"] == "Present" for p in g) else g[0]["murmur"]
        strata[(murmur, max(p["outcome"] for p in g))].append(g)
    out = {"train": [], "val": [], "test": []}
    for gs in strata.values():
        rng.shuffle(gs)
        n_tr, n_va = int(round(len(gs) * frac[0])), int(round(len(gs) * frac[1]))
        for name, part in (("train", gs[:n_tr]), ("val", gs[n_tr:n_tr + n_va]), ("test", gs[n_tr + n_va:])):
            out[name] += [p for g in part for p in g]
    return out


def featurize(patients: list[dict]) -> list[dict]:
    """Har bir sifatli yozuv → [n_win, 1, M, T] float16 (RAM tejash uchun)."""
    items = []
    for p in patients:
        for r in p["recordings"]:
            raw, sr, clip = load_wav(r["path"])
            if not assess_quality(raw, sr, clip).ok:
                continue
            win = windows(preprocess(raw, sr))
            if len(win) == 0:
                continue
            items.append({"pid": p["id"], "location": r["location"], "murmur": r["murmur"],
                          "outcome": p["outcome"], "x": log_mel(win).astype(np.float16)})
    return items


class WindowDataset(torch.utils.data.Dataset):
    def __init__(self, items: list[dict], augment: bool) -> None:
        self.index = [(i, w) for i, it in enumerate(items) for w in range(len(it["x"]))]
        self.items, self.augment = items, augment

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, k):
        i, w = self.index[k]
        it = self.items[i]
        x = torch.from_numpy(it["x"][w].astype(np.float32))
        if self.augment:                                  # yengil SpecAugment
            m, t = x.shape[1], x.shape[2]
            f0, fw = random.randrange(m), random.randint(0, 8)
            t0, tw = random.randrange(t), random.randint(0, 20)
            x[:, f0:f0 + fw, :] = 0
            x[:, :, t0:t0 + tw] = 0
        return x, it["murmur"], it["outcome"]


# ---------------------------------------------------------------- model
class PCGNet(nn.Module):
    """~0.1M parametr — 8 GB VRAM va CPU/ONNX uchun yengil."""

    def __init__(self, width: int = 16, dropout: float = 0.3) -> None:
        super().__init__()
        chans, layers, c_in = [width, width * 2, width * 4, width * 8], [], 1
        for c in chans:
            layers += [nn.Conv2d(c_in, c, 3, padding=1, bias=False), nn.BatchNorm2d(c), nn.ReLU(inplace=True),
                       nn.Conv2d(c, c, 3, padding=1, bias=False), nn.BatchNorm2d(c), nn.ReLU(inplace=True),
                       nn.MaxPool2d(2)]
            c_in = c
        self.body = nn.Sequential(*layers)
        self.drop = nn.Dropout(dropout)
        self.murmur = nn.Linear(c_in, 2)
        self.outcome = nn.Linear(c_in, 2)

    def forward(self, x):
        h = self.drop(torch.flatten(F.adaptive_avg_pool2d(self.body(x), 1), 1))
        return self.murmur(h), self.outcome(h)


# ---------------------------------------------------------------- baholash
def auroc(y: np.ndarray, s: np.ndarray) -> float:
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    ranks[order] = np.arange(1, len(order) + 1)
    # teng qiymatlar uchun o'rtacha rang
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        idx = allv == v
        ranks[idx] = ranks[idx].mean()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


@torch.no_grad()
def patient_scores(model, items: list[dict], device) -> dict[str, dict]:
    """Inference bilan bir xil agregatsiya: yozuv = oynalar o'rtachasi, bemor = yozuvlar maksimumi."""
    model.eval()
    per_pid = defaultdict(lambda: {"p_murmur": 0.0, "p_abnormal": 0.0, "agreement": 1.0})
    for it in items:
        x = torch.from_numpy(it["x"].astype(np.float32)).to(device)
        lm, lo = model(x)
        pm = torch.softmax(lm, 1)[:, 1].cpu().numpy()
        po = torch.softmax(lo, 1)[:, 1].cpu().numpy()
        rec_p = float(pm.mean())
        d = per_pid[it["pid"]]
        if rec_p >= d["p_murmur"]:
            d["p_murmur"] = rec_p
            d["agreement"] = float(np.mean((pm >= 0.5) == (rec_p >= 0.5)))
        d["p_abnormal"] = max(d["p_abnormal"], float(po.mean()))
    return dict(per_pid)


def choose_thresholds(y: np.ndarray, s: np.ndarray, min_sens: float, min_spec: float,
                      eps: float = 1e-6) -> tuple[float, float]:
    """Inference qoidasiga mos: p ≤ low → "yo'q", p ≥ high → "bor", oralig'i → abstain.

    low:  shovqinli bemorlarning ko'pi bilan (1-min_sens) qismi ≤ low bo'ladi;
    high: sog' bemorlarning kamida min_spec qismi < high bo'ladi.
    Sinflar to'liq ajralgan bo'lsa (low ≥ high) — bitta o'rta chegara, noaniq zona yo'q.
    """
    pos, neg = np.sort(s[y == 1]), np.sort(s[y == 0])
    if len(pos) == 0 or len(neg) == 0:
        return 0.3, 0.7
    misses = int(np.floor((1 - min_sens) * len(pos) + 1e-9))
    low = float(pos[misses]) - eps
    k = int(np.ceil(min_spec * len(neg) - 1e-9))
    high = float(neg[max(k, 1) - 1]) + eps
    if low >= high:
        low = high = (low + high) / 2
    return round(low, 6), round(high, 6)


def evaluate(scores: dict, patients: dict[str, dict], low: float, high: float, agree_min: float) -> dict:
    ids = [pid for pid in scores if patients[pid]["murmur"] in ("Present", "Absent")]
    y = np.array([int(patients[pid]["murmur"] == "Present") for pid in ids])
    s = np.array([scores[pid]["p_murmur"] for pid in ids])
    agr = np.array([scores[pid]["agreement"] for pid in ids])
    abstain = (agr < agree_min) | ((s > low) & (s < high))
    dec = s >= high
    keep = ~abstain
    tp = int(np.sum(dec & (y == 1) & keep)); fn = int(np.sum(~dec & (y == 1) & keep))
    tn = int(np.sum(~dec & (y == 0) & keep)); fp = int(np.sum(dec & (y == 0) & keep))
    yo = np.array([patients[pid]["outcome"] for pid in scores])
    so = np.array([scores[pid]["p_abnormal"] for pid in scores])
    return {
        "n_patients": len(ids),
        "murmur_auroc": round(auroc(y, s), 4),
        "abstain_rate": round(float(abstain.mean()), 4) if len(ids) else None,
        "sensitivity_decided": round(tp / (tp + fn), 4) if tp + fn else None,
        "specificity_decided": round(tn / (tn + fp), 4) if tn + fp else None,
        "confusion_decided": {"tp": tp, "fn": fn, "tn": tn, "fp": fp},
        "missed_murmur_among_all_present": int(np.sum((y == 1) & keep & ~dec)),
        "outcome_auroc": round(auroc(yo, so), 4),
    }


# ---------------------------------------------------------------- asosiy
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("weights/pcg"))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-sens", type=float, default=0.95)
    ap.add_argument("--min-spec", type=float, default=0.90)
    ap.add_argument("--agree-min", type=float, default=0.6)
    ap.add_argument("--max-patients", type=int, default=0, help="smoke test uchun cheklov")
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"
    print(f"qurilma: {device}" + (f" ({torch.cuda.get_device_name(0)})" if use_amp else ""))

    patients = read_patients(args.data_dir)
    if args.max_patients:
        patients = patients[:args.max_patients]
    by_id = {p["id"]: p for p in patients}
    split = split_patients(patients, args.seed)
    print({k: len(v) for k, v in split.items()}, "bemor")

    t0 = time.time()
    feats = {k: featurize(v) for k, v in split.items()}
    print({k: len(v) for k, v in feats.items()}, f"yozuv, xususiyatlar {time.time() - t0:.0f} s")

    train_ds = WindowDataset(feats["train"], augment=True)
    m_labels = np.array([feats["train"][i]["murmur"] for i, _ in train_ds.index])
    n_pos, n_neg = int((m_labels == 1).sum()), int((m_labels == 0).sum())
    w_pos = n_neg / max(n_pos, 1)
    o_labels = np.array([feats["train"][i]["outcome"] for i, _ in train_ds.index])
    w_abn = (o_labels == 0).sum() / max((o_labels == 1).sum(), 1)
    loader = torch.utils.data.DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                                         num_workers=args.workers, drop_last=len(train_ds) > args.batch)

    model = PCGNet().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=max(1, args.epochs * len(loader)))
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    crit_m = nn.CrossEntropyLoss(weight=torch.tensor([1.0, w_pos], device=device), ignore_index=IGNORE)
    crit_o = nn.CrossEntropyLoss(weight=torch.tensor([1.0, float(w_abn)], device=device))

    best, best_state = -1.0, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for x, ym, yo in loader:
            x, ym, yo = x.to(device), ym.to(device), yo.to(device)
            with torch.autocast(device.type, enabled=use_amp):
                lm, lo = model(x)
                loss_m = crit_m(lm, ym) if (ym != IGNORE).any() else lm.sum() * 0
                loss = loss_m + 0.5 * crit_o(lo, yo)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update(); sched.step()
            total += loss.detach().item() * len(x)
        val = patient_scores(model, feats["val"], device)
        ids = [p for p in val if by_id[p]["murmur"] in ("Present", "Absent")]
        auc = auroc(np.array([int(by_id[p]["murmur"] == "Present") for p in ids]),
                    np.array([val[p]["p_murmur"] for p in ids]))
        print(f"epoch {epoch:3d}  loss {total / max(len(train_ds), 1):.4f}  val murmur AUROC {auc:.4f}")
        if not np.isnan(auc) and auc > best:
            best, best_state = auc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)

    # chegaralar faqat validatsiyada
    val = patient_scores(model, feats["val"], device)
    ids = [p for p in val if by_id[p]["murmur"] in ("Present", "Absent")]
    low, high = choose_thresholds(np.array([int(by_id[p]["murmur"] == "Present") for p in ids]),
                                  np.array([val[p]["p_murmur"] for p in ids]), args.min_sens, args.min_spec)
    metrics = {
        "val": evaluate(val, by_id, low, high, args.agree_min),
        "test": evaluate(patient_scores(model, feats["test"], device), by_id, low, high, args.agree_min),
    }
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    args.out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    t_frames = feats["train"][0]["x"].shape[-1]
    torch.onnx.export(model, torch.zeros(1, 1, N_MELS, t_frames), args.out / "pcg.onnx",
                      input_names=["logmel"], output_names=["murmur_logits", "outcome_logits"],
                      dynamic_axes={"logmel": {0: "n"}, "murmur_logits": {0: "n"}, "outcome_logits": {0: "n"}},
                      opset_version=17, dynamo=False)
    card = {
        "name": "pcg_murmur_cnn", "version": time.strftime("%Y.%m.%d"),
        "task": "pediatrik PCG: shovqin bor/yo'q + kardiolog natijasi normal/anormal",
        "dataset": "CirCor DigiScope", "weights": "pcg.onnx",
        "thresholds": {"murmur_low": low, "murmur_high": high, "window_agreement": args.agree_min},
        "metrics": metrics,
        "training": {"seed": args.seed, "epochs": args.epochs, "sr": TARGET_SR, "win_s": WIN_S,
                     "min_sens": args.min_sens, "min_spec": args.min_spec, "device": str(device)},
    }
    (args.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out / "split.json").write_text(json.dumps({k: [p["id"] for p in v] for k, v in split.items()}),
                                         encoding="utf-8")
    print(f"saqlandi: {args.out}")


if __name__ == "__main__":
    main()
