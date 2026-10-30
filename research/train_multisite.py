"""Ko'p manbali PCG modeli: CirCor (Braziliya) + ZCHSound (Xitoy) — tashqi sinovdagi pasayishni kamaytirish tajribasi.

    python -m research.train_multisite --circor-dir <...> --zch-dir <...> --out weights/pcg_multisite

Uchta model BIR XIL kod va urug' bilan o'qitiladi va ikkala sinov to'plamida solishtiriladi (3×2 jadval):
  circor_only  — oldingi usul (taqqoslash uchun);  zch_only — faqat ZCHSound;  multisite — ikkalasi birga.

Maqsad bir xil emas: CirCor «shovqin bor/yo'q» belgilaydi, ZCHSound esa «yurak nuqsoni (ASD/VSD/PDA) bor/yo'q».
Birlashtirilganda model «ExoKG kerak» degan umumiy belgini o'rganadi. PFO (odatda shovqinsiz) va ≤28 kunlik
chaqaloqlar (platforma ularda AI ishlatmaydi) chiqarib tashlanadi.

Ikki yashirin xavfga qarshi:
  * manba (site) prior'i: har bir manba ICHIDA sinflar teng vaznlanadi — model «qaysi manbadan» ekanidan foyda ola olmaydi;
  * yosh: ZCHSound'da nuqsonli bolalar yoshroq (faqat yosh ~0.75 AUROC beradi) — natija yosh guruhlari bo'yicha va
    «faqat yosh» bazaviy chizig'i bilan solishtiriladi.

OLDINDAN BELGILANGAN QABUL MEZONI (natijani ko'rishdan oldin yozilgan):
  A. multisite CirCor testida circor_only dan 0.03 AUROC dan ko'p yomonlashmasin;
  B1. multisite ZCHSound testida circor_only dan kamida +0.10 AUROC yaxshi bo'lsin;
  B2. multisite ZCHSound testida «faqat yosh» chizig'idan kamida +0.05 AUROC yuqori bo'lsin (yoshdan tashqari signal).
  A, B1, B2 hammasi bajarilsa → weights/pcg_multisite (tadqiqot rejimi); aks holda salbiy natija sifatida yoziladi.

NATIJA (2026-10-30): mezonlar bajarildi, LEKIN QAROR — RAD ETILDI. Tajribadan keyin ZCHSound yozuvlari tashxis bo'yicha
ketma-ket yig'ilgani va sog'lar ichida ham «erta vs kech» AUROC ≈0.67 ekani topildi (research/control_zch_batch.py);
ZCHSound testidagi AUROC (0.97) yozuv-blok izidan kelgan bo'lishi mumkin. Mezon bu xavfni hisobga olmagan edi.
Yangi tajriba rejalashtirilganda, mezonga shunday nazorat (salbiy nazorat) ham OLDINDAN qo'shilishi kerak.
"""
from __future__ import annotations

import argparse
import json
import random
import time
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from research.external_zchsound import age_band, read_subset
from research.train_pcg import (IGNORE, PCGNet, WindowDataset, auroc, choose_thresholds, featurize, patient_scores,
                                read_patients, subject_groups)
from screening.features import N_MELS, log_mel
from screening.pcg import TARGET_SR, WIN_S, assess_quality, load_wav, preprocess, windows

ZCH_POSITIVE = {"ASD", "VSD", "PDA"}
SITES = {0: "circor", 1: "zch"}
AGREE_MIN = 0.6


# ---------------------------------------------------------------- ma'lumot
def load_circor(data_dir: Path, split_path: Path) -> tuple[dict, dict, dict]:
    """CirCor: avvalgi bo'linish (split.json) — test to'plami oldingi baholash bilan AYNAN bir xil."""
    patients = read_patients(data_dir)
    split_ids = json.loads(split_path.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in patients}
    groups_list = subject_groups(patients)
    group_of = {p["id"]: g[0]["id"] for g in groups_list for p in g}
    items, labels, groups = {}, {}, {}
    for part in ("train", "val", "test"):
        its = featurize([by_id[i] for i in split_ids[part] if i in by_id])
        for it in its:
            it["site"] = 0
            it["pid"] = "C:" + it["pid"]
        items[part] = its
    for p in patients:
        pid = "C:" + p["id"]
        labels[pid] = {"Present": 1, "Absent": 0}.get(p["murmur"])
        groups[pid] = "C:" + group_of[p["id"]]
    return items, labels, groups


