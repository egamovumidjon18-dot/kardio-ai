"""Kundalik check-in: yurak yetishmovchiligi belgilari va sternotomiya yarasi.

Hamma qoidalar deterministik. Yara rasmi saqlanadi va jarrohga yuboriladi;
CV modeli mahalliy ma'lumot yig'ilgandan keyin AI treki sifatida qo'shiladi.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source, risk_rank

HF_REF = "ESC 2021 HF guideline bemor tavsiyalari (3 kunda >2 kg vazn ortishi) + operatsiyadan keyingi konservativ chegaralar"
WOUND_REF = "Sternal SSI belgilari (CDC/NHSN chuqur SSI mezonlari asosida so'rovnoma)"
WOUND_PROTOCOL_REF = "CDC NHSN Jarrohlik yarasi infeksiyalari (SSI) mezonlari va ASEPSIS yara baholash shkalasi"

HF_SYMPTOMS = {
    "dyspnea_rest": ("tinch holatda hansirash", RiskLevel.HIGH),
    "orthopnea": ("yotganda hansirash (ortopnoe)", RiskLevel.HIGH),
    "syncope": ("hushdan ketish", RiskLevel.HIGH),
    "chest_pain_non_incisional": ("chokdan tashqari ko'krak og'rig'i", RiskLevel.HIGH),
    "palpitations": ("yurak urishi tartibsiz/tez", RiskLevel.MODERATE),
    "new_edema": ("oyoqlarda yangi shish", RiskLevel.MODERATE),
    "reduced_urine": ("siydik kamaygan", RiskLevel.MODERATE),
}

WOUND_SIGNS = {
    "purulent_discharge": ("yiringli ajralma", RiskLevel.HIGH),
    "sternal_instability": ("to'sh suyagida qimirlash/chiqillash", RiskLevel.HIGH),
    "dehiscence": ("chok ochilgan", RiskLevel.HIGH),
    "spreading_redness": ("qizarish kengaymoqda", RiskLevel.MODERATE),
    "serous_discharge": ("tiniq/qonli ajralma", RiskLevel.MODERATE),
    "increasing_pain": ("chok og'rig'i kuchaymoqda", RiskLevel.MODERATE),
}


def _worst(levels: list[RiskLevel]) -> RiskLevel:
    return max(levels, key=lambda r: risk_rank(r) or 0) if levels else RiskLevel.LOW


def weight_trend(history: list[tuple[str, float]]) -> Evidence:
    """history: [(ISO sana, kg)]. 3 kun ichida ≥2 kg → HIGH; 1 kunda ≥1 kg → MODERATE."""
    prov = Provenance(name="hf_weight_trend", reference=HF_REF)
    pts = sorted((datetime.fromisoformat(d), w) for d, w in history)
    if len(pts) < 2:
        return Evidence(kind="guardian.weight", value=pts[-1][1] if pts else None, unit="kg",
                        source=Source.PATIENT, provenance=prov, risk=RiskLevel.LOW,
                        explanation=["trend uchun kamida 2 o'lchov kerak"])
    last_t, last_w = pts[-1]
    risk, trace = RiskLevel.LOW, []
    for t, w in pts[:-1]:
        days = (last_t - t).total_seconds() / 86400
        gain = last_w - w
        if days <= 3.01 and gain >= 2.0:
            risk = RiskLevel.HIGH
            trace.append(f"{days:.0f} kunda +{gain:.1f} kg (≥2 kg / 3 kun)")
        elif days <= 1.01 and gain >= 1.0 and risk != RiskLevel.HIGH:
            risk = RiskLevel.MODERATE
            trace.append(f"{days:.0f} kunda +{gain:.1f} kg (≥1 kg / 1 kun)")
    return Evidence(kind="guardian.weight", value=last_w, unit="kg", source=Source.PATIENT, provenance=prov,
                    risk=risk, explanation=trace or ["vazn barqaror"])


def _unsure(codes: list[str], table: dict, levels: list, trace: list) -> None:
    """«Bilmayman» javobi «yo'q» degani EMAS: jiddiy (HIGH) belgi bo'yicha noaniqlik shifokor tekshiruvini talab qiladi (MODERATE)."""
    for c in codes:
        name, lvl = table[c]
        if lvl == RiskLevel.HIGH:
            levels.append(RiskLevel.MODERATE)
        trace.append(f"aniq emas (bemor bilmaydi): {name}")


def vitals_and_symptoms(heart_rate: Optional[float], spo2: Optional[float], temperature_c: Optional[float],
                        symptoms: list[str], unsure: Optional[list[str]] = None) -> Evidence:
    prov = Provenance(name="hf_symptoms", reference=HF_REF)
    unsure = [u for u in (unsure or []) if u not in symptoms]
    unknown = [s for s in [*symptoms, *unsure] if s not in HF_SYMPTOMS]
    if unknown:
        return Evidence.abstain("guardian.hf", Source.PATIENT, prov, f"noma'lum belgi kodlari: {unknown}")
    levels, trace = [], []
    if heart_rate is not None:
        if heart_rate > 120 or heart_rate < 45:
            levels.append(RiskLevel.HIGH); trace.append(f"puls {heart_rate:.0f} (>120 yoki <45)")
        elif heart_rate > 100:
            levels.append(RiskLevel.MODERATE); trace.append(f"puls {heart_rate:.0f} (>100)")
    if spo2 is not None:
        if spo2 < 90:
            levels.append(RiskLevel.HIGH); trace.append(f"SpO₂ {spo2:.0f}% (<90)")
        elif spo2 < 94:
            levels.append(RiskLevel.MODERATE); trace.append(f"SpO₂ {spo2:.0f}% (90–93)")
    if temperature_c is not None and temperature_c >= 38.0:
        levels.append(RiskLevel.MODERATE); trace.append(f"harorat {temperature_c:.1f}°C")
    for s in symptoms:
        name, lvl = HF_SYMPTOMS[s]
        levels.append(lvl); trace.append(name)
    _unsure(unsure, HF_SYMPTOMS, levels, trace)
    return Evidence(kind="guardian.hf", value={"hr": heart_rate, "spo2": spo2, "t": temperature_c, "symptoms": symptoms, "unsure": unsure},
                    source=Source.PATIENT, provenance=prov, risk=_worst(levels),
                    explanation=trace or ["belgilar yo'q"])


def wound(signs: list[str], fever: bool = False, photo_ref: Optional[str] = None, unsure: Optional[list[str]] = None) -> Evidence:
    prov = Provenance(name="sternal_wound_questionnaire", reference=WOUND_REF)
    unsure = [u for u in (unsure or []) if u not in signs]
    unknown = [s for s in [*signs, *unsure] if s not in WOUND_SIGNS]
    if unknown:
        return Evidence.abstain("guardian.wound", Source.PATIENT, prov, f"noma'lum belgi kodlari: {unknown}")
    levels = [WOUND_SIGNS[s][1] for s in signs]
    trace = [WOUND_SIGNS[s][0] for s in signs]
    _unsure(unsure, WOUND_SIGNS, levels, trace)
    risk = _worst(levels)
    if fever and signs and risk == RiskLevel.MODERATE:
        risk = RiskLevel.HIGH
        trace.append("isitma + yara belgisi → chuqur SSI gumoni")
    if photo_ref:
        trace.append("rasm jarrohga ko'rib chiqish uchun yuborildi (AI tahlili hali yo'q)")
    return Evidence(kind="guardian.wound", value={"signs": signs, "fever": fever, "photo_ref": photo_ref, "unsure": unsure},
                    source=Source.PATIENT, provenance=prov, risk=risk if (signs or unsure) else RiskLevel.LOW,
                    explanation=trace or ["yara belgilari yo'q"])


def assess_wound_protocol(
    erythema: str = "none",
    edema: str = "none",
    discharge: str = "none",
    pain: str = "mild_expected",
    warmth: str = "normal",
    dehiscence: str = "none",
    sternal_instability: bool = False,
    fever: bool = False,
    photo_ref: Optional[str] = None,
    notes: Optional[str] = None,
) -> Evidence:
    """Sternotomiya yarasi standart 5 o'qli protokoli (CDC NHSN / ASEPSIS)."""
    prov = Provenance(name="sternotomy_wound_protocol", version="1.0.0", reference=WOUND_PROTOCOL_REF)
    levels: list[RiskLevel] = []
    trace: list[str] = []

    # 1. Qizarish (Erythema)
    if erythema == "spreading_over_2cm":
        levels.append(RiskLevel.MODERATE)
        trace.append("qizarish chok atrofida >2 sm kengaygan")
    elif erythema == "mild_under_2cm":
        trace.append("yengil chegaralangan qizarish (≤2 sm)")

    # 2. Shish (Edema)
    if edema == "severe":
        levels.append(RiskLevel.MODERATE)
        trace.append("to'sh ustida yaqqol shish")
    elif edema == "mild":
        trace.append("biroz shish")

    # 3. Ajralma (Discharge)
    if discharge == "purulent":
        levels.append(RiskLevel.HIGH)
        trace.append("yiringli ajralma (kritik SSI belgisi)")
    elif discharge == "serous":
        levels.append(RiskLevel.MODERATE)
        trace.append("seroz yoki qonli ajralma")

    # 4. Og'riq (Pain)
    if pain == "severe":
        levels.append(RiskLevel.MODERATE)
        trace.append("kuchli va kuchayuvchi ko'krak og'rig'i")
    elif pain == "increasing":
        levels.append(RiskLevel.MODERATE)
        trace.append("chok sohasida kuchayuvchi og'riq")

    # 5. Mahalliy harorat (Warmth)
    if warmth == "elevated":
        levels.append(RiskLevel.MODERATE)
        trace.append("mahalliy harorat ko'tarilgan (giperemiya)")

    # 6. Chok ochilishi (Dehiscence)
    if dehiscence == "deep_separation":
        levels.append(RiskLevel.HIGH)
        trace.append("chuqur to'qimalar/fassiya ajralishi")
    elif dehiscence == "superficial":
        levels.append(RiskLevel.MODERATE)
        trace.append("yuzaki teri choki ochilishi")

    # 7. To'sh suyagi instabilligi (Sternal Instability)
    if sternal_instability:
        levels.append(RiskLevel.HIGH)
        trace.append("to'sh suyagi qimirlashi/chiqillashi (mediastinit xavfi)")

    # Isitma (Fever)
    if fever:
        if any(lvl in (RiskLevel.MODERATE, RiskLevel.HIGH) for lvl in levels):
            levels.append(RiskLevel.HIGH)
            trace.append("isitma (≥38°C) + yara belgisi → chuqur SSI gumoni")
        else:
            levels.append(RiskLevel.MODERATE)
            trace.append("isitma (≥38°C)")

    risk = _worst(levels)
    if photo_ref:
        trace.append("rasm jarroh monitorida ko'rib chiqish uchun biriktirildi")

    val = {
        "erythema": erythema,
        "edema": edema,
        "discharge": discharge,
        "pain": pain,
        "warmth": warmth,
        "dehiscence": dehiscence,
        "sternal_instability": sternal_instability,
        "fever": fever,
        "photo_ref": photo_ref,
        "notes": notes,
    }
    return Evidence(
        kind="guardian.wound_protocol",
        value=val,
        source=Source.PATIENT,
        provenance=prov,
        risk=risk if (levels or fever or sternal_instability) else RiskLevel.LOW,
        explanation=trace or ["yara holati qoniqarli, infeksiya belgilari yo'q"],
    )
