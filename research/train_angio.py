"""ARCADE (stenoz) da U-Net: koronar angiografiya kadrida stenoz nomzodlari segmentatsiyasi. ONNX eksport.

Ma'lumot:  https://zenodo.org/records/10390295  (ARCADE; registry'da CC-BY 4.0, Zenodo yozuvi CC0 deb ko'rsatadi)

    python -m research.train_angio --data-dir <...>/arcade --out weights/angio

Muhim:
  * ARCADE'ning muallif bo'linishi ishlatiladi (train 1000 / val 200 / test 300). Bemor identifikatori
    BERILMAGAN, shuning uchun bir bemorning kadrlari turli to'plamlarga tushmaganini tekshirib bo'lmaydi
    — bu cheklov model kartasiga yoziladi;
  * 512 px, AMP, kichik U-Net (8 GB VRAM);
  * chegara va minimal maydon faqat validatsiyada tanlanadi; test bir marta baholanadi;
  * deyarli barcha kadrda stenoz bor (997/1000) → rasm darajasida spetsifiklik baholanmaydi;
    baholash: piksel Dice va lezion darajasida (nomzod) sezgirlik / aniqlik, bootstrap 95% CI (kadr darajasida).
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from angio.image import SIZE, candidates, components, load_gray, to_model_input


# ---------------------------------------------------------------- ma'lumot
def load_split(root: Path, split: str, limit: int = 0) -> tuple[np.ndarray, np.ndarray, list[int]]:
    from PIL import Image, ImageDraw

    ann_dir = root / "stenosis" / split
    d = json.load(open(ann_dir / "annotations" / f"{split}.json"))
    polys: dict[int, list] = {}
    for a in d["annotations"]:
        polys.setdefault(a["image_id"], []).extend(a["segmentation"])
    images = d["images"][:limit] if limit else d["images"]
    x = np.zeros((len(images), 1, SIZE, SIZE), dtype=np.float16)
    y = np.zeros((len(images), SIZE, SIZE), dtype=np.uint8)
    for i, im in enumerate(images):
        x[i] = to_model_input(load_gray(ann_dir / "images" / im["file_name"]))[0]
        m = Image.new("L", (im["width"], im["height"]), 0)
        dr = ImageDraw.Draw(m)
        for seg in polys.get(im["id"], []):
            pts = [(seg[k], seg[k + 1]) for k in range(0, len(seg) - 1, 2)]
            if len(pts) >= 3:
                dr.polygon(pts, fill=1)
        if (im["width"], im["height"]) != (SIZE, SIZE):
            m = m.resize((SIZE, SIZE), Image.NEAREST)
        y[i] = np.asarray(m)
    return x, y, [im["id"] for im in images]


# ---------------------------------------------------------------- model
def cb(c_in: int, c_out: int) -> nn.Sequential:
    return nn.Sequential(nn.Conv2d(c_in, c_out, 3, padding=1, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(inplace=True),
                         nn.Conv2d(c_out, c_out, 3, padding=1, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(inplace=True))


class UNet(nn.Module):
    """~1.9M parametr (base=16), kirish [N,1,512,512], chiqish [N,1,512,512] logit."""

    def __init__(self, base: int = 16) -> None:
        super().__init__()
        ch = [base, base * 2, base * 4, base * 8, base * 16]
        self.enc = nn.ModuleList([cb(1, ch[0])] + [cb(ch[i], ch[i + 1]) for i in range(4)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(ch[i + 1], ch[i], 2, 2) for i in range(4)])
        self.dec = nn.ModuleList([cb(ch[i] * 2, ch[i]) for i in range(4)])
        self.out = nn.Conv2d(ch[0], 1, 1)

    def forward(self, x):
        skips = []
        for i, e in enumerate(self.enc):
            x = e(x if i == 0 else F.max_pool2d(x, 2))
            skips.append(x)
        x = skips[-1]
        for i in reversed(range(4)):
            x = self.dec[i](torch.cat([self.up[i](x), skips[i]], dim=1))
        return self.out(x)


def loss_fn(logits, y):
    bce = F.binary_cross_entropy_with_logits(logits, y, pos_weight=torch.tensor(5.0, device=y.device))
    p = torch.sigmoid(logits)
    inter, den = (p * y).sum((1, 2, 3)), p.sum((1, 2, 3)) + y.sum((1, 2, 3))
    return bce + (1 - (2 * inter + 1) / (den + 1)).mean()


def augment(x: torch.Tensor, y: torch.Tensor):
    if random.random() < 0.5:
        x, y = x.flip(-1), y.flip(-1)
    n = x.shape[0]
    x = (x - 0.5) * (1 + 0.3 * (torch.rand(n, 1, 1, 1, device=x.device) - 0.5)) + 0.5 \
        + 0.1 * (torch.rand(n, 1, 1, 1, device=x.device) - 0.5)
    # tasodifiy affin: kichik burilish/masshtab/siljish
    ang = (torch.rand(n, device=x.device) - 0.5) * 2 * 0.17           # ±10°
    sc = 1 + (torch.rand(n, device=x.device) - 0.5) * 0.2
    th = torch.zeros(n, 2, 3, device=x.device)
    th[:, 0, 0], th[:, 0, 1] = torch.cos(ang) / sc, -torch.sin(ang) / sc
    th[:, 1, 0], th[:, 1, 1] = torch.sin(ang) / sc, torch.cos(ang) / sc
    th[:, :, 2] = (torch.rand(n, 2, device=x.device) - 0.5) * 0.1
    g = F.affine_grid(th, x.shape, align_corners=False)
    return F.grid_sample(x, g, padding_mode="border", align_corners=False).clamp(0, 1), \
        (F.grid_sample(y, g, mode="nearest", padding_mode="zeros", align_corners=False))


@torch.no_grad()
def predict(model, x: np.ndarray, device, batch: int = 8) -> np.ndarray:
    model.eval()
    out = []
    for i in range(0, len(x), batch):
        xb = torch.from_numpy(x[i:i + batch].astype(np.float32)).to(device)
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            out.append(torch.sigmoid(model(xb).float()).cpu().numpy()[:, 0].astype(np.float16))
    return np.concatenate(out)


# ---------------------------------------------------------------- baholash
def dice(pred: np.ndarray, gt: np.ndarray) -> float:
    s = pred.sum() + gt.sum()
    return float(2 * (pred & gt).sum() / s) if s else 1.0


def lesion_match(prob: np.ndarray, gt: np.ndarray, thr: float, min_area: int, iou_thr: float = 0.1) -> dict:
    """Lezion: GT komponenti bashorat komponenti bilan IoU ≥ iou_thr kesishsa topilgan."""
    gt_c = components(gt.astype(bool), 20)
    pr_c = components(prob >= thr, min_area)
    matched_g = sum(any((g & p).sum() / max((g | p).sum(), 1) >= iou_thr for p in pr_c) for g in gt_c)
    matched_p = sum(any((g & p).sum() / max((g | p).sum(), 1) >= iou_thr for g in gt_c) for p in pr_c)
    return {"n_gt": len(gt_c), "n_pred": len(pr_c), "tp_gt": matched_g, "tp_pred": matched_p}


def per_image(prob: np.ndarray, y: np.ndarray, thr: float, min_area: int) -> list[dict]:
    rows = []
    for p, g in zip(prob, y):
        pm = p.astype(np.float32) >= thr
        r = lesion_match(p.astype(np.float32), g, thr, min_area)
        r.update(dice=dice(pm, g.astype(bool)), iou=float((pm & (g > 0)).sum() / max((pm | (g > 0)).sum(), 1)))
        rows.append(r)
    return rows


def summarize(rows: list[dict]) -> dict:
    tp_g, n_g = sum(r["tp_gt"] for r in rows), sum(r["n_gt"] for r in rows)
    tp_p, n_p = sum(r["tp_pred"] for r in rows), sum(r["n_pred"] for r in rows)
    return {"dice": float(np.mean([r["dice"] for r in rows])), "iou": float(np.mean([r["iou"] for r in rows])),
            "lesion_recall": tp_g / n_g if n_g else float("nan"),
            "lesion_precision": tp_p / n_p if n_p else float("nan"),
            "n_images": len(rows), "n_gt_lesions": n_g, "n_pred_lesions": n_p}


def bootstrap(rows: list[dict], n: int = 1000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    acc: dict[str, list] = {}
    for _ in range(n):
        pick = [rows[i] for i in rng.integers(0, len(rows), len(rows))]
        for k, v in summarize(pick).items():
            if k.startswith(("dice", "iou", "lesion")) and not np.isnan(v):
                acc.setdefault(k, []).append(v)
    return {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] for k, v in acc.items()}


def report(prob, y, thr, min_area) -> dict:
    rows = per_image(prob, y, thr, min_area)
    s = {k: round(v, 4) if isinstance(v, float) else v for k, v in summarize(rows).items()}
    s["ci95"] = bootstrap(rows)
    return s


# ---------------------------------------------------------------- asosiy
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True, help="arcade/ (ichida stenosis/, syntax/)")
    ap.add_argument("--out", type=Path, default=Path("weights/angio"))
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="smoke test uchun")
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"
    print(f"qurilma: {device}")
    t0 = time.time()
    data = {s: load_split(args.data_dir, s, args.limit) for s in ("train", "val", "test")}
    print({s: len(v[0]) for s, v in data.items()}, f"kadr, {time.time() - t0:.0f} s")

    model = UNet().to(device)
    print("parametrlar:", sum(p.numel() for p in model.parameters()))
    xtr, ytr = torch.from_numpy(data["train"][0]), torch.from_numpy(data["train"][1])
    steps = args.epochs * ((len(xtr) + args.batch - 1) // args.batch)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best, best_state = -1.0, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        perm, total = torch.randperm(len(xtr)), 0.0
        for i in range(0, len(perm), args.batch):
            b = perm[i:i + args.batch]
            xb, yb = xtr[b].float().to(device), ytr[b].float().to(device)[:, None]
            xb, yb = augment(xb, yb)
            with torch.autocast(device.type, enabled=use_amp):
                loss = loss_fn(model(xb).float(), yb)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update(); sched.step()
            total += loss.item() * len(b)
        if epoch % 2 == 0 or epoch == args.epochs:
            pv = predict(model, data["val"][0], device)
            d = float(np.mean([dice(p.astype(np.float32) >= 0.5, g.astype(bool)) for p, g in zip(pv, data["val"][1])]))
            print(f"epoch {epoch:3d} loss {total / len(xtr):.4f} val Dice {d:.4f}", flush=True)
            if d > best:
                best, best_state = d, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)

    # chegara va minimal maydon — faqat validatsiyada: lezion F1 maksimal
    pv = predict(model, data["val"][0], device)
    best_cfg, best_f1 = (0.5, 30), -1.0
    for thr in (0.3, 0.4, 0.5, 0.6, 0.7):
        for ma in (10, 30, 60, 100):
            s = summarize(per_image(pv, data["val"][1], thr, ma))
            r, p = s["lesion_recall"], s["lesion_precision"]
            f1 = 2 * r * p / (r + p) if r + p else 0
            if f1 > best_f1:
                best_f1, best_cfg = f1, (thr, ma)
    thr, min_area = best_cfg
    print("tanlangan chegara:", thr, "min_area:", min_area, "val lesion F1", round(best_f1, 4))
    metrics = {"val": report(pv, data["val"][1], thr, min_area),
               "test": report(predict(model, data["test"][0], device), data["test"][1], thr, min_area)}
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    args.out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.save(model.state_dict(), args.out / "angio.pt")
    torch.onnx.export(model, torch.zeros(1, 1, SIZE, SIZE), args.out / "angio.onnx", input_names=["image"],
                      output_names=["logits"], dynamic_axes={"image": {0: "n"}, "logits": {0: "n"}},
                      opset_version=17, dynamo=False)
    card = {
        "name": "angio_stenosis_unet", "version": time.strftime("%Y.%m.%d"),
        "task": "koronar angiografiya (512 px): stenoz nomzodlari segmentatsiyasi — SYNTAX bahosiga yordamchi",
        "dataset": "ARCADE", "weights": "angio.onnx",
        "thresholds": {"prob": thr, "min_area_px": min_area, "size": SIZE},
        "metrics": metrics,
        "limitations": ["ARCADE'da bemor ID'si yo'q: train/val/test orasida bemor leakage tekshirilmagan",
                        "997/1000 kadrda stenoz bor: rasm darajasidagi spetsifiklik baholanmadi",
                        "bitta markaz (Eron), bitta annotator guruhi; tashqi validatsiya yo'q",
                        "SYNTAX kalkulyatori EMAS: segment nomi, okklyuziya, bifurkatsiya, kalsifikatsiya baholanmaydi"],
        "training": {"seed": args.seed, "epochs": args.epochs, "device": str(device), "amp": use_amp},
    }
    (args.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saqlandi: {args.out}")


if __name__ == "__main__":
    main()
