"""CirCor'da yozuv-sharoit (kampaniya/vaqt) izini tekshirish — ZCHSound'da topilgan xato bu yerda bormi?

    python -m research.control_circor_batch --circor-dir <...>/circor-heart-sound/1.0.3

1) Metama'lumot: kampaniya, bemor raqami, yosh/bo'y/vazn murmur bilan qanchalik bog'liq; takror audio; ikki ID li bolalar.
2) Salbiy nazorat (E1): faqat murmur YO'Q bolalar ichida audiodan kampaniyani (CC2014/CC2015) ajratish mumkinmi?
3) Kampaniyalararo tekshiruv (E2): bitta kampaniyada o'qitib, IKKINCHISIDA sinash (bir bolaning ikki ID'si ikkala
   kampaniyada bo'lgani uchun, ikkala tomonda uchragan bolalar chiqarib tashlanadi — aks holda sizib chiqadi).
   Natija bir kampaniya ichidagi natija bilan solishtiriladi: saqlansa — model kampaniya izini emas, tovushni o'rgangan.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import torch

from research.train_multisite import ci, f3, fit, site_report
from research.train_pcg import IGNORE, auroc, choose_thresholds, featurize, patient_scores, read_patients, subject_groups

CAMPAIGNS = ("CC2014", "CC2015")
AGE_ORDER = {"Neonate": 0, "Infant": 1, "Child": 2, "Adolescent": 3, "Young Adult": 4}


def _auc(y, s) -> float:
    a = auroc(np.asarray(y), np.asarray(s, dtype=float))
    return max(a, 1 - a)


def meta_report(data_dir: Path, rows: list[dict], patients: list[dict], groups: list[list[dict]]) -> dict:
    camp = {r["Patient ID"]: r["Campaign"] for r in rows}
    out: dict = {"n_patients": len(rows), "campaigns": dict(Counter(camp.values())), "by_campaign": {}}
    for c in CAMPAIGNS:
        sub = [r for r in rows if r["Campaign"] == c]
        m = Counter(r["Murmur"] for r in sub)
        ids = np.array([int(r["Patient ID"]) for r in sub])
        lab = [(int(r["Patient ID"]), int(r["Murmur"] == "Present")) for r in sub if r["Murmur"] in ("Present", "Absent")]
        i_arr, y_arr = np.array([i for i, _ in lab]), np.array([v for _, v in lab])
        qs = np.quantile(i_arr, [0, .25, .5, .75, 1.0])
        out["by_campaign"][c] = {
            "n": len(sub), "murmur": dict(m), "present_rate": m["Present"] / max(1, m["Present"] + m["Absent"]),
            "id_range": [int(ids.min()), int(ids.max())], "id_vs_murmur_auroc": _auc(y_arr, i_arr),
            "present_rate_by_id_quartile": [round(float(y_arr[(i_arr >= lo) & (i_arr <= hi)].mean()), 2)
                                            for lo, hi in zip(qs[:-1], qs[1:])]}
    lab = [(r["Campaign"] == CAMPAIGNS[1], r["Murmur"] == "Present") for r in rows if r["Murmur"] in ("Present", "Absent")]
    out["campaign_only_auroc"] = _auc([int(b) for _, b in lab], [int(a) for a, _ in lab])
    ages = [(AGE_ORDER[r["Age"]], int(r["Murmur"] == "Present")) for r in rows if r["Age"] in AGE_ORDER and r["Murmur"] in ("Present", "Absent")]
    out["age_auroc"] = _auc([v for _, v in ages], [o for o, _ in ages])
    for key in ("Height", "Weight"):
        pr = [(float(r[key]), int(r["Murmur"] == "Present")) for r in rows if r[key] not in ("nan", "") and r["Murmur"] in ("Present", "Absent")]
        out[f"{key.lower()}_auroc"] = _auc([v for _, v in pr], [x for x, _ in pr])
    seen, dup = {}, 0
    for p in sorted((data_dir / "training_data").glob("*.wav")):
        h = hashlib.md5(p.read_bytes()).hexdigest()
        dup += h in seen
        seen.setdefault(h, p.name)
    multi = [g for g in groups if len(g) > 1]
    pairs = [(g[0]["murmur"], g[1]["murmur"]) for g in multi if len(g) == 2]
    out.update(duplicate_audio=dup, multi_id_groups=len(multi),
               multi_id_cross_campaign=sum(len({camp[p["id"]] for p in g}) > 1 for g in multi),
               multi_id_label_disagree=sum(a != b for a, b in pairs), multi_id_pairs=len(pairs))
    return out


def _split_groups(group_list, seed, frac=(0.6, 0.15)):
    rng = random.Random(seed)
    g = group_list[:]
    rng.shuffle(g)
    n_tr, n_va = int(len(g) * frac[0]), int(len(g) * frac[1])
    return g[:n_tr], g[n_tr:n_tr + n_va], g[n_tr + n_va:]


def _items(groups_list, camp, relabel=None):
    pts = [p for g in groups_list for p in g]
    its = featurize(pts)
    for it in its:
        it["site"] = 0
        if relabel is not None:
            it["murmur"], it["outcome"] = relabel[it["pid"]], IGNORE
    return its


def main() -> None:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--circor-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seeds", default="7,8,9")
    ap.add_argument("--out", type=Path, default=Path("docs/experiments"))
    ap.add_argument("--skip-train", action="store_true")
    args = ap.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    rows = list(csv.DictReader(open(args.circor_dir / "training_data.csv", encoding="utf-8")))
    camp = {r["Patient ID"]: r["Campaign"] for r in rows}
    patients = read_patients(args.circor_dir)
    groups = subject_groups(patients)
    report = {"meta": meta_report(args.circor_dir, rows, patients, groups)}
    m = report["meta"]
    print(f"[meta] kampaniya bilan murmur AUROC {m['campaign_only_auroc']:.3f}; yosh {m['age_auroc']:.3f}; bo'y {m['height_auroc']:.3f}; "
          f"vazn {m['weight_auroc']:.3f}; bemor raqami: CC2014 {m['by_campaign']['CC2014']['id_vs_murmur_auroc']:.3f}, "
          f"CC2015 {m['by_campaign']['CC2015']['id_vs_murmur_auroc']:.3f}", flush=True)

    if not args.skip_train:
        # kampaniyalar aralash bola guruhlari (ikki ID: bittasi 2014, bittasi 2015) — ikkala tajribada chiqarib tashlanadi
        def camps_of(g):
            return {camp[p["id"]] for p in g}
        clean = [g for g in groups if len(camps_of(g)) == 1]
        # ---- E1: murmur YO'Q bolalar ichida audiodan kampaniyani ajratish
        absent = [g for g in clean if all(p["murmur"] == "Absent" for p in g)]
        cl = {p["id"]: int(camp[p["id"]] == CAMPAIGNS[1]) for g in absent for p in g}
        e1 = []
        for seed in (int(s) for s in args.seeds.split(",")):
            by_c = [[g for g in absent if camps_of(g) == {c}] for c in CAMPAIGNS]
            parts = [[], [], []]
            for gl in by_c:
                for i, part in enumerate(_split_groups(gl, seed)):
                    parts[i] += part
            tr, va, te = (_items(parts[i], camp, relabel=cl) for i in range(3))
            labels = {it["pid"]: cl[it["pid"]] for it in tr + va + te}
            model, _ = fit(tr, va, labels, device, args.epochs, seed, log=lambda msg: None)
            sc = patient_scores(model, te, device)
            ids = list(sc)
            e1.append(auroc(np.array([labels[i] for i in ids]), np.array([sc[i]["p_murmur"] for i in ids])))
            print(f"[E1] urug' {seed}: murmur YO'Q bolalar ichida audio → kampaniya TEST AUROC {e1[-1]:.3f} (n={len(ids)})", flush=True)
        report["E1_campaign_from_audio"] = {"auroc": e1, "mean": float(np.mean(e1)), "n_groups": len(absent)}

        # ---- E2: kampaniyalararo
        labels_all = {p["id"]: {"Present": 1, "Absent": 0}.get(p["murmur"]) for p in patients}
        group_of = {p["id"]: g[0]["id"] for g in groups for p in g}
        e2 = {}
        for a_c, b_c in (CAMPAIGNS, CAMPAIGNS[::-1]):
            a_groups = [g for g in clean if camps_of(g) == {a_c}]
            b_groups = [g for g in clean if camps_of(g) == {b_c}]
            tr_g, va_g, te_g = _split_groups(a_groups, 42, frac=(0.70, 0.15))
            tr, va = _items(tr_g, camp), _items(va_g, camp)
            test_in, test_out = _items(te_g, camp), _items(b_groups, camp)
            model, _ = fit(tr, va, labels_all, device, args.epochs, 42, log=lambda msg: None)
            vs = patient_scores(model, va, device)
            vids = [p for p in vs if labels_all.get(p) is not None]
            low, high = choose_thresholds(np.array([labels_all[p] for p in vids]), np.array([vs[p]["p_murmur"] for p in vids]), 0.95, 0.90)
            res = {}
            for name, its in (("ichki (xuddi shu kampaniya, ko'rilmagan bolalar)", test_in), (f"TASHQI ({b_c})", test_out)):
                res[name] = site_report(patient_scores(model, its, device), labels_all, group_of, low, high)
                print(f"[E2] {a_c} → {name}: AUROC {ci(res[name], 'auroc')} (n={res[name]['n']}, murmur {res[name]['n_pos']})", flush=True)
            e2[f"{a_c}->{b_c}"] = res
        report["E2_leave_campaign_out"] = e2

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "circor_batch_check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    L = ["# CirCor: yozuv-sharoit (kampaniya/vaqt) izi tekshiruvi", "",
         "ZCHSound'da topilgan xato (tashxis bo'yicha ketma-ket yozuv) CirCor'da bormi? `research/control_circor_batch.py`.", "",
         "## 1. Metama'lumot", "", "| Belgi | Murmur bilan AUROC (0.5 = bog'lanish yo'q) |", "|---|---|",
         f"| Faqat kampaniya (CC2014/CC2015) | {f3(m['campaign_only_auroc'])} |", f"| Yosh toifasi | {f3(m['age_auroc'])} |",
         f"| Bo'y | {f3(m['height_auroc'])} |", f"| Vazn | {f3(m['weight_auroc'])} |"]
    for c in CAMPAIGNS:
        b = m["by_campaign"][c]
        L.append(f"| Bemor raqami, {c} (n={b['n']}, murmur ulushi {b['present_rate']:.2f}) | {f3(b['id_vs_murmur_auroc'])}; raqam kvartillari bo'yicha murmur ulushi {b['present_rate_by_id_quartile']} |")
    L += ["", f"Bayt-ma-bayt takror yozuv: {m['duplicate_audio']}. Ikki ID li bolalar: {m['multi_id_groups']} (hammasi ikkala kampaniyada); "
          f"ularda murmur belgisi mos kelmagan: {m['multi_id_label_disagree']} / {m['multi_id_pairs']} (belgi shovqini)."]
    if "E1_campaign_from_audio" in report:
        e1 = report["E1_campaign_from_audio"]
        L += ["", "## 2. Salbiy nazorat: murmur YO'Q bolalar ichida audiodan kampaniyani ajratish", "",
              f"AUROC (urug'lar bo'yicha): {', '.join(f'{v:.3f}' for v in e1['auroc'])}; o'rtacha **{e1['mean']:.3f}** (0.5 = iz yo'q). "
              f"Solishtirish uchun ZCHSound'da erta-vs-kech: 0.669."]
        L += ["", "## 3. Kampaniyalararo tekshiruv", "", "| O'qitilgan → sinalgan | AUROC (95% CI) | Sezgirlik | Spetsifiklik |", "|---|---|---|---|"]
        for direction, res in report["E2_leave_campaign_out"].items():
            for name, r in res.items():
                L.append(f"| {direction}: {name} (n={r['n']}, murmur {r['n_pos']}) | {ci(r, 'auroc')} | {ci(r, 'sensitivity')} | {ci(r, 'specificity')} |")
    (args.out / "circor_batch_check.md").write_text("\n".join(L), encoding="utf-8")
    print("\nsaqlandi:", args.out / "circor_batch_check.md")


if __name__ == "__main__":
    main()
