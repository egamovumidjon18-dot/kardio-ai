"""PTB-XL'da o'qitilgan EKG modelining (AFIB) TASHQI tekshiruvi: Chapman–Shaoxing (Xitoy), CC0, 10 646 EKG.

    python -m research.external_ecg_chapman --data-dir C:\\Users\\user\\data\\chapman --out docs/experiments/ecg_chapman_external.json

Model butunlay boshqa mamlakat, boshqa apparat va boshqa aholida, QAYTA O'QITILMASDAN, aynan dasturdagi yo'l bilan
(`ECGModel.analyze`: sifat tekshiruvi → preprocess → ONNX → model card'dagi chegaralar) sinaladi.

OLDINDAN BELGILANGAN MEZONLAR (natijadan OLDIN yozilgan):
  1. AFIB AUROC ≥ 0.90 va bootstrap 95% CI pastki chegarasi ≥ 0.88;
  2. qaror qilingan holatlarda sezgirlik ≥ 0.85 va o'ziga xoslik ≥ 0.85 (chegaralar PTB-XL val'dan, O'ZGARTIRILMAYDI);
  3. sifat yoki noaniqlik tufayli abstain ≤ 20%.
Yorliq: Rhythm == "AFIB" → 1; qolganlari → 0. Bo'lmachalar titrashi (AF, flutter) alohida hisobot qilinadi
(model uni AFIB deb belgilasa — klinik jihatdan xavfli xato emas, lekin asosiy ko'rsatkichda «yolg'on musbat» sanaladi).
Chapman signallari mikrovoltda → mV ga o'tkaziladi (/1000), 500 Hz, 10 s.
"""
from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path

import numpy as np

from ecg.model import ECGModel
from research.train_lowef import boot
from research.train_pcg import auroc

FS = 500.0
LEADS = ("I", "II", "III", "AVR", "AVL", "AVF", "V1", "V2", "V3", "V4", "V5", "V6")
CRITERIA = {"auroc": 0.90, "auroc_ci_low": 0.88, "sensitivity": 0.85, "specificity": 0.85, "max_abstain": 0.20}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--weights", type=Path, default=Path("weights/ecg"))
    ap.add_argument("--out", type=Path, default=Path("docs/experiments/ecg_chapman_external.json"))
    a = ap.parse_args()
    import pandas as pd

    model = ECGModel.from_dir(a.weights)
    assert model is not None, "weights/ecg topilmadi"
    diag = pd.read_excel(a.data_dir / "Diagnostics.xlsx").set_index("FileName")
    z = zipfile.ZipFile(a.data_dir / "ECGData.zip")
    rows = []
    for k, name in enumerate(n for n in z.namelist() if n.endswith(".csv")):
        fid = Path(name).stem
        if fid not in diag.index:
            continue
        x = pd.read_csv(io.BytesIO(z.read(name))).to_numpy(dtype=np.float32).T / 1000.0   # µV → mV, [12, N]
        d = diag.loc[fid]
        ev = model.analyze(x, FS, LEADS, age_years=float(d["PatientAge"]))
        v = ev.value if isinstance(ev.value, dict) else {}
        reason = ev.explanation[0] if ev.abstained else ""
        rows.append({"id": fid, "rhythm": d["Rhythm"], "age": float(d["PatientAge"]), "sex": d["Gender"],
                     "p": v.get("p_afib"), "abstained": ev.abstained,
                     "quality_reject": ev.abstained and ("sifatsiz" in reason or "tarmoq" in reason or "qisqa" in reason),
                     "decided_afib": (not ev.abstained) and ev.risk.value in ("high", "very_high")})
        if (k + 1) % 2000 == 0:
            print(f"  {k + 1} ta EKG", flush=True)

    y = np.array([r["rhythm"] == "AFIB" for r in rows], dtype=int)
    has_p = np.array([r["p"] is not None for r in rows])
    p = np.array([r["p"] if r["p"] is not None else np.nan for r in rows])
    ab = np.array([r["abstained"] for r in rows]); qr = np.array([r["quality_reject"] for r in rows])
    dec = ~ab; pred = np.array([r["decided_afib"] for r in rows])
    tp = int(np.sum(pred & (y == 1) & dec)); fn = int(np.sum(~pred & (y == 1) & dec))
    tn = int(np.sum(~pred & (y == 0) & dec)); fp = int(np.sum(pred & (y == 0) & dec))
    yy, pp = y[has_p], p[has_p]
    flutter = np.array([r["rhythm"] == "AF" for r in rows])
    res = {
        "n": len(rows), "n_afib": int(y.sum()), "n_with_probability": int(has_p.sum()),
        "auroc": round(auroc(yy, pp), 4), "auroc_ci95": boot(yy, pp),
        "abstain_rate": round(float(ab.mean()), 4), "quality_reject_rate": round(float(qr.mean()), 4),
        "sensitivity": round(tp / max(1, tp + fn), 4), "specificity": round(tn / max(1, tn + fp), 4),
        "ppv": round(tp / max(1, tp + fp), 4), "npv": round(tn / max(1, tn + fn), 4), "tp": tp, "fn": fn, "tn": tn, "fp": fp,
        "thresholds_from_ptbxl": {"afib_low": model.low, "afib_high": model.high},
        "flutter_called_afib": f"{int(np.sum(pred & flutter & dec))}/{int(np.sum(flutter & dec))}",
        "fp_by_rhythm": {r: int(np.sum(pred & dec & (y == 0) & np.array([x["rhythm"] == r for x in rows])))
                         for r in sorted({x["rhythm"] for x in rows}) if r != "AFIB"},
        "auroc_by_sex": {s: round(auroc(yy[m], pp[m]), 4) for s in ("MALE", "FEMALE")
                         for m in [np.array([r["sex"] == s for r in rows])[has_p]]},
        "auroc_by_age": {}, "criteria": CRITERIA,
    }
    ages = np.array([r["age"] for r in rows])[has_p]
    for lo, hi in ((18, 50), (50, 70), (70, 120)):
        m = (ages >= lo) & (ages < hi)
        if 0 < yy[m].sum() < m.sum():
            res["auroc_by_age"][f"{lo}-{hi}"] = {"n": int(m.sum()), "afib": int(yy[m].sum()), "auroc": round(auroc(yy[m], pp[m]), 4)}
    res["checks"] = {"auroc": res["auroc"] >= CRITERIA["auroc"], "auroc_ci_low": res["auroc_ci95"][0] >= CRITERIA["auroc_ci_low"],
                     "sensitivity": res["sensitivity"] >= CRITERIA["sensitivity"],
                     "specificity": res["specificity"] >= CRITERIA["specificity"],
                     "abstain": res["abstain_rate"] <= CRITERIA["max_abstain"]}
    res["passed"] = all(res["checks"].values())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
