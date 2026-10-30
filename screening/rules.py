"""Deterministik trek: pulsoksimetriya va klinik qizil bayroqlar.

Bu qoidalar AI'dan mustaqil ishlaydi va Concordance'da "qoida" tomoni bo'ladi.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

AAP_2020 = ("Martin GR et al. Updated strategies for pulse oximetry screening for critical "
            "congenital heart disease. Pediatrics 2020;146(1):e20191650")


class CCHDResult(str, Enum):
    PASS = "pass"
    REPEAT = "repeat"
    FAIL = "fail"


def newborn_pulse_ox(right_hand: float, foot: float, attempt: int = 1,
                     age_hours: Optional[float] = None) -> Evidence:
    """AAP 2020 CCHD algoritmi (o'ng qo'l = preduktal, oyoq = postduktal).

    PASS:   o'ng qo'l YOKI oyoq ≥95% va farq ≤3%
    FAIL:   istalgan biri <90%, yoki 2-urinishda ham PASS emas
    REPEAT: qolgan holatlar (1 soatdan keyin bir marta qayta)
    """
    prov = Provenance(name="cchd_pulse_ox", version="aap-2020", reference=AAP_2020)
    for v in (right_hand, foot):
        if not 50 <= v <= 100:
            return Evidence.abstain("screening.cchd", Source.RULE, prov,
                                    f"SpO₂ qiymati ishonchsiz: {v}% (50–100 oralig'ida bo'lishi kerak)")
    diff = abs(right_hand - foot)
    trace = [f"o'ng qo'l {right_hand:.0f}%, oyoq {foot:.0f}%, farq {diff:.0f}%, urinish {attempt}"]
    if age_hours is not None and age_hours < 24:
        trace.append("ogohlantirish: skrining ≥24 soatda tavsiya etiladi, ertaroq soxta-musbat ko'p")

    if min(right_hand, foot) < 90:
        result = CCHDResult.FAIL
        trace.append("istalgan nuqtada <90% → FAIL")
    elif max(right_hand, foot) >= 95 and diff <= 3:
        result = CCHDResult.PASS
        trace.append("≥95% va farq ≤3% → PASS")
    elif attempt >= 2:
        result = CCHDResult.FAIL
        trace.append("2-urinishda ham PASS emas → FAIL")
    else:
        result = CCHDResult.REPEAT
        trace.append("90–94% yoki farq >3% → 1 soatdan keyin qayta o'lchash")

    risk = {CCHDResult.PASS: RiskLevel.LOW, CCHDResult.REPEAT: RiskLevel.MODERATE,
            CCHDResult.FAIL: RiskLevel.HIGH}[result]
    return Evidence(kind="screening.cchd", value=result.value, source=Source.RULE,
                    provenance=prov, unit="%", risk=risk, explanation=trace)


def resting_spo2(spo2: float) -> Evidence:
    """Yangi tug'ilgandan katta bolalar uchun. Guideline emas — konservativ evristika."""
    prov = Provenance(name="resting_spo2", reference="konservativ evristika (mahalliy protokol bilan tasdiqlang)")
    if not 50 <= spo2 <= 100:
        return Evidence.abstain("screening.spo2", Source.RULE, prov, f"SpO₂ qiymati ishonchsiz: {spo2}%")
    if spo2 < 90:
        risk, note = RiskLevel.HIGH, "<90% — gipoksemiya"
    elif spo2 < 95:
        risk, note = RiskLevel.MODERATE, "90–94% — chegaraviy"
    else:
        risk, note = RiskLevel.LOW, "≥95% — me'yorda"
    return Evidence(kind="screening.spo2", value=spo2, unit="%", source=Source.RULE,
                    provenance=prov, risk=risk, explanation=[f"tinch holatda SpO₂ {spo2:.0f}%: {note}"])


# Qizil bayroqlar: kod → (o'zbekcha nomi, katta/kichik)
RED_FLAGS: dict[str, tuple[str, bool]] = {
    "cyanosis": ("markaziy sianoz", True),
    "feeding_diaphoresis": ("emizish/ovqatlanishda terlash, tez charchash", True),
    "failure_to_thrive": ("vazn olmaslik", True),
    "tachypnea_rest": ("tinch holatda taxipnoe", True),
    "hepatomegaly": ("gepatomegaliya", True),
    "weak_femoral_pulse": ("son arteriyasida puls sust/yo'q", True),
    "exertional_syncope": ("jismoniy zo'riqishda hushdan ketish", True),
    "exertional_chest_pain": ("jismoniy zo'riqishda ko'krak og'rig'i", True),
    "family_sudden_death": ("oilada <50 yoshda to'satdan o'lim", True),
    "recurrent_pneumonia": ("qaytalanuvchi pnevmoniya", False),
    "exercise_intolerance": ("jismoniy yuklamaga chidamsizlik", False),
    "syndromic_features": ("sindromal belgilar (masalan, Daun)", False),
}


def red_flags(codes: list[str]) -> Evidence:
    prov = Provenance(name="red_flags", reference="pediatrik kardiologiya klinik belgilari")
    unknown = [c for c in codes if c not in RED_FLAGS]
    if unknown:
        return Evidence.abstain("screening.red_flags", Source.RULE, prov, f"noma'lum belgi kodlari: {unknown}")
    major = [RED_FLAGS[c][0] for c in codes if RED_FLAGS[c][1]]
    minor = [RED_FLAGS[c][0] for c in codes if not RED_FLAGS[c][1]]
    if major:
        risk = RiskLevel.HIGH
    elif len(minor) >= 2:
        risk = RiskLevel.MODERATE
    elif minor:
        risk = RiskLevel.LOW
    else:
        risk = RiskLevel.NORMAL
    trace = [f"katta: {', '.join(major) or '—'}", f"kichik: {', '.join(minor) or '—'}"]
    return Evidence(kind="screening.red_flags", value=sorted(codes), source=Source.CLINICIAN,
                    provenance=prov, risk=risk, explanation=trace)
