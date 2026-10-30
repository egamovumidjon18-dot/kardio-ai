"""Tajriba: mahalliy ma'lumot qancha bo'lsa, model yangi klinikaga moslashadi?

ZCHSound (Xitoy) "yangi klinika" o'rnida: CirCor bazaviy modeli N ta mahalliy bolada
fine-tune qilinadi va hech qachon ishlatilmagan qat'iy test qismida baholanadi.
Maqsad — O'zbekistonda nechta yozuv yig'ish kerakligini taxmin qilish.

    python -m research.adapt_zchsound --data-dir <...>/ZCHSound --base <...>/circor_base --out docs/experiments

Yorliq: TYN (ASD, VSD, PDA) = 1, NORMAL = 0. PFO (odatda shovqinsiz) va ≤28 kunlik
neonatlar (model ular uchun abstain qiladi) chiqarib tashlanadi.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from research.external_zchsound import read_subset
from research.train_pcg import PCGNet, WindowDataset, auroc
from screening.features import log_mel
from screening.pcg import assess_quality, load_wav, preprocess, windows

POSITIVE = {"ASD", "VSD", "PDA"}


def load_items(data_dir: Path) -> list[dict]:
    items = []
    for r in read_subset(data_dir, "clean"):
        if r["dx"] not in POSITIVE | {"NORMAL"} or (r["age_days"] is not None and r["age_days"] <= 28):
            continue
        raw, sr, clip = load_wav(r["path"])
        if not assess_quality(raw, sr, clip).ok:
            continue
        win = windows(preprocess(raw, sr))
        if len(win):
            y = int(r["dx"] in POSITIVE)
            items.append({"pid": r["id"], "subject": r["subject"], "dx": r["dx"], "murmur": y, "outcome": y,
                          "x": log_mel(win).astype(np.float16)})
    return items


def by_subject(items: list[dict]) -> list[list[dict]]:
    """Bitta bolaning barcha yozuvlari bitta guruh (ZCHSound'da 1 bola = 1 yozuv)."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["subject"], []).append(it)
    return list(groups.values())


def stratified_split(subjects: list[list[dict]], test_frac: float, seed: int) -> tuple[list, list]:
    """Bola darajasida, tashxis bo'yicha stratifikatsiya."""
    rng = random.Random(seed)
    test, pool = [], []
    for dx in sorted({g[0]["dx"] for g in subjects}):
        gs = [g for g in subjects if g[0]["dx"] == dx]
        rng.shuffle(gs)
        k = int(round(len(gs) * test_frac))
        test += gs[:k]
        pool += gs[k:]
    return test, pool


def flat(subjects: list[list[dict]]) -> list[dict]:
    return [it for g in subjects for it in g]


@torch.no_grad()
def scores(model: nn.Module, subjects: list[list[dict]], device) -> np.ndarray:
    """Bola bali = yozuvlar maksimumi (platformadagi kabi), yozuv = oynalar o'rtachasi."""
    model.eval()
    out = []
    for g in subjects:
        rec = []
        for it in g:
            lm, _ = model(torch.from_numpy(it["x"].astype(np.float32)).to(device))
            rec.append(float(torch.softmax(lm, 1)[:, 1].mean()))
        out.append(max(rec))
    return np.array(out)


def sens_at_spec(y: np.ndarray, s: np.ndarray, spec: float = 0.80) -> float:
    thr = np.quantile(s[y == 0], spec)
    return float(np.mean(s[y == 1] > thr))


def finetune(base: dict, train: list[dict], device, epochs: int, lr: float, seed: int) -> nn.Module:
    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
    model = PCGNet().to(device)
    model.load_state_dict(base)
    ds = WindowDataset(train, augment=True)
    loader = torch.utils.data.DataLoader(ds, batch_size=64, shuffle=True, drop_last=len(ds) > 64)
    labels = np.array([train[i]["murmur"] for i, _ in ds.index])
    w = torch.tensor([1.0, float((labels == 0).sum() / max((labels == 1).sum(), 1))], device=device)
    crit = nn.CrossEntropyLoss(weight=w)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-3)
    for _ in range(epochs):
        model.train()
        for x, ym, _ in loader:
            x, ym = x.to(device), ym.to(device)
            lm, _ = model(x)
            loss = crit(lm, ym)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
    return model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--base", type=Path, required=True, help="pcg.pt bor papka")
    ap.add_argument("--out", type=Path, default=Path("docs/experiments"))
    ap.add_argument("--sizes", default="50,100,200,0")       # 0 = butun pool
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    subjects = by_subject(load_items(args.data_dir))
    test, pool = stratified_split(subjects, 0.4, args.seed)
    y_test = np.array([g[0]["murmur"] for g in test])
    print(f"bolalar: {len(subjects)} (test {len(test)}, pool {len(pool)}); test TYN {int(y_test.sum())}")

    base = torch.load(args.base / "pcg.pt", map_location=device)
    model0 = PCGNet().to(device)
    model0.load_state_dict(base)
    s0 = scores(model0, test, device)
    results = [{"n": 0, "auroc": [auroc(y_test, s0)], "sens_at_spec80": [sens_at_spec(y_test, s0)]}]
    print(f"N=0 (moslashtirishsiz): AUROC {results[0]['auroc'][0]:.3f}")

    for n in [int(v) for v in args.sizes.split(",")]:
        n_eff = n or len(pool)
        reps = args.repeats if n else min(args.repeats, 3)
        aucs, sens = [], []
        for rep in range(reps):
            rng = random.Random(1000 * n_eff + rep)
            sample = rng.sample(pool, n_eff) if n_eff < len(pool) else list(pool)
            if len({g[0]["murmur"] for g in sample}) < 2:
                continue
            m = finetune(base, flat(sample), device, args.epochs, args.lr, seed=rep)
            s = scores(m, test, device)
            aucs.append(auroc(y_test, s)); sens.append(sens_at_spec(y_test, s))
        results.append({"n": n_eff, "auroc": aucs, "sens_at_spec80": sens})
        print(f"N={n_eff}: AUROC {np.mean(aucs):.3f} ± {np.std(aucs):.3f} ({len(aucs)} takror)")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "zchsound_adaptation.json").write_text(json.dumps(
        {"test_n": len(test), "test_chd": int(y_test.sum()), "pool_n": len(pool), "epochs": args.epochs,
         "lr": args.lr, "results": results}, indent=2), encoding="utf-8")
    lines = ["# Tajriba: mahalliy ma'lumot bilan moslashtirish (ZCHSound \"yangi klinika\" sifatida)", "",
             f"Qat'iy test: {len(test)} bola (TYN {int(y_test.sum())}: ASD/VSD/PDA; PFO va neonatlar chiqarilgan). "
             f"Fine-tuning havzasi: {len(pool)} bola. {args.epochs} epoch, lr {args.lr}.", "",
             "| Mahalliy bolalar soni (N) | AUROC (o'rtacha ± SD) | Sezgirlik @ 80% spetsifiklik | Takrorlar |",
             "|---|---|---|---|"]
    for r in results:
        a, s = np.array(r["auroc"]), np.array(r["sens_at_spec80"])
        lines.append(f"| {r['n'] if r['n'] else '0 (moslashtirishsiz)'} | {a.mean():.3f} ± {a.std():.3f} | "
                     f"{s.mean():.3f} ± {s.std():.3f} | {len(a)} |")
    lines += ["", "Izoh: 'Sezgirlik @ 80% spetsifiklik' chegarasi test to'plamidagi ROC egri chizig'idan olingan "
                  "(egri chiziq nuqtasi, mustaqil chegara emas)."]
    (args.out / "zchsound_adaptation.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