def load_zch(data_dir: Path, seed: int) -> tuple[dict, dict, dict, dict]:
    """ZCHSound (toza to'plam): bola darajasida, tashxis bo'yicha stratifikatsiyalangan 60/15/25 bo'linish."""
    rows = [r for r in read_subset(data_dir, "clean")
            if r["dx"] in ZCH_POSITIVE | {"NORMAL"} and not (r["age_days"] is not None and r["age_days"] <= 28)]
    kept = []
    for r in rows:
        raw, sr, clip = load_wav(r["path"])
        if not assess_quality(raw, sr, clip).ok:
            continue
        win = windows(preprocess(raw, sr))
        if len(win) == 0:
            continue
        kept.append({"pid": "Z:" + r["id"], "murmur": int(r["dx"] in ZCH_POSITIVE), "outcome": IGNORE, "site": 1,
                     "x": log_mel(win).astype(np.float16), "dx": r["dx"], "age_days": r["age_days"]})
    rng = random.Random(seed)
    items = {"train": [], "val": [], "test": []}
    for dx in sorted({k["dx"] for k in kept}):
        g = [k for k in kept if k["dx"] == dx]
        rng.shuffle(g)
        n_tr, n_va = int(round(len(g) * 0.60)), int(round(len(g) * 0.15))
        items["train"] += g[:n_tr]
        items["val"] += g[n_tr:n_tr + n_va]
        items["test"] += g[n_tr + n_va:]
    labels = {k["pid"]: k["murmur"] for k in kept}
    groups = {k["pid"]: k["pid"] for k in kept}              # ZCHSound: 1 bola = 1 yozuv
    meta = {k["pid"]: {"dx": k["dx"], "age_days": k["age_days"]} for k in kept}
    return items, labels, groups, meta


class SiteDataset(WindowDataset):
    def __getitem__(self, k):
        x, ym, yo = super().__getitem__(k)
        return x, ym, yo, self.items[self.index[k][0]]["site"]


# ---------------------------------------------------------------- o'qitish
def site_class_weights(ds: SiteDataset, sites: set[int]) -> torch.Tensor:
    """Har bir manba ichida sinflar teng vaznlanadi: w[site, class] = N_site / (2 · N_site,class)."""
    cnt = np.zeros((2, 2))
    for i, _ in ds.index:
        it = ds.items[i]
        if it["murmur"] in (0, 1):
            cnt[it["site"], it["murmur"]] += 1
    w = np.zeros((2, 2), dtype=np.float32)
    for s in sites:
        for c in (0, 1):
            w[s, c] = cnt[s].sum() / (2 * cnt[s, c]) if cnt[s, c] else 0.0
    return torch.tensor(w)


def val_score(model, val_items: list[dict], labels: dict, device) -> float:
    """Manbalar bo'yicha AUROC o'rtachasi (aralash AUROC manba prior'iga bog'liq bo'lib qolmasin)."""
    aucs = []
    for s in sorted({it["site"] for it in val_items}):
        part = [it for it in val_items if it["site"] == s]
        sc = patient_scores(model, part, device)
        ids = [p for p in sc if labels.get(p) is not None]
        a = auroc(np.array([labels[p] for p in ids]), np.array([sc[p]["p_murmur"] for p in ids]))
        if not np.isnan(a):
            aucs.append(a)
    return float(np.mean(aucs)) if aucs else float("nan")


