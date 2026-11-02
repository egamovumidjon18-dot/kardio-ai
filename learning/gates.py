"""Avtomatik darvozalar: nomzod model faqat HAMMASIDAN o'tsa, tasdiqlash uchun ko'rsatiladi.

Bo'sag'alar kodda qat'iy yozilgan (natijaga qarab o'zgartirilmaydi). Ma'lumot darvozasi — o'qitishdan OLDIN
(ZCHSound'dagi kabi yashirin xato bo'lsa, o'qitish umuman boshlanmaydi); model darvozasi — o'qitishdan KEYIN.
"""
from __future__ import annotations

import random
from typing import Optional

from learning.dataset import bucket, label_of, usable
from research.export_local import _auroc, collection_confound

CFG = {
    "min_children": 60,        # kamida shuncha tasdiqlangan, yaroqli bola
    "min_per_class": 20,       # har sinfdan kamida
    "min_new": 30,             # oxirgi nomzoddan beri kamida shuncha yangi bola
    "local_gain": 0.03,        # mahalliy test AUROC kamida shuncha oshsin (juft bootstrap ishonch oralig'ining quyi chegarasi > 0)
    "circor_margin": 0.03,     # CirCor testida shundan ko'p yomonlashmasin
    "abstain_margin": 0.05,    # «javob bermadi» ulushi shundan ko'p oshmasin
    "sens_margin": 0.05,       # sezgirlik shundan ko'p pasaymasin (nuqsonli bolani o'tkazib yuborish xavfi)
    "label_gain": 0.02,        # haqiqiy belgilar bilan o'qitilgan nomzod aralashtirilgan belgilar bilan o'qitilganidan kamida shuncha yaxshi
    "min_test_per_class": 8,   # mahalliy test to'plamida har sinfdan kamida (aks holda baho ishonchsiz)
}


