"""Troponin va NT-proBNP biokimyoviy dinamikasi tahlili moduli.

Standartlar:
  * ESC 2023: O'tkir koronar sindrom (ACS) 0h/1h va 0h/3h hs-cTn (High-Sensitivity Troponin) algoritmi;
  * ESC 2021/2023: Yurak yetishmovchiligi (Heart Failure) NT-proBNP / BNP ICON yoshga moslashtirilgan chegaralari;
  * LOINC kodlari: hs-cTnI (49563-0), NT-proBNP (33762-6).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

BIOMARKER_PROV = Provenance(
    name="esc_biomarker_dynamics",
    version="2026.11.03",
    reference="ESC 2023 ACS Guidelines (0h/1h hs-cTn algorithm) + ESC 2021 Heart Failure ICON NT-proBNP cutoffs",
    dataset_license="ESC / AHA Clinical Guidelines",
)


@dataclass
class BiomarkersInput:
    troponin_0h_ng_l: Optional[float] = None       # 0-soatdagi bazaviy hs-cTn (ng/L)
    troponin_1h_ng_l: Optional[float] = None       # 1-soatdagi dinamik hs-cTn (ng/L)
    troponin_3h_ng_l: Optional[float] = None       # 3-soatdagi dinamik hs-cTn (ng/L)
    nt_probnp_pg_ml: Optional[float] = None        # NT-proBNP (pg/mL)
    bnp_pg_ml: Optional[float] = None              # Muqobil BNP (pg/mL)
    age_years: float = 60.0                        # Bemor yoshi (yillarda)
    symptoms_onset_hours: float = 3.0              # Ko'krak qafasidagi og'riq boshlanganidan buyon vaqt
    creatinine_umol_l: Optional[float] = None      # Zardob kreatinini (klirens ta'sirini baholash uchun)


def assess_biomarkers(inp: BiomarkersInput) -> Evidence:
    """Troponin va NT-proBNP dinamikasini baholab Evidence qaytaradi."""
    if inp.troponin_0h_ng_l is None and inp.nt_probnp_pg_ml is None and inp.bnp_pg_ml is None:
        return Evidence.abstain(
            kind="lab.biomarkers",
            source=Source.RULE,
            provenance=BIOMARKER_PROV,
            reason="Biokimyoviy tahlillar kiritilmadi: kamida troponin yoki NT-proBNP talab etiladi",
        )

    expl = []
    risks = []
    val = {}

    # 1. Troponin dinamikasi (ESC 2023 0h/1h hs-cTnI protokoli)
    t0 = inp.troponin_0h_ng_l
    t1 = inp.troponin_1h_ng_l
    t3 = inp.troponin_3h_ng_l

    if t0 is not None:
        val["troponin_0h_ng_l"] = t0
        delta_1h = round(t1 - t0, 2) if t1 is not None else None
        delta_3h = round(t3 - t0, 2) if t3 is not None else None
        val["troponin_1h_ng_l"] = t1
        val["troponin_delta_1h"] = delta_1h
        val["troponin_3h_ng_l"] = t3
        val["troponin_delta_3h"] = delta_3h

        # ESC Qoidalari:
        # A) Rule-in (Infarkt / Nekroz tasdiqlandi):
        # 0h >= 52 ng/L YOKI delta 1h >= 5 ng/L YOKI delta 3h >= 10 ng/L
        if t0 >= 52.0 or (delta_1h is not None and delta_1h >= 5.0) or (delta_3h is not None and delta_3h >= 10.0):
            trop_status = "rule_in"
            trop_risk = RiskLevel.VERY_HIGH
            reason = f"hs-cTnI o'tkir miokard shikastlanishi darajasida (0h={t0} ng/L"
            if delta_1h is not None:
                reason += f", Δ1h={delta_1h} ng/L"
            reason += ") — O'tkir infarkt / NSTEMI xavfi juda yuqori!"
            expl.append(reason)

        # B) Rule-out (Infarkt inkor etildi):
        # (0h < 5 ng/L va simptomlar >= 2h) YOKI (0h < 12 ng/L va delta 1h < 3 ng/L)
        elif (t0 < 5.0 and inp.symptoms_onset_hours >= 2.0) or (t0 < 12.0 and delta_1h is not None and abs(delta_1h) < 3.0):
            trop_status = "rule_out"
            trop_risk = RiskLevel.LOW
            expl.append(f"hs-cTnI o'tkir miokard infarktini inkor etadi (0h={t0} ng/L, xavf past)")

        # C) Observe (Oraliq / Kuzatuv zonasi):
        else:
            trop_status = "observe"
            trop_risk = RiskLevel.MODERATE
            expl.append(f"hs-cTnI oraliq (kuzatuv) zonasida (0h={t0} ng/L) — 3 soatda takroriy tahlil va ExoKG zarur")

        val["troponin_decision"] = trop_status
        risks.append(trop_risk)

    # 2. NT-proBNP / BNP Dinamikasi (Yurak yetishmovchiligi)
    bnp_val = inp.nt_probnp_pg_ml if inp.nt_probnp_pg_ml is not None else inp.bnp_pg_ml
    bnp_type = "NT-proBNP" if inp.nt_probnp_pg_ml is not None else "BNP"

    bnp_key = "nt_probnp" if inp.nt_probnp_pg_ml is not None else "bnp"

    if bnp_val is not None:
        val[f"{bnp_key}_pg_ml"] = bnp_val
        # Buyrak yetishmovchiligi (kreatinin > 150 mkmol/l) klirensni pasaytiradi
        has_ckd = inp.creatinine_umol_l is not None and inp.creatinine_umol_l > 150.0

        # Yoshga bog'liq chegaralar (ICON study)
        if inp.age_years < 50:
            age_cutoff = 450.0
        elif inp.age_years <= 75:
            age_cutoff = 900.0
        else:
            age_cutoff = 1800.0

        if has_ckd:
            age_cutoff = max(age_cutoff, 1200.0)

        # Baholash
        if bnp_val >= 5000.0:
            bnp_status = "severe_decompensation"
            bnp_risk = RiskLevel.VERY_HIGH
            expl.append(f"{bnp_type}={bnp_val} pg/mL: O'tkir yaqqol dekompensatsiya va o'pka dimlanishi xavfi!")
        elif bnp_val >= age_cutoff:
            bnp_status = "elevated"
            bnp_risk = RiskLevel.HIGH
            expl.append(f"{bnp_type}={bnp_val} pg/mL (yosh chegarasi {int(age_cutoff)}): Yurak yetishmovchiligi dekompensatsiyasi belgilari")
        elif bnp_val < 300.0:
            bnp_status = "rule_out"
            bnp_risk = RiskLevel.LOW
            expl.append(f"{bnp_type}={bnp_val} pg/mL (< 300): O'tkir yurak yetishmovchiligi ehtimoli kam")
        else:
            bnp_status = "borderline"
            bnp_risk = RiskLevel.MODERATE
            expl.append(f"{bnp_type}={bnp_val} pg/mL: Mo''tadil miokard devori zo'riqishi")

        val[f"{bnp_key}_decision"] = bnp_status
        risks.append(bnp_risk)

    # Yakuniy xavf (Eng yuqori klinik xavf qoidasi)
    from core.evidence import RISK_ORDER

    final_risk = RiskLevel.LOW
    for r in risks:
        if RISK_ORDER.index(r) > RISK_ORDER.index(final_risk):
            final_risk = r

    val["overall_biomarker_risk"] = final_risk.value

    return Evidence(
        kind="lab.biomarkers",
        value=val,
        source=Source.RULE,
        provenance=BIOMARKER_PROV,
        risk=final_risk,
        explanation=expl,
    )