def fit(train_items, val_items, labels, device, epochs, seed, batch=128, lr=1e-3, log=print, init_state=None):
    """init_state — joriy model og'irliklari (state_dict): berilsa, noldan emas, shundan davom ettirib o'qitiladi."""
    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
    sites = {it["site"] for it in train_items}
    ds = SiteDataset(train_items, augment=True)
    wtab = site_class_weights(ds, sites).to(device)
    out_y = np.array([ds.items[i]["outcome"] for i, _ in ds.index])
    out_y = out_y[out_y != IGNORE]
    w_abn = float((out_y == 0).sum() / max((out_y == 1).sum(), 1)) if len(out_y) else 1.0
    loader = torch.utils.data.DataLoader(ds, batch_size=batch, shuffle=True, drop_last=len(ds) > batch)
    model = PCGNet().to(device)
    if init_state is not None:
        model.load_state_dict(init_state)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=max(1, epochs * len(loader)))
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    out_w = torch.tensor([1.0, w_abn], device=device)
    best, best_state = -1.0, None
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        for x, ym, yo, st in loader:
            x, ym, yo, st = x.to(device), ym.to(device), yo.to(device), st.to(device)
            with torch.autocast(device.type, enabled=use_amp):
                lm, lo = model(x)
            lm, lo = lm.float(), lo.float()
            valid = ym != IGNORE
            w = torch.where(valid, wtab[st, ym.clamp(min=0)], torch.zeros_like(ym, dtype=torch.float32))
            ce = F.cross_entropy(lm, ym.clamp(min=0), reduction="none")
            loss_m = (ce * w).sum() / w.sum().clamp(min=1e-6)
            ov = yo != IGNORE
            loss_o = (F.cross_entropy(lo, yo.clamp(min=0), reduction="none") * out_w[yo.clamp(min=0)] * ov).sum() / ov.sum().clamp(min=1)
            loss = loss_m + 0.5 * loss_o
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update(); sched.step()
            total += loss.detach().item() * len(x)
        vs = val_score(model, val_items, labels, device)
        if epoch % 5 == 0 or epoch == 1:
            log(f"    epoch {epoch:3d}  loss {total / max(len(ds), 1):.4f}  val AUROC (manbalar o'rtachasi) {vs:.4f}")
        if not np.isnan(vs) and vs > best:
            best, best_state = vs, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best


# ---------------------------------------------------------------- baholash
def arrays(scores: dict, labels: dict, groups: dict):
    ids = [p for p in scores if labels.get(p) is not None]
    return (ids, np.array([labels[p] for p in ids]), np.array([scores[p]["p_murmur"] for p in ids]),
            np.array([scores[p]["agreement"] for p in ids]), [groups[p] for p in ids])


def decide(s, agr, low, high):
    abstain = (agr < AGREE_MIN) | ((s > low) & (s < high))
    return s >= high, ~abstain


def conf(y, dec, keep):
    tp = int(((dec == 1) & (y == 1) & keep).sum()); fn = int(((dec == 0) & (y == 1) & keep).sum())
    tn = int(((dec == 0) & (y == 0) & keep).sum()); fp = int(((dec == 1) & (y == 0) & keep).sum())
    return {"tp": tp, "fn": fn, "tn": tn, "fp": fp,
            "sensitivity": tp / (tp + fn) if tp + fn else float("nan"),
            "specificity": tn / (tn + fp) if tn + fp else float("nan")}


def site_report(scores, labels, groups, low, high, n_boot=1000, seed=0):
    ids, y, s, agr, grp = arrays(scores, labels, groups)
    dec, keep = decide(s, agr, low, high)
    rep = {"n": len(ids), "n_pos": int(y.sum()), "auroc": auroc(y, s), "abstain_rate": float(1 - keep.mean()), **conf(y, dec, keep)}
    by_g = defaultdict(list)
    for i, g in enumerate(grp):
        by_g[g].append(i)
    keys, rng = list(by_g), np.random.default_rng(seed)
    boots = defaultdict(list)
    for _ in range(n_boot):
        idx = np.array([i for k in rng.choice(len(keys), len(keys)) for i in by_g[keys[k]]])
        a = auroc(y[idx], s[idx]); c = conf(y[idx], dec[idx], keep[idx])
        for name, v in (("auroc", a), ("sensitivity", c["sensitivity"]), ("specificity", c["specificity"])):
            if not np.isnan(v):
                boots[name].append(v)
    rep["ci95"] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in boots.items()}
    return rep


def zch_breakdown(scores, labels, meta, low, high):
    ids = [p for p in scores if p in meta and labels.get(p) is not None]
    y = np.array([labels[p] for p in ids]); s = np.array([scores[p]["p_murmur"] for p in ids])
    age = np.array([meta[p]["age_days"] if meta[p]["age_days"] is not None else np.nan for p in ids])
    out = {"age_only_auroc": auroc(y, -np.nan_to_num(age, nan=np.nanmedian(age))), "by_age": {}, "by_dx": {}}
    for band in sorted({age_band(a if not np.isnan(a) else None) for a in age}):
        m = np.array([age_band(a if not np.isnan(a) else None) == band for a in age])
        out["by_age"][band] = {"n": int(m.sum()), "n_pos": int(y[m].sum()), "auroc": auroc(y[m], s[m]) if m.sum() else float("nan")}
    for dx in sorted({meta[p]["dx"] for p in ids}):
        m = np.array([meta[p]["dx"] == dx for p in ids])
        out["by_dx"][dx] = {"n": int(m.sum()), "flagged": float((s[m] >= high).mean())}
    return out


