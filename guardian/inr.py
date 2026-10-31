"""Varfarin nazorati: laboratoriya qog'ozidan MNO (INR) → maqsad oralig'i bilan solishtirish.

XAVFSIZLIK: bemorga doza aytilmaydi. Bemor faqat "me'yorda / shifokorga
murojaat qiling" xabarini oladi; doza qarori shifokor ekranida.
OCR alohida (telefon kamerasi → matn); bu modul OCR chiqargan MATNni tahlil qiladi.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

REFERENCE = "Otto CM et al. 2020 ACC/AHA Guideline for Valvular Heart Disease. Circulation 2021;143:e72-e227"

Indication = Literal["mechanical_aortic", "mechanical_aortic_risk", "mechanical_mitral", "bioprosthetic", "af"]

# maqsad (o'rta qiymat, past, yuqori)
TARGETS: dict[str, tuple[float, float, float]] = {
    "mechanical_aortic": (2.5, 2.0, 3.0),        # bikuspid/zamonaviy, tromboemboliya xavf omillarisiz
    "mechanical_aortic_risk": (3.0, 2.5, 3.5),   # AF, oldingi tromboemboliya, LV disfunksiya, giperkoagulyatsiya
    "mechanical_mitral": (3.0, 2.5, 3.5),
    "bioprosthetic": (2.5, 2.0, 3.0),            # dastlabki 3–6 oy
    "af": (2.5, 2.0, 3.0),
}

# "MHO" — OCR kirill "МНО" ni ko'pincha lotin harflari bilan o'qiydi.
# Laboratoriya qog'ozlarida ko'pincha ikki nom birga yoziladi: «MNO (INR): 3.8», «INR(МНО) = 3,1» — qavsdagi nom ham qabul qilinadi.
_KEY = r"(?:INR|MNO|MHO|МНО)"
_PATTERN = re.compile(rf"\b{_KEY}\b(?:\s*[(\[]\s*{_KEY}\s*[)\]])?\s*[:=\-]?\s*(\d{{1,2}}(?:[.,]\d{{1,2}})?)", re.IGNORECASE)


def parse_inr_text(text: str) -> Optional[float]:
    """OCR matnidan MNO qiymatini ajratadi. Bir nechta qiymat bo'lsa yoki topilmasa → None."""
    values = {float(m.group(1).replace(",", ".")) for m in _PATTERN.finditer(text or "")}
    return values.pop() if len(values) == 1 else None


def assess_inr(value: Optional[float], indication: Indication, source_text: str = "") -> Evidence:
    target, lo, hi = TARGETS[indication]
    prov = Provenance(name="inr_target", version="acc-aha-2020", reference=REFERENCE)
    if value is None:
        return Evidence.abstain("guardian.inr", Source.PATIENT, prov,
                                "MNO qiymati aniq o'qilmadi — bemor qiymatni qo'lda kiritsin yoki rasmni qayta yuborsin")
    if not 0.8 <= value <= 12:
        return Evidence.abstain("guardian.inr", Source.PATIENT, prov, f"MNO {value} — fiziologik bo'lmagan qiymat (OCR xatosi?)")

    mechanical = indication.startswith("mechanical")
    trace = [f"MNO {value:.2f}, maqsad {target} ({lo}–{hi}), ko'rsatma: {indication}"]
    if value >= 5.0:
        risk = RiskLevel.VERY_HIGH if value >= 8 else RiskLevel.HIGH
        trace.append("qon ketish xavfi yuqori")
    elif mechanical and value < lo - 0.5:
        risk = RiskLevel.HIGH
        trace.append("mexanik klapan: tromboz/emboliya xavfi")
    elif lo <= value <= hi:
        risk = RiskLevel.LOW
        trace.append("maqsad oralig'ida")
    else:
        risk = RiskLevel.MODERATE
        trace.append("maqsaddan tashqarida — shifokor dozani ko'rib chiqadi")
    if source_text:
        trace.append("manba: OCR matni")
    return Evidence(kind="guardian.inr", value=value, unit="MNO", source=Source.PATIENT,
                    provenance=prov, risk=risk, explanation=trace)
