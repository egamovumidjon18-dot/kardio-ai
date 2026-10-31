"""Uchidan-uchiga tekshiruv: har bir AI modul DASTUR ORQALI (HTTP API, haqiqiy og'irliklar) javobi ma'lum namunalarda sinaladi.

    python -m research.e2e_check --data C:\\Users\\user\\data --out docs/experiments/e2e_check.md

Bu yangi validatsiya EMAS (u alohida hisobotlarda): bu — «modellar dasturda haqiqatan to'g'ri ulanganmi va kutilgan
natijani beryaptimi» degan nazorat. Har modul uchun test bo'limidan har bir sinfdan N ta namuna olinadi (deterministik).
Kutilgan: musbat holatlarning ko'pchiligi «xavf bor», manfiylarning ko'pchiligi «xavf yo'q» deb chiqishi; abstain hisoblanadi.
"""
from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np

LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def to_csv(sig: np.ndarray, names=LEADS) -> bytes:
    buf = io.StringIO()
    buf.write(",".join(names) + "\n")
    for row in np.asarray(sig, dtype=np.float32).T:
        buf.write(",".join(f"{v:.4f}" for v in row) + "\n")
    return buf.getvalue().encode()


def tally(rows: list[dict]) -> dict:
    pos = [r for r in rows if r["truth"]]
    neg = [r for r in rows if not r["truth"]]
    dec_pos = [r for r in pos if r["call"] is not None]
    dec_neg = [r for r in neg if r["call"] is not None]
    return {"n_pos": len(pos), "n_neg": len(neg),
            "tp": sum(r["call"] for r in dec_pos), "fn": sum(not r["call"] for r in dec_pos),
            "tn": sum(not r["call"] for r in dec_neg), "fp": sum(r["call"] for r in dec_neg),
            "abstain": sum(r["call"] is None for r in rows), "errors": sum(bool(r.get("error")) for r in rows)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--out", type=Path, default=Path("docs/experiments/e2e_check.md"))
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    os.environ["CARDIOPATH_DB"] = str(tmp / "e2e.db")
    os.environ["CARDIOPATH_AUTH"] = "off"
    from fastapi.testclient import TestClient
    from api.main import default_app
    from ecg.signal import read_wfdb

    c = TestClient(default_app())
    models = c.get("/models").json()
    health = c.get("/health").json()
    results: dict[str, dict] = {}
    t0 = time.time()

    def episode(ref: str, pop: str) -> str:
        return c.post("/episodes", json={"patient_ref": ref, "actor": "e2e", "population": pop}).json()["id"]

    # ---------------------------------------------------------------- 1. PCG (CirCor test bemorlari)
    circor = a.data / "circor" / "the-circor-digiscope-phonocardiogram-dataset-1.0.3"
    split = json.loads(Path("weights/pcg/split.json").read_text(encoding="utf-8"))
    test_ids = {str(x) for x in split["test"]}
    age_days = {"Infant": 180, "Child": 2200, "Adolescent": 4700}
    meta = [r for r in csv.DictReader(open(circor / "training_data.csv", encoding="utf-8"))
            if r["Patient ID"] in test_ids and r["Murmur"] in ("Present", "Absent") and r["Age"] in age_days]
    rows = []
    for label in ("Present", "Absent"):
        for r in [m for m in meta if m["Murmur"] == label][:a.n]:
            pid = r["Patient ID"]
            files = sorted((circor / "training_data").glob(f"{pid}_*.wav"))
            eid = episode(f"E2E-PCG-{pid}", "pediatric")
            resp = c.post(f"/episodes/{eid}/screening", data={"actor": "e2e", "age_days": str(age_days[r["Age"]])},
                          files=[("recordings", (f.name, f.read_bytes(), "audio/wav")) for f in files])
            if resp.status_code != 200:
                rows.append({"truth": label == "Present", "call": None, "error": resp.text[:120]}); continue
            ai = resp.json()["concordance"]["ai"]
            call = None if ai is None or ai["abstained"] else ai["risk"] in ("moderate", "high", "very_high")
            rows.append({"truth": label == "Present", "call": call})
    results["pcg"] = {"name": "Yurak tovushi: shovqin bor/yo'q", "data": "CirCor test (bemor darajasida)", **tally(rows)}

    # ---------------------------------------------------------------- 2. EKG AFIB (PTB-XL rasmiy test fold 10)
    ptb = a.data / "ptbxl" / "ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3"
    db = list(csv.DictReader(open(ptb / "ptbxl_database.csv", encoding="utf-8")))
    afib = [r for r in db if r["strat_fold"] == "10" and "AFIB" in ast.literal_eval(r["scp_codes"])]
    norm = [r for r in db if r["strat_fold"] == "10" and set(ast.literal_eval(r["scp_codes"])) == {"NORM"}]
    rows = []
    for truth, group in ((True, afib), (False, norm)):
        for r in group[:a.n]:
            sig, fs, names = read_wfdb(ptb / r["filename_hr"])
            eid = episode(f"E2E-ECG-{r['ecg_id']}", "adult")
            age = float(r["age"]) if r["age"] and float(r["age"]) < 120 else 60
            resp = c.post(f"/episodes/{eid}/ecg", data={"actor": "e2e", "fs": str(fs), "age_years": str(age)},
                          files={"file": ("e.csv", to_csv(sig, list(names)), "text/csv")})
            if resp.status_code != 200:
                rows.append({"truth": truth, "call": None, "error": resp.text[:120]}); continue
            ev = resp.json()["evidence"]
            rows.append({"truth": truth, "call": None if ev["abstained"] else ev["risk"] in ("high", "very_high")})
    results["ecg_afib"] = {"name": "EKG: bo'lmachalar fibrillyatsiyasi", "data": "PTB-XL fold 10 (500 Hz, mV)", **tally(rows)}

    # ---------------------------------------------------------------- 3–4. AI-EKG past EF va tuzilmaviy (EchoNext test)
    en = a.data / "echonext"
    meta = [r for r in csv.DictReader(open(en / "echonext_metadata_100k.csv", encoding="utf-8")) if r["split"] == "test"]
    wav = np.load(en / "EchoNext_test_waveforms.npy", mmap_mode="r")
    rows_ef, rows_shd = [], []
    pick = [i for i, r in enumerate(meta) if r["lvef_lte_45_flag"] == "1"][:a.n] + [i for i, r in enumerate(meta) if r["lvef_lte_45_flag"] == "0"][:a.n]
    for i in pick:
        r = meta[i]
        sig = np.asarray(wav[i, 0], dtype=np.float32).T            # [12, 2500], 250 Hz (EchoNext oldindan standartlashtirilgan)
        eid = episode(f"E2E-EN-{i}", "adult")
        resp = c.post(f"/episodes/{eid}/ecg", data={"actor": "e2e", "fs": "250", "age_years": str(float(r["age_at_ecg"] or 60))},
                      files={"file": ("e.csv", to_csv(sig), "text/csv")})
        if resp.status_code != 200 or "low_ef" not in resp.json():
            rows_ef.append({"truth": r["lvef_lte_45_flag"] == "1", "call": None, "error": resp.text[:120]}); continue
        lev = resp.json()["low_ef"]["evidence"]
        rows_ef.append({"truth": r["lvef_lte_45_flag"] == "1", "call": None if lev["abstained"] else lev["risk"] != "low"})
        if "structural" in resp.json():
            sev = resp.json()["structural"]["evidence"]
            rows_shd.append({"truth": r["shd_moderate_or_greater_flag"] == "1", "call": None if sev["abstained"] else sev["risk"] != "low"})
    results["ecg_low_ef"] = {"name": "AI-EKG: past EF (≤45%)", "data": "EchoNext test (250 Hz, oldindan standartlashtirilgan)", **tally(rows_ef)}
    results["ecg_shd"] = {"name": "AI-EKG: tuzilmaviy kasallik", "data": "EchoNext test, xuddi shu EKG'lar", **tally(rows_shd)}

    # ---------------------------------------------------------------- 5. Angiografiya (ARCADE stenosis test — hammasida stenoz bor)
    arc = a.data / "arcade" / "x" / "arcade" / "stenosis" / "test"
    ann = json.loads((arc / "annotations" / "test.json").read_text(encoding="utf-8"))
    with_sten = sorted({x["image_id"] for x in ann["annotations"]})
    imgs = {im["id"]: im["file_name"] for im in ann["images"]}
    rows = []
    for iid in with_sten[:a.n * 2]:
        eid = episode(f"E2E-ANG-{iid}", "adult")
        resp = c.post(f"/episodes/{eid}/angio", data={"actor": "e2e"},
                      files={"file": (imgs[iid], (arc / "images" / imgs[iid]).read_bytes(), "image/png")})
        if resp.status_code != 200:
            rows.append({"truth": True, "call": None, "error": resp.text[:120]}); continue
        ev = resp.json()["evidence"]
        rows.append({"truth": True, "call": None if ev["abstained"] else bool((ev["value"] or {}).get("n_candidates"))})
    results["angio"] = {"name": "Angiografiya: stenoz nomzodi", "data": "ARCADE test (stenozli kadrlar)", **tally(rows)}

    # ---------------------------------------------------------------- 6. MNO qog'ozi OCR (sun'iy rasm: qiymat ma'lum)
    rows = []
    try:
        from PIL import Image, ImageDraw, ImageFont
        eid = episode("E2E-INR", "adult")
        for f, tt in [("screening", "workup"), ("workup", "heart_team"), ("heart_team", "procedure"), ("procedure", "icu"),
                      ("icu", "discharge"), ("discharge", "guardian_30d")]:
            c.post(f"/episodes/{eid}/transition", json={"from_stage": f, "to_stage": tt, "author": "e2e"})
        try:
            font = ImageFont.truetype("arial.ttf", 34)
        except OSError:
            font = ImageFont.load_default()
        for v in (1.6, 2.5, 3.8, 5.2):
            im = Image.new("RGB", (900, 320), "white"); d = ImageDraw.Draw(im)
            d.text((40, 40), "LABORATORIYA TAHLILI", fill="black", font=font)
            d.text((40, 120), "Protrombin vaqti: 24.1 s", fill="black", font=font)
            d.text((40, 200), f"MNO (INR): {v}", fill="black", font=font)
            b = io.BytesIO(); im.save(b, "PNG")
            resp = c.post(f"/episodes/{eid}/guardian/inr-image", data={"actor": "e2e", "indication": "mechanical_mitral"},
                          files={"file": ("inr.png", b.getvalue(), "image/png")})
            ev = resp.json().get("evidence", [{}])
            ev = ev[0] if isinstance(ev, list) else ev
            got = ev.get("value") if isinstance(ev.get("value"), (int, float)) else (ev.get("value") or {}).get("inr") if isinstance(ev.get("value"), dict) else None
            rows.append({"truth": True, "call": None if ev.get("abstained") else (got is not None and abs(float(got) - v) < 0.05), "read": got, "expected": v})
    except Exception as exc:                       # noqa: BLE001
        rows.append({"truth": True, "call": None, "error": str(exc)[:120]})
    results["inr_ocr"] = {"name": "MNO qog'ozi: raqamni o'qish", "data": "sun'iy laboratoriya rasmi (qiymat ma'lum)", **tally(rows),
                          "detail": [(r.get("expected"), r.get("read")) for r in rows]}

    # ---------------------------------------------------------------- shadow va ishlash vaqti
    rep = c.get("/shadow/report").json()
    summary = {"seconds": round(time.time() - t0, 1), "models_loaded": {k: (v or {}).get("name") for k, v in models.items() if isinstance(v, dict) and "name" in (v or {})},
               "pcg_model": (health.get("pcg_model") or {}).get("name"), "shadow_runs": rep.get("runs"), "results": results}
    lines = ["# Uchidan-uchiga tekshiruv: modellar dastur orqali (haqiqiy og'irliklar)", "",
             f"Sana: {time.strftime('%Y-%m-%d')}. Skript: `research/e2e_check.py`. Har sinfdan {a.n} ta namuna, HTTP API orqali.", "",
             "| Modul | Ma'lumot | Musbat: topildi | Manfiy: to'g'ri «yo'q» | Javob bermadi | Xato |", "|---|---|---|---|---|---|"]
    for k, r in results.items():
        pos = f"{r['tp']}/{r['tp'] + r['fn']}" if r["n_pos"] else "—"
        neg = f"{r['tn']}/{r['tn'] + r['fp']}" if r["n_neg"] else "—"
        lines.append(f"| {r['name']} | {r['data']} | {pos} | {neg} | {r['abstain']} | {r['errors']} |")
    lines += ["", f"Shadow model ishga tushgan EKG'lar: {rep.get('runs')}. Umumiy vaqt: {summary['seconds']} s.", ""]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    a.out.with_suffix(".json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