def f3(x):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def ci(rep, k):
    lo_hi = rep["ci95"].get(k)
    return f"{f3(rep[k])} ({lo_hi[0]:.3f}–{lo_hi[1]:.3f})" if lo_hi else f3(rep[k])


# ---------------------------------------------------------------- asosiy
def main() -> None:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--circor-dir", type=Path, required=True)
    ap.add_argument("--zch-dir", type=Path, required=True)
    ap.add_argument("--circor-split", type=Path, default=Path("weights/pcg/split.json"))
    ap.add_argument("--out", type=Path, default=Path("weights/pcg_multisite"))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-sens", type=float, default=0.95)
    ap.add_argument("--min-spec", type=float, default=0.90)
    args = ap.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"qurilma: {device}", flush=True)

    t0 = time.time()
    c_items, c_labels, c_groups = load_circor(args.circor_dir, args.circor_split)
    z_items, z_labels, z_groups, z_meta = load_zch(args.zch_dir, args.seed)
    labels, groups = {**c_labels, **z_labels}, {**c_groups, **z_groups}
    print(f"xususiyatlar {time.time() - t0:.0f} s | CirCor yozuvlar { {k: len(v) for k, v in c_items.items()} } "
          f"| ZCH bolalar { {k: len(v) for k, v in z_items.items()} } (test TYN {sum(i['murmur'] for i in z_items['test'])})", flush=True)

    results, models = {}, {}
    for name, sites in (("circor_only", {0}), ("zch_only", {1}), ("multisite", {0, 1})):
        print(f"\n== {name} ==", flush=True)
        pick = lambda d: [it for s in sorted(sites) for it in (c_items if s == 0 else z_items)[d]]   # noqa: E731
        t1 = time.time()
        model, best = fit(pick("train"), pick("val"), labels, device, args.epochs, args.seed, log=lambda m: print(m, flush=True))
        val_sc = patient_scores(model, pick("val"), device)
        ids = [p for p in val_sc if labels.get(p) is not None]
        low, high = choose_thresholds(np.array([labels[p] for p in ids]), np.array([val_sc[p]["p_murmur"] for p in ids]),
                                      args.min_sens, args.min_spec)
        res = {"val_auroc_mean_sites": best, "thresholds": {"low": low, "high": high}, "train_seconds": round(time.time() - t1)}
        for site, (its, nm) in {"circor": (c_items["test"], "circor"), "zch": (z_items["test"], "zch")}.items():
            sc = patient_scores(model, its, device)
            res[site] = site_report(sc, labels, groups, low, high)
            if site == "zch":
                res["zch_breakdown"] = zch_breakdown(sc, labels, z_meta, low, high)
        results[name], models[name] = res, model
        print(f"  CirCor test AUROC {ci(res['circor'], 'auroc')} | ZCH test AUROC {ci(res['zch'], 'auroc')}", flush=True)

    # ---- qabul mezoni (oldindan belgilangan)
    base, multi = results["circor_only"], results["multisite"]
    A = multi["circor"]["auroc"] >= base["circor"]["auroc"] - 0.03
    B1 = multi["zch"]["auroc"] >= base["zch"]["auroc"] + 0.10
    B2 = multi["zch"]["auroc"] >= multi["zch_breakdown"]["age_only_auroc"] + 0.05
    verdict = {"A_circor_not_worse": bool(A), "B1_zch_gain_ge_0.10": bool(B1), "B2_beyond_age_ge_0.05": bool(B2),
               "accepted": bool(A and B1 and B2)}
    print("\nQABUL MEZONI:", verdict, flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    report = {"seed": args.seed, "epochs": args.epochs, "device": str(device), "results": results, "verdict": verdict}
    (args.out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    (args.out / "zch_split.json").write_text(json.dumps({k: [i["pid"] for i in v] for k, v in z_items.items()}), encoding="utf-8")

    lines = ["# Ko'p manbali PCG modeli: CirCor + ZCHSound", "",
             f"Urug' {args.seed}, {args.epochs} epoch. Uchala model bir xil kod bilan o'qitilgan; AUROC — bola darajasida bootstrap 95% CI.", "",
             "| Model | CirCor testi (n, shovqinli) AUROC | ZCHSound testi (n, nuqsonli) AUROC |", "|---|---|---|"]
    for name in ("circor_only", "zch_only", "multisite"):
        r = results[name]
        lines.append(f"| {name} | {ci(r['circor'], 'auroc')} ({r['circor']['n']}, {r['circor']['n_pos']}) | "
                     f"{ci(r['zch'], 'auroc')} ({r['zch']['n']}, {r['zch']['n_pos']}) |")
    lines += ["", "## Bitta chegarada qaror (chegara birlashgan validatsiyada tanlangan: sezgirlik ≥95%, spetsifiklik ≥90%)", "",
              "| Model | Sinov | Sezgirlik | Spetsifiklik | Abstain |", "|---|---|---|---|---|"]
    for name in ("circor_only", "zch_only", "multisite"):
        for site in ("circor", "zch"):
            r = results[name][site]
            lines.append(f"| {name} | {site} | {ci(r, 'sensitivity')} | {ci(r, 'specificity')} | {f3(r['abstain_rate'])} |")
    lines += ["", "## ZCHSound testi: yosh va tashxis bo'yicha", ""]
    for name in ("circor_only", "multisite"):
        b = results[name]["zch_breakdown"]
        lines.append(f"**{name}** — «faqat yosh» chizig'i AUROC {f3(b['age_only_auroc'])}; yosh guruhlari ichida: " +
                     "; ".join(f"{k}: n={v['n']} (nuqsonli {v['n_pos']}) AUROC {f3(v['auroc'])}" for k, v in b["by_age"].items()) +
                     "; belgilanganlar ulushi: " + ", ".join(f"{k} {f3(v['flagged'])}" for k, v in b["by_dx"].items()))
        lines.append("")
    lines += ["## Oldindan belgilangan qabul mezoni", "",
              f"- A (CirCor'da 0.03 dan ko'p yomonlashmaslik): **{'bajarildi' if A else 'BAJARILMADI'}**",
              f"- B1 (ZCHSound'da kamida +0.10): **{'bajarildi' if B1 else 'BAJARILMADI'}**",
              f"- B2 («faqat yosh»dan kamida +0.05 yuqori): **{'bajarildi' if B2 else 'BAJARILMADI'}**",
              f"- Mezon bo'yicha xulosa: **{'qabul' if verdict['accepted'] else 'rad'}**. "
              "LEKIN: ZCHSound'da yozuv-blok izi topilgan (`research/control_zch_batch.py`), shuning uchun B1/B2 isbot emas; "
              "qaror: RAD ETILDI (2026-10-30).", "",
              "Cheklov: ZCHSound sinov to'plami o'qitish to'plami bilan BIR MANBADAN (boshqa bolalar, lekin bir shifoxona). "
              "Bu «uchinchi, ko'rilmagan klinika»da ishlashini isbotlamaydi; haqiqiy tashqi tekshiruv uchun mahalliy yozuvlar kerak."]
    (args.out / "report.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- multisite modelni eksport (qabul qilinsa ham, tahlil uchun saqlanadi; qaror hisobotda)
    model = models["multisite"].eval().cpu()
    torch.save(model.state_dict(), args.out / "pcg.pt")
    t_frames = z_items["train"][0]["x"].shape[-1]
    torch.onnx.export(model, torch.zeros(1, 1, N_MELS, t_frames), args.out / "pcg.onnx",
                      input_names=["logmel"], output_names=["murmur_logits", "outcome_logits"],
                      dynamic_axes={"logmel": {0: "n"}, "murmur_logits": {0: "n"}, "outcome_logits": {0: "n"}},
                      opset_version=17, dynamo=False)
    card = {"name": "pcg_murmur_cnn_multisite", "version": time.strftime("%Y.%m.%d"),
            "task": "pediatrik PCG: shovqin / yurak nuqsoni (ExoKG kerak) — ko'p manbali",
            "dataset": "CirCor DigiScope + ZCHSound", "weights": "pcg.onnx",
            "thresholds": {"murmur_low": multi["thresholds"]["low"], "murmur_high": multi["thresholds"]["high"],
                           "window_agreement": AGREE_MIN, "min_age_days": 29},
            "metrics": {"circor_test": multi["circor"], "zch_test": multi["zch"], "verdict": verdict},
            "training": {"seed": args.seed, "epochs": args.epochs, "sr": TARGET_SR, "win_s": WIN_S,
                         "site_balanced_loss": True, "device": str(device)}}
    (args.out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"\nsaqlandi: {args.out}  | umumiy vaqt {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
