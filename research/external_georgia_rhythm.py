"""AFIB modeli + ritm modeli BIRIKMASI: uchinchi mustaqil to'plamda tekshiruv — Georgia 12-Lead ECG Challenge (G12EC, AQSh, Emory),
PhysioNet Challenge 2021 v1.0.3 (CC BY 4.0), 10 344 EKG. Ikkala model ham bu to'plamni hech qachon ko'rmagan
(AFIB modeli PTB-XL'da, ritm modeli Chapman'da o'qitilgan).

    python -m research.external_georgia_rhythm --data-dir C:\\Users\\user\\data\\georgia

BIRIKMA QOIDASI (natijadan OLDIN yozilgan, ikkala modelning chegaralari o'zgartirilmaydi):
  - AFIB modeli abstain qilsa → birikma ham abstain;
  - AFIB modeli «AFIB yo'q» desa → AFIB yo'q;
  - AFIB modeli «AFIB» desa, LEKIN ritm modelining eng ehtimolli sinfi AFL, SVT yoki STACH bo'lsa va uning AFIB ehtimoli
    o'z chegarasidan past bo'lsa → «tez supraventrikulyar ritm (titrash/SVT/AFIB) — shifokor aniqlashtiradi».
    Bu xavfni PASAYTIRMAYDI: holat baribir «aritmiya» deb belgilanadi, faqat aniq «AFIB» tashxisi qo'yilmaydi;
  - qolgan holda → AFIB.

OLDINDAN BELGILANGAN MEZONLAR (Georgia, bir marta):
  1. birikmaning AFIB sezgirligi ≥ 0.85;
  2. birikmaning AFIB o'ziga xosligi ≥ 0.92;
  3. AFL + SVT + STACH holatlarining «AFIB» deb belgilangani ≤ 25%;
  4. xavfsizlik: AFIB holatlarining «AFIB» yoki «tez ritm» deb belgilangani (ya'ni hech bo'lmasa aritmiya bayrog'i) ≥ 0.95;
  5. foyda: o'ziga xoslik AFIB modelining yolg'iz o'zidan ≥ 0.02 yuqori, sezgirlik yo'qotishi ≤ 0.05;
  6. abstain ≤ 20%.
Hammasi bajarilsa passed=true. Aks holda birikma dasturga ulanmaydi.

Yorliq (SNOMED, Dx qatori), ustuvorlik: AFIB 164889003 > AFL 164890007 > SVT (426761007, 67198005, 713422000) >
STACH 427084000 > SBRAD 426177001 > SR (426783006, 427393009). Kardiostimulyator (10370003) bo'lsa yoki ritm kodi bo'lmasa — chiqariladi.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ecg.model import ECGModel
from ecg.signal import preprocess
from research.train_lowef import boot
from research.train_pcg import auroc

CLASSES = ["SR", "SBRAD", "STACH", "AFIB", "AFL", "SVT"]
SNOMED_PRIORITY = [({"164889003"}, "AFIB"), ({"164890007"}, "AFL"), ({"426761007", "67198005", "713422000"}, "SVT"),
                   ({"427084000"}, "STACH"), ({"426177001"}, "SBRAD"), ({"426783006", "427393009"}, "SR")]
EXCLUDE = {"10370003"}
VETO = {"AFL", "SVT", "STACH"}
GATES = {"sensitivity": 0.85, "specificity": 0.92, "max_fast_called_afib": 0.25, "flag_sensitivity": 0.95,
         "min_specificity_gain": 0.02, "max_sensitivity_loss": 0.05, "max_abstain": 0.20}


def read_record(hea: Path) -> tuple[np.ndarray, float, tuple[str, ...], float | None, set[str]]:
    from scipy.io import loadmat
    lines = hea.read_text(encoding="utf-8", errors="replace").splitlines()
    fs = float(lines[0].split()[2])
    sig_lines = [l.split() for l in lines[1:] if l and not l.startswith("#")]
    gains = np.array([float(s[2].split("/")[0].split("(")[0]) for s in sig_lines], dtype=np.float32)
    leads = tuple(s[-1].upper() for s in sig_lines)
    x = loadmat(str(hea.with_suffix(".mat")))["val"].astype(np.float32) / gains[:, None]
    age, dx = None, set()
    for l in lines:
        if l.startswith("# Age:"):
            try:
                v = float(l.split(":", 1)[1])
                age = v if np.isfinite(v) else None
            except ValueError:
                pass
        if l.startswith("# Dx:"):
            dx = {c.strip() for c in l.split(":", 1)[1].split(",") if c.strip()}
    return x, fs, leads, age, dx


def label(dx: set[str]) -> str | None:
    if dx & EXCLUDE:
        return None
    return next((c for codes, c in SNOMED_PRIORITY if dx & codes), None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--afib-weights", type=Path, default=Path("weights/ecg"))
    ap.add_argument("--rhythm-weights", type=Path, default=Path("weights/ecg_rhythm"))
    ap.add_argument("--out", type=Path, default=Path("docs/experiments/ecg_georgia_combined.json"))
    a = ap.parse_args()
    import onnxruntime as ort

    afib = ECGModel.from_dir(a.afib_weights)
    assert afib is not None, "weights/ecg topilmadi"
    card = json.loads((a.rhythm_weights / "model_card.json").read_text(encoding="utf-8"))
    r_thr = float(card["thresholds"]["afib_threshold"])
    sess = ort.InferenceSession(str(a.rhythm_weights / card["weights"]), providers=["CPUExecutionProvider"])

    rows, skipped = [], {"no_rhythm_or_paced": 0, "unreadable": 0}
    heas = sorted(a.data_dir.rglob("*.hea"))
    for k, hea in enumerate(heas):
        try:
            x, fs, leads, age, dx = read_record(hea)
        except Exception:
            skipped["unreadable"] += 1
            continue
        lab = label(dx)
        if lab is None:
            skipped["no_rhythm_or_paced"] += 1
            continue
        ev = afib.analyze(x, fs, leads, age_years=age)
        v = ev.value if isinstance(ev.value, dict) else {}
        pos = (not ev.abstained) and ev.risk.value in ("high", "very_high")
        lg = sess.run(None, {"ecg": preprocess(x, fs)[None].astype(np.float32)})[0][0]
        pr = np.exp(lg - lg.max()); pr /= pr.sum()
        top = CLASSES[int(pr.argmax())]
        vetoed = pos and top in VETO and pr[3] < r_thr
        rows.append({"id": hea.stem, "y": lab, "age": age, "p_afib": v.get("p_afib"), "abstained": ev.abstained,
                     "afib_alone": pos, "combined": pos and not vetoed, "fast_flag": vetoed, "rhythm_top": top,
                     "p_rhythm": [round(float(q), 5) for q in pr]})
        if (k + 1) % 2000 == 0:
            print(f"  {k + 1}/{len(heas)}", flush=True)

    y = np.array([r["y"] for r in rows]); is_af = y == "AFIB"
    ab = np.array([r["abstained"] for r in rows]); dec = ~ab
    alone = np.array([r["afib_alone"] for r in rows]); comb = np.array([r["combined"] for r in rows])
    flag = comb | np.array([r["fast_flag"] for r in rows])
    fast = np.isin(y, list(VETO))

    def sens_spec(pred):
        return (round(float(pred[dec & is_af].mean()), 4), round(float((~pred[dec & ~is_af]).mean()), 4))

    def by_class(pred):
        return {c: f"{int(pred[dec & (y == c)].sum())}/{int((dec & (y == c)).sum())}" for c in CLASSES}

    s_al, sp_al = sens_spec(alone); s_c, sp_c = sens_spec(comb)
    has_p = np.array([r["p_afib"] is not None for r in rows])
    pa = np.array([r["p_afib"] if r["p_afib"] is not None else np.nan for r in rows])
    prh = np.array([r["p_rhythm"] for r in rows])
    res = {
        "n": len(rows), "skipped": skipped, "class_counts": {c: int((y == c).sum()) for c in CLASSES},
        "abstain_rate": round(float(ab.mean()), 4),
        "afib_alone": {"sensitivity": s_al, "specificity": sp_al,
                       "auroc": round(auroc(is_af[has_p].astype(int), pa[has_p]), 4),
                       "auroc_ci95": boot(is_af[has_p].astype(int), pa[has_p]),
                       "fast_called_afib": round(float(alone[dec & fast].mean()), 4),
                       "called_afib_by_true_class": by_class(alone)},
        "rhythm_model": {"afib_auroc": round(auroc(is_af.astype(int), prh[:, 3]), 4),
                         "per_class_auroc": {c: round(auroc((y == c).astype(int), prh[:, k]), 4)
                                             for k, c in enumerate(CLASSES) if 0 < (y == c).sum() < len(y)}},
        "combined": {"sensitivity": s_c, "specificity": sp_c,
                     "fast_called_afib": round(float(comb[dec & fast].mean()), 4),
                     "flag_sensitivity": round(float(flag[dec & is_af].mean()), 4),
                     "called_afib_by_true_class": by_class(comb), "fast_flag_by_true_class": by_class(flag & ~comb)},
        "rhythm_threshold": r_thr, "gates": GATES,
    }
    c = res["combined"]
    res["checks"] = {"sensitivity": c["sensitivity"] >= GATES["sensitivity"],
                     "specificity": c["specificity"] >= GATES["specificity"],
                     "fast_called_afib": c["fast_called_afib"] <= GATES["max_fast_called_afib"],
                     "flag_sensitivity": c["flag_sensitivity"] >= GATES["flag_sensitivity"],
                     "specificity_gain": sp_c - sp_al >= GATES["min_specificity_gain"],
                     "sensitivity_loss": s_al - s_c <= GATES["max_sensitivity_loss"],
                     "abstain": res["abstain_rate"] <= GATES["max_abstain"]}
    res["passed"] = all(res["checks"].values())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
