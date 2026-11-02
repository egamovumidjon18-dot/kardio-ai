"""Koronar tomir shoxlari va stenoz anatomiyasi tahlili (ESC/EACTS 2018/2024 Guidelines).

Chap asosiy poya (LMS), LAD, LCx, RCA tomirlaridagi torayishlarni klinik
xavf darajasiga ko'tarish va Heart Team konsiliumiga uzatish qoidalari.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source, risk_rank

ANGIO_REF = "ESC/EACTS 2018 & 2024 Myocardial Revascularization Guidelines (LMS va ko'p tomirli zararlanish mezonlari)"

VALID_VESSELS = {
    "LMS": "Chap asosiy poya (Left Main Stem)",
    "LAD_PROX": "LAD proksimal segmenti (Oldingi tushuvchi)",
    "LAD_MID_DIST": "LAD o'rta/distal segmenti",
    "LCX": "LCx (O'rab oluvchi arteriya)",
    "RCA": "RCA (O'ng toj arteriya)",
    "DIAGONAL": "Diagonal tarmoq",
    "OM": "O'tmas chekka tarmoq (OM)",
}


@dataclass
class CoronaryLesion:
    vessel: str                         # LMS, LAD_PROX, LCX, RCA...
    stenosis_percent: float             # 0 - 100%
    is_bifurcation: bool = False        # Medina tasnifidagi bifurkatsiya
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def assess_coronary_anatomy(lesions: list[CoronaryLesion], ai_candidate_count: int = 0) -> Evidence:
    """Koronar tomirlar anatomiyasiga ko'ra xavf darajasini deterministik baholaydi."""
    prov = Provenance(name="coronary_anatomy_guideline", version="1.0.0", reference=ANGIO_REF)

    if not lesions:
        return Evidence(
            kind="angio.anatomy",
            value={"lesions": [], "ai_candidate_count": ai_candidate_count},
            source=Source.CLINICIAN,
            provenance=prov,
            risk=RiskLevel.NORMAL if ai_candidate_count == 0 else RiskLevel.LOW,
            explanation=["Stenoz kiritilmagan"],
        )

    levels: list[RiskLevel] = []
    trace: list[str] = []

    has_lms_critical = False
    significant_vessels = set()

    for les in lesions:
        v_name = VALID_VESSELS.get(les.vessel, les.vessel)
        pct = les.stenosis_percent

        # LMS (Chap asosiy poya) — 50% dan yuqori bo'lsa zudlik bilan VERY_HIGH
        if les.vessel == "LMS" and pct >= 50.0:
            has_lms_critical = True
            levels.append(RiskLevel.VERY_HIGH)
            trace.append(f"🔴 LMS (Chap asosiy poya) stenozi {pct:.0f}% (≥50%) — Zudlik bilan KShSh (CABG) konsiliumi talab etiladi")
        elif les.vessel == "LAD_PROX" and pct >= 70.0:
            levels.append(RiskLevel.HIGH)
            trace.append(f"🟠 Proksimal LAD kritik stenozi {pct:.0f}% (≥70%)")
            significant_vessels.add("LAD")
        elif pct >= 70.0:
            levels.append(RiskLevel.MODERATE)
            trace.append(f"{v_name} kritik stenozi {pct:.0f}% (≥70%)")
            base_vessel = les.vessel.split("_")[0]
            significant_vessels.add(base_vessel)
        elif pct >= 50.0:
            levels.append(RiskLevel.LOW)
            trace.append(f"{v_name} o'rtacha stenozi {pct:.0f}% (50–69%)")

        if les.is_bifurcation:
            trace.append(f"{v_name} bifurkatsiya zararlanishi mavjud")

    # 3 tomirli kasallik (LAD + LCx + RCA)
    if len(significant_vessels) >= 3 and not has_lms_critical:
        levels.append(RiskLevel.VERY_HIGH)
        trace.append("Ko'p tomirli (3 tomirli) jiddiy zararlanish — Heart Team konsiliumi zarur")

    risk = max(levels, key=lambda r: risk_rank(r) or 0) if levels else RiskLevel.LOW

    val = {
        "lesions": [l.to_dict() for l in lesions],
        "significant_vessels_count": len(significant_vessels),
        "lms_involved": has_lms_critical,
        "ai_candidate_count": ai_candidate_count,
    }

    return Evidence(
        kind="angio.anatomy",
        value=val,
        source=Source.CLINICIAN,
        provenance=prov,
        risk=risk,
        explanation=trace or ["Stenoz parametrlari me'yorda"],
    )
