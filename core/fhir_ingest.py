"""HL7 FHIR R4 Ikki Tomonlama Integratsiya va Qabul Qilish (Ingestion) Moduli.

Kasalxona axborot tizimlari (MIS / HIS / LIS) dan keladigan FHIR R4
standartidagi Observation va Bundle (laboratoriya tahlillari, biomarkerlar,
gemodinamik ko'rsatkichlar) resurslarini avtomatik tahlil qilib,
CardioPath AI klinik dalillari (Evidence) va xavf darajalariga o'tkazadi.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from core.episode import Episode
from core.evidence import Evidence, Provenance, RiskLevel, Source
from guardian.inr import assess_inr
from risk.biomarkers import BiomarkersInput, assess_biomarkers
from risk.kdigo import KDIGOInput, assess_kdigo

log = logging.getLogger("cardiopath.fhir.ingest")

LOINC_SYSTEM = "http://loinc.org"

# Standart LOINC kodlari xaritasi
LOINC_MAP = {
    # Troponin I va T
    "49563-0": "troponin",
    "6598-7": "troponin",
    "10839-9": "troponin",
    "89579-7": "troponin",
    # NT-proBNP va BNP
    "33762-6": "nt_probnp",
    "42637-9": "bnp",
    "30934-4": "bnp",
    # Buyrak (Kreatinin)
    "2160-0": "creatinine",
    "38483-4": "creatinine",
    # Koagulogramma (INR / MNO)
    "6301-6": "inr",
    # Elektrolitlar va qon tahlili
    "2823-3": "potassium",
    "718-7": "hemoglobin",
    # Vital ko'rsatkichlar
    "85354-9": "blood_pressure_panel",
    "8480-6": "systolic_bp",
    "8462-4": "diastolic_bp",
    "8867-4": "heart_rate",
    "59408-5": "spo2",
    "2708-6": "spo2",
    "8310-5": "temperature",
    "29463-7": "weight",
}


@dataclass
class FhirIngestResult:
    success: bool
    episode_id: str
    patient_ref: str
    resources_processed: int
    evidence_created: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "episode_id": self.episode_id,
            "patient_ref": self.patient_ref,
            "resources_processed": self.resources_processed,
            "evidence_created": self.evidence_created,
            "errors": self.errors,
        }


def _extract_resources(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """FHIR Bundle yoki Observation resurslarini yagona ro'yxatga ajratadi."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]

    if not isinstance(payload, dict):
        return []

    res_type = payload.get("resourceType")
    if res_type == "Bundle":
        entries = payload.get("entry", [])
        return [e.get("resource") for e in entries if isinstance(e, dict) and e.get("resource")]
    return [payload]


def _extract_loinc_code(obs: dict[str, Any]) -> Optional[str]:
    """Observation resursining 'code.coding' blokidan LOINC kodini oladi."""
    code_block = obs.get("code", {})
    codings = code_block.get("coding", [])
    for c in codings:
        if c.get("system") in (LOINC_SYSTEM, "http://loinc.org") or not c.get("system"):
            code = str(c.get("code", "")).strip()
            if code in LOINC_MAP:
                return code
    return None


def _normalize_quantity(val_q: dict[str, Any], loinc_type: str) -> Optional[float]:
    """Birliklar bo'yicha qiymatni standart SI formatiga keltiradi."""
    if not isinstance(val_q, dict):
        return None
    val = val_q.get("value")
    if val is None:
        return None
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return None

    unit = (val_q.get("unit") or val_q.get("code") or "").lower()

    # Kreatinin: mg/dL -> umol/L (1 mg/dL = 88.42 umol/L)
    if loinc_type == "creatinine":
        if "mg/dl" in unit:
            return round(fval * 88.42, 2)
        return round(fval, 2)

    # Troponin: ug/L yoki ng/mL -> ng/L (1 ng/mL = 1000 ng/L)
    if loinc_type == "troponin":
        if "ng/ml" in unit or "ug/l" in unit or "µg/l" in unit:
            return round(fval * 1000.0, 2)
        return round(fval, 2)

    return round(fval, 2)


