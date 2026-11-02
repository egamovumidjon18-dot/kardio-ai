"""Ko'p modalli (Multimodal) klinik sintez, ziddiyatlar va konsilium protokoli testlari."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode, Stage
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.fhir_export import export_episode_to_fhir
from integration.digest import episode_digest
from risk.protocol import heart_team_protocol


def test_multimodal_synthesis_and_discordance():
    ep = Episode(patient_ref="PAT-MULTI-99", population="adult", stage=Stage.HEART_TEAM)

    # 1. CXR Rentgen (Og'ir kardiomegaliya va dimlanish)
    ep.add(Evidence(
        kind="cxr.findings",
        source=Source.MODEL,
        provenance=Provenance("cxr_test", "v1"),
        risk=RiskLevel.VERY_HIGH,
        value={"ctr_ratio": 0.63, "cardiomegaly": True, "pulmonary_congestion": "severe"},
        explanation=["Og'ir kardiomegaliya (CTR=0.63)", "O'pka shishi / dimlanishi"]
    ))

    # 2. Biomarkerlar (Troponin Rule-In, NT-proBNP dekompensatsiya)
    ep.add(Evidence(
        kind="lab.biomarkers",
        source=Source.CLINICIAN,
        provenance=Provenance("bio_test", "v1"),
        risk=RiskLevel.VERY_HIGH,
        value={
            "troponin_decision": "rule_in",
            "nt_probnp_decision": "decompensation_very_likely",
            "troponin_0h_ng_l": 85.0,
            "troponin_1h_ng_l": 120.0,
            "nt_probnp_pg_ml": 2400.0,
        },
        explanation=["hs-cTnI 0h/1h o'tkir o'sishi (Rule-In)", "NT-proBNP dekompensatsiya"]
    ))

    # 3. ExoKG Klapanlar (Og'ir aortal stenoz va o'pka gipertenziyasi)
    ep.add(Evidence(
        kind="echo.valves",
        source=Source.CLINICIAN,
        provenance=Provenance("valves_test", "v1"),
        risk=RiskLevel.VERY_HIGH,
        value={
            "aortic_stenosis": {"grade": "severe", "severe": True},
            "mitral_regurgitation": {"grade": "mild", "severe": False},
            "pulmonary_hypertension": {"spap_mmhg": 58.0, "grade": "severe", "severe": True}
        },
        explanation=["Og'ir aortal stenoz", "Og'ir o'pka gipertenziyasi (sPAP=58 mmHg)"]
    ))

    # 4. Koronar angiografiya (LMS 70% stenozi)
    ep.add(Evidence(
        kind="angio.vessels",
        source=Source.CLINICIAN,
        provenance=Provenance("angio_test", "v1"),
        risk=RiskLevel.VERY_HIGH,
        value={"lms_stenosis_pct": 70.0, "lad_stenosis_pct": 85.0, "rca_stenosis_pct": 60.0},
        explanation=["Chap asosiy poya (LMS) 70% stenozi"]
    ))

    # 5. EKG Intervallari (Xavfli QTc)
    ep.add(Evidence(
        kind="ecg.intervals",
        source=Source.MODEL,
        provenance=Provenance("ecg_test", "v1"),
        risk=RiskLevel.HIGH,
        value={"hr_bpm": 88.0, "pr_ms": 170.0, "qrs_ms": 105.0, "qt_ms": 440.0, "qtc_bazett_ms": 532.0},
        explanation=["QTc Bazett 532 ms (xavfli uzayish)"]
    ))

    # 6. EKG AFIB (Low risk / normal ritm) -> Troponin bilan ziddiyatni tekshirish uchun
    ep.add(Evidence(
        kind="ecg.afib",
        source=Source.MODEL,
        provenance=Provenance("afib_test", "v1"),
        risk=RiskLevel.LOW,
        value={"p_afib": 0.05},
        explanation=["Sinusli ritm"]
    ))

    # 7. ExoKG EF (Saqlangan EF 55%) -> Rentgendagi dimlanish bilan HFpEF ziddiyatini tekshirish uchun
    ep.add(Evidence(
        kind="clinician.lvef",
        source=Source.CLINICIAN,
        provenance=Provenance("lvef_test", "v1"),
        risk=RiskLevel.LOW,
        value=55.0,
        explanation=["Simpson EF 55%"]
    ))

    # Epizod digest tahlili
    digest = episode_digest(ep)
    assert digest["overall_risk"] == "very_high"

    topics = [d["topic"] for d in digest["discussion"]]
    codes = [d["code"] for d in digest["discussion"]]

    assert "cxr_severe_cardio" in codes
    assert "cxr_congestion" in codes
    assert "bio_acs_rule_in" in codes
    assert "bio_hf_decomp" in codes
    assert "echo_severe_as" in codes
    assert "echo_severe_ph" in codes
    assert "angio_lms_stenosis" in codes
    assert "ecg_long_qtc" in codes
    assert "bio_ecg_discordance" in codes
    assert "cxr_echo_discordance" in codes

    # Heart Team protokoli tekshiruvi
    proto = heart_team_protocol(ep)
    assert "CXR Rentgen (kardiomegaliya, dimlanish)" in proto
    assert "Biomarkerlar (hs-cTnI / NT-proBNP)" in proto
    assert "ExoKG Klapanlar va sPAP" in proto
    assert "Koronar tomirlar va LMS" in proto
    assert "Chap asosiy poya (LMS)" in proto
    assert "QTc" in proto

    # HL7 FHIR R4 eksporti
    fhir = export_episode_to_fhir(ep, digest)
    assert fhir["resourceType"] == "Bundle"
    assert fhir["type"] == "document"

    obs_codes = []
    for entry in fhir["entry"]:
        res = entry["resource"]
        if res["resourceType"] == "Observation":
            for c in res.get("code", {}).get("coding", []):
                obs_codes.append(c.get("code"))
            for comp in res.get("component", []):
                for c in comp.get("code", {}).get("coding", []):
                    obs_codes.append(c.get("code"))

    # Barcha asosiy LOINC kodlari mavjud bo'lishi shart
    assert "36572-6" in obs_codes  # CXR
    assert "72271-0" in obs_codes  # CTR
    assert "49563-0" in obs_codes  # Troponin
    assert "33762-6" in obs_codes  # NT-proBNP
    assert "883-9" in obs_codes    # Echo
    assert "20230-9" in obs_codes  # sPAP