def _gate(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def dataset_gate(children: list[dict], cfg: dict = CFG) -> dict:
    use = usable(children)
    pos = sum(label_of(c["dx"]) == 1 for c in use)
    neg = len(use) - pos
    items = [_gate("yetarli bola", len(use) >= cfg["min_children"], f"{len(use)} ta (kerak: {cfg['min_children']})"),
             _gate("har sinfdan yetarli", min(pos, neg) >= cfg["min_per_class"],
                   f"nuqsonli {pos}, sog' {neg} (har biri kamida {cfg['min_per_class']})")]
    test = [c for c in use if bucket(c["patient_key"]) == "test"]
    items.append(_gate("bemorlar takrorlanmagan", len({c["patient_key"] for c in use}) == len(use),
                       "har bemor uchun bitta tasdiqlangan holat kerak"))
    t_pos = sum(label_of(c["dx"]) == 1 for c in test)
    items.append(_gate("mahalliy test to'plamida har sinfdan yetarli", min(t_pos, len(test) - t_pos) >= cfg["min_test_per_class"],
                       f"test: nuqsonli {t_pos}, sog' {len(test) - t_pos} (har biri kamida {cfg['min_test_per_class']})"))
    conf = collection_confound({c["eid"]: (c["created_at"], "NORMAL" if label_of(c["dx"]) == 0 else c["dx"], c["device"])
                                for c in use})
    if conf is None:
        items.append(_gate("yig'ish tartibi tekshirildi", False, "tekshirish uchun ma'lumot yetarli emas"))
    else:
        items.append(_gate("yig'ish tartibi aralash (tashxis bilan ketma-ket emas)", not conf["order_warn"],
                           f"tartib bilan tashxis AUROC {conf['order_auroc']} (≥0.85 xavfli)"))
        items.append(_gate("qurilmalar ikkala sinfni yozgan", not conf["device_warn"],
                           f"qurilma sofligi {conf['device_purity'] or '—'}"))
    return {"passed": all(g["passed"] for g in items), "items": items, "n_usable": len(use), "n_pos": pos, "n_neg": neg,
            "confound": conf}


def paired_bootstrap_delta(y: list[int], s_new: list[float], s_old: list[float], n: int = 1000, seed: int = 0):
    """Ikki modelning AUROC farqi (yangi − eski) va 95% ishonch oralig'i: bir xil bolalar qayta tanlanadi (juft)."""
    k = len(y)
    delta = _auroc(y, s_new) - _auroc(y, s_old)
    rng, ds = random.Random(seed), []
    for _ in range(n):
        idx = [rng.randrange(k) for _ in range(k)]
        yy = [y[i] for i in idx]
        if 0 < sum(yy) < k:
            ds.append(_auroc(yy, [s_new[i] for i in idx]) - _auroc(yy, [s_old[i] for i in idx]))
    ds.sort()
    if not ds:
        return delta, float("nan"), float("nan")
    return delta, ds[int(0.025 * len(ds))], ds[int(0.975 * len(ds)) - 1]


def model_gate(champion: dict, challenger: dict, delta: tuple, control_auroc: Optional[float], cfg: dict = CFG) -> dict:
    """champion/challenger: {"local": metrika, "circor": metrika}; metrika: auroc, sensitivity, abstain_rate."""
    d, lo, hi = delta
    items = [_gate("mahalliy testda sifat ishonchli oshdi", d >= cfg["local_gain"] and lo > 0,
                   f"AUROC farqi {d:+.3f} (95% CI {lo:+.3f}…{hi:+.3f}); kerak: ≥{cfg['local_gain']} va CI quyi chegarasi >0")]
    c_new, c_old = challenger["circor"]["auroc"], champion["circor"]["auroc"]
    items.append(_gate("CirCor testida yomonlashmadi", c_new >= c_old - cfg["circor_margin"],
                       f"{c_old:.3f} → {c_new:.3f} (ruxsat: −{cfg['circor_margin']})"))
    for site, label in (("local", "mahalliy"), ("circor", "CirCor")):
        a_new, a_old = challenger[site]["abstain_rate"], champion[site]["abstain_rate"]
        items.append(_gate(f"«javob bermadi» ulushi oshmadi ({label})", a_new - a_old <= cfg["abstain_margin"],
                           f"{a_old:.3f} → {a_new:.3f} (ruxsat: +{cfg['abstain_margin']})"))
        s_new, s_old = challenger[site]["sensitivity"], champion[site]["sensitivity"]
        items.append(_gate(f"sezgirlik pasaymadi ({label})", s_new >= s_old - cfg["sens_margin"],
                           f"{s_old:.3f} → {s_new:.3f} (ruxsat: −{cfg['sens_margin']})"))
    # Salbiy nazorat: mahalliy belgilari ARALASHTIRILGAN nomzod. U joriy modeldan «yaxshi» chiqmasligi kerak (aks holda
    # o'qitish jarayonida sizib chiqish yoki ma'lumot izi bor), va haqiqiy nomzod undan aniq yaxshiroq bo'lishi kerak.
    if control_auroc is None or control_auroc != control_auroc:
        items.append(_gate("salbiy nazorat o'tkazildi", False, "bajarilmadi"))
    else:
        champ_local, chall_local = champion["local"]["auroc"], challenger["local"]["auroc"]
        items.append(_gate("aralashtirilgan belgilar nomzodni «yaxshilamaydi» (sizib chiqish yo'q)",
                           control_auroc - champ_local < cfg["local_gain"],
                           f"nazorat AUROC {control_auroc:.3f}, joriy {champ_local:.3f} (farq {control_auroc - champ_local:+.3f}, "
                           f"ruxsat: <{cfg['local_gain']})"))
        items.append(_gate("haqiqiy belgilar aralashtirilganidan yaxshiroq (mahalliy belgilar foyda berdi)",
                           chall_local - control_auroc >= cfg["label_gain"],
                           f"nomzod {chall_local:.3f}, nazorat {control_auroc:.3f} (farq {chall_local - control_auroc:+.3f}, "
                           f"kerak: ≥{cfg['label_gain']})"))
    return {"passed": all(g["passed"] for g in items), "items": items}