def ingest_fhir_data(
    payload: dict[str, Any] | list[Any],
    episode: Episode,
    actor: str = "fhir_lis_service",
) -> FhirIngestResult:
    """FHIR JSON ma'lumotlarini qabul qilib, epizodga klinik dalillar sifatida qo'shadi."""
    resources = _extract_resources(payload)
    prov = Provenance(
        name="hl7_fhir_r4_ingest",
        version="4.0.1",
        reference="HL7 FHIR R4 Clinical Ingestion Protocol (LOINC Standardized)",
    )

    extracted_values: dict[str, Any] = {}
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    for res in resources:
        if res.get("resourceType") != "Observation":
            continue

        code = _extract_loinc_code(res)
        if not code:
            continue

        l_type = LOINC_MAP[code]
        val_q = res.get("valueQuantity")

        # Qon bosimi paneli componentlari
        if l_type == "blood_pressure_panel":
            for comp in res.get("component", []):
                c_code = _extract_loinc_code(comp)
                if c_code == "8480-6":
                    extracted_values["systolic_bp"] = _normalize_quantity(comp.get("valueQuantity", {}), "systolic_bp")
                elif c_code == "8462-4":
                    extracted_values["diastolic_bp"] = _normalize_quantity(comp.get("valueQuantity", {}), "diastolic_bp")
            continue

        if val_q:
            num = _normalize_quantity(val_q, l_type)
            if num is not None:
                extracted_values[l_type] = num

    # 1. Biomarkerlar (Troponin / NT-proBNP)
    if "troponin" in extracted_values or "nt_probnp" in extracted_values or "bnp" in extracted_values:
        # Epizodda oldingi troponin bormi?
        prev_t0 = None
        for ev in episode.evidence:
            if ev.kind == "lab.biomarkers" and isinstance(ev.value, dict):
                prev_t0 = ev.value.get("troponin_0h_ng_l")
                break

        curr_t = extracted_values.get("troponin")
        b_inp = BiomarkersInput(
            troponin_0h_ng_l=prev_t0 if prev_t0 is not None else curr_t,
            troponin_1h_ng_l=curr_t if prev_t0 is not None and curr_t != prev_t0 else None,
            nt_probnp_pg_ml=extracted_values.get("nt_probnp"),
            bnp_pg_ml=extracted_values.get("bnp"),
            creatinine_umol_l=extracted_values.get("creatinine"),
        )
        bio_ev = assess_biomarkers(b_inp)
        bio_ev.source = Source.CLINICIAN
        bio_ev.provenance = prov
        evidence_list.append(bio_ev)

    # 2. Buyrak (Kreatinin va KDIGO)
    if "creatinine" in extracted_values:
        creat = extracted_values["creatinine"]
        # Epizodda bazaviy kreatinin qidirish
        base_creat = creat
        for ev in episode.evidence:
            if ev.kind == "risk.kdigo" and isinstance(ev.value, dict):
                base_creat = ev.value.get("baseline_creatinine", creat)
                break

        k_ev = assess_kdigo(KDIGOInput(baseline_creatinine=base_creat, current_creatinine=creat))
        k_ev.source = Source.CLINICIAN
        k_ev.provenance = prov
        evidence_list.append(k_ev)

    # 3. Koagulogramma (INR / MNO)
    if "inr" in extracted_values:
        inr_val = extracted_values["inr"]
        inr_ev = assess_inr(inr_val, "mechanical_aortic", "HL7 FHIR R4 LIS Lab Report")
        inr_ev.source = Source.CLINICIAN
        inr_ev.provenance = prov
        evidence_list.append(inr_ev)

    # 4. Vital ko'rsatkichlar (Qon bosimi, HR, SpO2, harorat, vazn)
    vitals_keys = {"systolic_bp", "diastolic_bp", "heart_rate", "spo2", "temperature", "weight"}
    found_vitals = {k: extracted_values[k] for k in vitals_keys if k in extracted_values}
    if found_vitals:
        v_risk = RiskLevel.NORMAL
        v_expl = []

        hr = found_vitals.get("heart_rate")
        if hr is not None:
            if hr > 120 or hr < 45:
                v_risk = RiskLevel.HIGH
                v_expl.append(f"Yurak urishi kritik ({hr} zarba/min)")
            elif hr > 100 or hr < 50:
                v_risk = RiskLevel.MODERATE
                v_expl.append(f"Yurak urishi me'yordan tashqari ({hr} zarba/min)")

        spo2 = found_vitals.get("spo2")
        if spo2 is not None:
            if spo2 < 90:
                v_risk = RiskLevel.VERY_HIGH
                v_expl.append(f"Gipoksiya: SpO2 kritik darajada ({spo2}%)")
            elif spo2 < 94:
                v_risk = RiskLevel.HIGH
                v_expl.append(f"Gipoksiya: SpO2 pasaygan ({spo2}%)")

        sbp = found_vitals.get("systolic_bp")
        if sbp is not None:
            if sbp < 90:
                v_risk = RiskLevel.VERY_HIGH
                v_expl.append(f"Gipotoniya: Sistolik arterial bosim past ({sbp} mmHg)")
            elif sbp >= 180:
                v_risk = RiskLevel.HIGH
                v_expl.append(f"Gipertonik kriz: Sistolik bosim {sbp} mmHg")

        if not v_expl:
            v_expl.append("Vital ko'rsatkichlar me'yor oralig'ida")

        v_ev = Evidence(
            kind="vitals.fhir",
            value=found_vitals,
            source=Source.CLINICIAN,
            provenance=prov,
            risk=v_risk,
            explanation=v_expl,
        )
        evidence_list.append(v_ev)

    # Barcha yaratilgan dalillarni epizodga qo'shish
    for ev in evidence_list:
        episode.add(ev)

    return FhirIngestResult(
        success=len(evidence_list) > 0,
        episode_id=episode.id,
        patient_ref=episode.patient_ref,
        resources_processed=len(resources),
        evidence_created=[e.to_dict() for e in evidence_list],
        errors=errors,
    )
