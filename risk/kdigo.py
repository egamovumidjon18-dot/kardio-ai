"""KDIGO (Kidney Disease: Improving Global Outcomes) 2012 — O'tkir buyrak zararlanishi (AKI) deterministik qoidasi.

Kardioxirurgiya va reanimatsiya (ICU) bosqichida bemorning kreatinin dinamikasi
va soatlik siydik miqdori bo'yicha O'BYe (AKI) bosqichini baholash.

Manba:
  KDIGO Clinical Practice Guideline for Acute Kidney Injury. Kidney Int Suppl 2012;2(1):1–138.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

REFERENCE = "KDIGO AKI Work Group. Kidney Int Suppl 2012;2(1):1-138"


@dataclass
class KDIGOInput:
    baseline_creatinine: float               # µmol/L (operatsiyadan oldingi bazaviy daraja)
    current_creatinine: float                # µmol/L (amaldagi zardob kreatinini)
    creatinine_48h_rise: Optional[float] = None  # µmol/L (oxirgi 48 soat ichidagi mutlaq o'sish)
    urine_output_ml_kg_h: Optional[float] = None # ml/kg/soat (soatlik diurez)
    urine_hours: Optional[float] = None      # ushbu diurez davom etgan soatlar soni
    rrt: bool = False                        # buyrak o'rnini bosuvchi terapiya (dializ/CRRT)


def assess_kdigo(inp: KDIGOInput) -> Evidence:
    """KDIGO mezonlari bo'yicha O'BYe (AKI) bosqichi va klinik xavfini baholaydi."""
    prov = Provenance(name="kdigo_aki", version="2012", reference=REFERENCE)
    kind = "risk.kdigo"

    if (not math.isfinite(inp.baseline_creatinine) or not math.isfinite(inp.current_creatinine)
            or inp.baseline_creatinine <= 0 or inp.current_creatinine <= 0):
        return Evidence.abstain(kind, Source.RULE, prov, "kreatinin qiymatlari noto'g'ri (musbat son bo'lishi kerak)")

    ratio = inp.current_creatinine / inp.baseline_creatinine
    reasons: list[str] = []
    stage = 0

    # 1. Dializ / RRT
    if inp.rrt:
        stage = 3
        reasons.append("Buyrak o'rnini bosuvchi terapiya (gemodializ/CRRT) o'tkazilmoqda")

    # 2. Kreatinin mezonlari
    if not inp.rrt:
        if ratio >= 3.0:
            stage = max(stage, 3)
            reasons.append(f"Kreatinin bazaviy darajadan {ratio:.1f} baravar oshgan (≥3.0×)")
        elif inp.current_creatinine >= 353.6 and (inp.current_creatinine - inp.baseline_creatinine >= 26.5):
            stage = max(stage, 3)
            reasons.append(f"Kreatinin {inp.current_creatinine:.1f} µmol/L (≥353.6 µmol/L va o'tkir ko'tarilish)")
        elif ratio >= 2.0:
            stage = max(stage, 2)
            reasons.append(f"Kreatinin bazaviy darajadan {ratio:.1f} baravar oshgan (2.0–2.9×)")
        elif ratio >= 1.5:
            stage = max(stage, 1)
            reasons.append(f"Kreatinin bazaviy darajadan {ratio:.1f} baravar oshgan (1.5–1.9×)")
        elif inp.creatinine_48h_rise is not None and inp.creatinine_48h_rise >= 26.5:
            stage = max(stage, 1)
            reasons.append(f"Oxirgi 48 soatda kreatinin {inp.creatinine_48h_rise:.1f} µmol/L ga oshgan (≥26.5 µmol/L)")

    # 3. Siydik miqdori (Diurez) mezonlari
    u_rate = inp.urine_output_ml_kg_h
    u_hrs = inp.urine_hours or 0.0
    if u_rate is not None and u_hrs > 0:
        if u_rate == 0.0 and u_hrs >= 12.0:
            stage = max(stage, 3)
            reasons.append(f"Anuriya (0 ml/kg/s) {u_hrs:.0f} soat davom etgan (≥12 soat)")
        elif u_rate < 0.3 and u_hrs >= 24.0:
            stage = max(stage, 3)
            reasons.append(f"Oliguriya ({u_rate:.2f} ml/kg/s < 0.3) 24 soat davom etgan")
        elif u_rate < 0.5 and u_hrs >= 12.0:
            stage = max(stage, 2)
            reasons.append(f"Diurez kamayishi ({u_rate:.2f} ml/kg/s < 0.5) {u_hrs:.0f} soat davom etgan (≥12 soat)")
        elif u_rate < 0.5 and u_hrs >= 6.0:
            stage = max(stage, 1)
            reasons.append(f"Diurez kamayishi ({u_rate:.2f} ml/kg/s < 0.5) {u_hrs:.0f} soat davom etgan (≥6 soat)")

    if stage == 0:
        risk = RiskLevel.LOW
        reasons.append(f"KDIGO bo'yicha O'BYe belgilari yo'q (kreatinin nisbati: {ratio:.2f})")
    elif stage == 1:
        risk = RiskLevel.MODERATE
    elif stage == 2:
        risk = RiskLevel.HIGH
    else:
        risk = RiskLevel.VERY_HIGH

    stage_names = {
        0: "O'BYe yo'q (KDIGO 0)",
        1: "O'tkir buyrak zararlanishi 1-bosqich (KDIGO 1)",
        2: "O'tkir buyrak zararlanishi 2-bosqich (KDIGO 2)",
        3: "O'tkir buyrak zararlanishi 3-bosqich (KDIGO 3 — kritik)",
    }

    action_plans = {
        0: "Buyrak faoliyati barqaror; standart monitoring davom ettirilsin.",
        1: "Nefrotoksik dorilar (NSAID, aminoglikozidlar) to'xtatilsin, suyuqlik balansi nazoratga olinsin.",
        2: "Zudlik bilan nefrolog maslahati, dori dozalarini kreatinin klirensiga moslashtirish, intensiv monitoring.",
        3: "Reanimatsiya (ICU) sharoitida shoshilinch chora, buyrak o'rnini bosuvchi terapiya (CRRT/gemodializ)ga tayyorgarlik.",
    }

    value = {
        "stage": stage,
        "stage_name": stage_names[stage],
        "creatinine_ratio": round(ratio, 2),
        "baseline_creatinine_umol_l": inp.baseline_creatinine,
        "current_creatinine_umol_l": inp.current_creatinine,
        "creatinine_48h_rise_umol_l": inp.creatinine_48h_rise,
        "urine_output_ml_kg_h": inp.urine_output_ml_kg_h,
        "urine_hours": inp.urine_hours,
        "rrt": inp.rrt,
        "action_plan": action_plans[stage],
    }

    explanation = [stage_names[stage]] + reasons + [f"Tavsiya: {action_plans[stage]}"]

    return Evidence(
        kind=kind,
        value=value,
        source=Source.RULE,
        provenance=prov,
        risk=risk,
        explanation=explanation,
    )
