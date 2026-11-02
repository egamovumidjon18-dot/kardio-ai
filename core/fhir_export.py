"""HL7 FHIR R4 standart klinik hujjat (Bundle) eksport moduli.

Kasalxona axborot tizimlari (MIS / HIS / PACS) bilan xalqaro standartda
integratsiya qilish uchun bemor epizodi, laboratoriya, EKG, ExoKG,
KDIGO AKI, rozilik va xavf baholarini FHIR R4 JSON formatiga o'tkazadi.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from core.consent import get_clinical_consent
from core.episode import Episode
from core.evidence import Evidence, RiskLevel

LOINC_SYSTEM = "http://loinc.org"
SNOMED_SYSTEM = "http://snomed.info/sct"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def export_episode_to_fhir(ep: Episode, digest: Optional[dict] = None) -> dict[str, Any]:
    """Epizod ma'lumotlarini to'liq HL7 FHIR R4 Document Bundle shakliga keltiradi."""
    bundle_id = str(uuid.uuid4())
    patient_id = f"patient-{ep.patient_ref}"
    composition_id = f"comp-{ep.id}"
    now_str = _utcnow()

    entries: list[dict[str, Any]] = []

    # 1. Patient resursi (de-identifikatsiyalangan)
    patient_resource = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [
            {
                "use": "usual",
                "type": {
                    "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR", "display": "Medical Record Number"}]
                },
                "value": ep.patient_ref,
            }
        ],
        "active": True,
    }
    entries.append({"fullUrl": f"urn:uuid:{patient_id}", "resource": patient_resource})

    # 2. Consent resursi (Yozma rozilik)
    c_info = get_clinical_consent(ep)
    if c_info:
        consent_id = f"consent-{ep.id}"
        consent_resource = {
            "resourceType": "Consent",
            "id": consent_id,
            "status": "active",
            "scope": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "patient-privacy", "display": "Privacy Consent"}]
            },
            "category": [
                {
                    "coding": [{"system": LOINC_SYSTEM, "code": "59284-0", "display": "Consent Document"}],
                    "text": c_info.get("consent_type", "treatment_and_ai"),
                }
            ],
            "patient": {"reference": f"urn:uuid:{patient_id}"},
            "dateTime": c_info.get("consented_at", now_str),
            "performer": [{"display": c_info.get("clinician", "Shifokor")}],
            "provision": {
                "type": "permit",
                "purpose": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "TREAT", "display": "treatment"}],
            },
            "identifier": [{"system": "http://hospital.uz/consent-forms", "value": c_info.get("paper_ref", "—")}],
        }
        entries.append({"fullUrl": f"urn:uuid:{consent_id}", "resource": consent_resource})

    # 3. Observation resurslari (Har bir Evidence uchun)
    observation_refs = []
    for idx, ev in enumerate(ep.evidence):
        obs_id = f"obs-{ev.id or idx}"
        observation_refs.append({"reference": f"urn:uuid:{obs_id}"})

        code_coding = [{"system": "http://cardiopath.ai/evidence", "code": ev.kind, "display": ev.kind}]
        value_data: dict[str, Any] = {}

        # Modallik bo'yicha LOINC kodlar va qiymatlar
        if ev.kind == "ecg.intervals" and isinstance(ev.value, dict):
            code_coding.append({"system": LOINC_SYSTEM, "code": "8867-4", "display": "Heart rate"})
            components = []
            for k, loinc_c, disp, unit in [
                ("qtc_bazett_ms", "8633-0", "QTc Bazett interval", "ms"),
                ("pr_interval_ms", "8625-6", "PR interval", "ms"),
                ("qrs_duration_ms", "8631-4", "QRS duration", "ms"),
                ("heart_rate_bpm", "8867-4", "Heart rate", "/min"),
            ]:
                if ev.value.get(k) is not None:
                    components.append({
                        "code": {"coding": [{"system": LOINC_SYSTEM, "code": loinc_c, "display": disp}]},
                        "valueQuantity": {"value": float(ev.value[k]), "unit": unit},
                    })
            value_data["component"] = components

        elif ev.kind == "risk.kdigo" and isinstance(ev.value, dict):
            code_coding.append({"system": LOINC_SYSTEM, "code": "72271-0", "display": "KDIGO Acute Kidney Injury Stage"})
            value_data["valueCodeableConcept"] = {
                "text": f"Stage {ev.value.get('stage', 0)} ({ev.value.get('stage_name', 'Normal')})"
            }

        elif ev.kind == "risk.euroscore2" and isinstance(ev.value, (int, float)):
            code_coding.append({"system": LOINC_SYSTEM, "code": "82747-7", "display": "EuroSCORE II mortality risk"})
            value_data["valueQuantity"] = {"value": float(ev.value), "unit": "%"}

        elif ev.kind == "echo.ef" and isinstance(ev.value, (int, float)):
            code_coding.append({"system": LOINC_SYSTEM, "code": "10230-1", "display": "Left ventricular Ejection fraction"})
            value_data["valueQuantity"] = {"value": float(ev.value), "unit": "%"}

        elif ev.kind == "cxr.findings" and isinstance(ev.value, dict):
            code_coding.append({"system": LOINC_SYSTEM, "code": "36572-6", "display": "Chest X-ray view"})
            comps = []
            if "ctr_ratio" in ev.value:
                comps.append({
                    "code": {"coding": [{"system": LOINC_SYSTEM, "code": "72271-0", "display": "Cardiothoracic ratio"}]},
                    "valueQuantity": {"value": float(ev.value["ctr_ratio"]), "unit": "ratio"}
                })
            value_data["component"] = comps
            value_data["valueString"] = f"CTR: {ev.value.get('ctr_ratio')}; Kardiomegaliya: {ev.value.get('cardiomegaly')}; O'pka dimlanishi: {ev.value.get('pulmonary_congestion')}"

        elif ev.kind == "echo.valves" and isinstance(ev.value, dict):
            code_coding.append({"system": LOINC_SYSTEM, "code": "883-9", "display": "Echocardiogram study"})
            comps = []
            val = ev.value
            as_info = val.get("aortic_stenosis", {})
            mr_info = val.get("mitral_regurgitation", {})
            ph_info = val.get("pulmonary_hypertension", {})
            if ph_info.get("spap_mmhg") is not None:
                comps.append({
                    "code": {"coding": [{"system": LOINC_SYSTEM, "code": "20230-9", "display": "Systolic pulmonary artery pressure"}]},
                    "valueQuantity": {"value": float(ph_info["spap_mmhg"]), "unit": "mmHg"}
                })
            value_data["component"] = comps
            value_data["valueString"] = f"AS: {as_info.get('grade')}; MR: {mr_info.get('grade')}; sPAP: {ph_info.get('spap_mmhg')} mmHg"

        elif ev.kind == "lab.biomarkers" and isinstance(ev.value, dict):
            comps = []
            if ev.value.get("troponin_0h_ng_l") is not None:
                code_coding.append({"system": LOINC_SYSTEM, "code": "49563-0", "display": "Cardiac troponin I in Serum or Plasma"})
                comps.append({
                    "code": {"coding": [{"system": LOINC_SYSTEM, "code": "49563-0", "display": "hs-cTnI 0h"}]},
                    "valueQuantity": {"value": float(ev.value["troponin_0h_ng_l"]), "unit": "ng/L"}
                })
            if ev.value.get("nt_probnp_pg_ml") is not None:
                code_coding.append({"system": LOINC_SYSTEM, "code": "33762-6", "display": "NT-proBNP in Serum or Plasma"})
                comps.append({
                    "code": {"coding": [{"system": LOINC_SYSTEM, "code": "33762-6", "display": "NT-proBNP"}]},
                    "valueQuantity": {"value": float(ev.value["nt_probnp_pg_ml"]), "unit": "pg/mL"}
                })
            value_data["component"] = comps
            value_data["valueString"] = f"Troponin: {ev.value.get('troponin_decision')}; NT-proBNP: {ev.value.get('nt_probnp_decision')}" 

        else:
            value_data["valueString"] = str(ev.value) if ev.value is not None else "—"

        obs_resource = {
            "resourceType": "Observation",
            "id": obs_id,
            "status": "final",
            "code": {"coding": code_coding, "text": ev.kind},
            "subject": {"reference": f"urn:uuid:{patient_id}"},
            "effectiveDateTime": ev.created_at or now_str,
            "interpretation": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": "A" if ev.risk in (RiskLevel.HIGH, RiskLevel.VERY_HIGH) else "N",
                            "display": ev.risk.value.upper(),
                        }
                    ],
                    "text": f"Risk: {ev.risk.value}",
                }
            ],
            "note": [{"text": "; ".join(ev.explanation)}] if ev.explanation else [],
            **value_data,
        }
        entries.append({"fullUrl": f"urn:uuid:{obs_id}", "resource": obs_resource})

    # 4. RiskAssessment resursi
    overall_risk = (digest.get("overall_risk") if digest else None) or "unknown"
    risk_id = f"risk-{ep.id}"
    risk_resource = {
        "resourceType": "RiskAssessment",
        "id": risk_id,
        "status": "final",
        "subject": {"reference": f"urn:uuid:{patient_id}"},
        "occurrenceDateTime": now_str,
        "prediction": [
            {
                "outcome": {"text": "Cardiovascular surgical and clinical outcome risk"},
                "qualitativeRisk": {
                    "coding": [{"system": "http://cardiopath.ai/risk-levels", "code": overall_risk, "display": overall_risk.upper()}]
                },
            }
        ],
        "basis": observation_refs,
    }
    entries.append({"fullUrl": f"urn:uuid:{risk_id}", "resource": risk_resource})

    # 5. Composition (Klinik epikriz sarvarag'i)
    composition_resource = {
        "resourceType": "Composition",
        "id": composition_id,
        "status": "final",
        "type": {
            "coding": [{"system": LOINC_SYSTEM, "code": "11488-4", "display": "Consultation note"}],
            "text": "CardioPath-AI Kardiologik Klinik Xulosa",
        },
        "subject": {"reference": f"urn:uuid:{patient_id}"},
        "date": now_str,
        "title": "CardioPath-AI Konsilium va Klinik Tahlil Epikrizi",
        "section": [
            {
                "title": "Klinik Dalillar (Observations)",
                "entry": observation_refs,
            },
            {
                "title": "Yig'ma Xavf Baholash (Risk Assessment)",
                "entry": [{"reference": f"urn:uuid:{risk_id}"}],
            },
        ],
    }
    # Composition hujjatning birinchi elementi bo'lishi kerak
    entries.insert(0, {"fullUrl": f"urn:uuid:{composition_id}", "resource": composition_resource})

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "identifier": {"system": "http://cardiopath.ai/episodes", "value": ep.id},
        "type": "document",
        "timestamp": now_str,
        "entry": entries,
    }
    return bundle
