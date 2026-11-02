import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.consent import ConsentInput, record_clinical_consent
from core.episode import Episode
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.fhir_export import export_episode_to_fhir
from core.store import SqliteEpisodeStore


def test_fhir_bundle_structure():
    ep = Episode(patient_ref="BEMOR-FHIR-777", population="adult")
    inp = ConsentInput(
        clinician="Dr. Akromov",
        paper_ref="V-2026-999",
        consent_type="surgery_and_ai",
        notes="Bemor to'liq xabardor qilingan holda imzoladi",
    )
    ep.add(record_clinical_consent(ep, inp, actor="dr_akromov"))

    # ECG dalili
    ep.add(
        Evidence(
            kind="ecg.intervals",
            value={
                "heart_rate_bpm": 74.0,
                "pr_interval_ms": 160.0,
                "qrs_duration_ms": 95.0,
                "qt_interval_ms": 380.0,
                "qtc_bazett_ms": 421.0,
            },
            risk=RiskLevel.LOW,
            source=Source.RULE,
            provenance=Provenance(name="ecg.intervals"),
            explanation=["Normal sinus ritmi"],
        )
    )

    # KDIGO AKI dalili
    ep.add(
        Evidence(
            kind="risk.kdigo",
            value={"stage": 1, "stage_name": "Stage 1 (Yengil shikastlanish)", "risk": "moderate"},
            risk=RiskLevel.MODERATE,
            source=Source.RULE,
            provenance=Provenance(name="risk.kdigo"),
            explanation=["Kreatinin 48 soatda 26.5 mkmol/l dan ortiq oshdi"],
        )
    )

    # EuroSCORE II
    ep.add(
        Evidence(
            kind="risk.euroscore2",
            value=3.45,
            risk=RiskLevel.LOW,
            source=Source.RULE,
            provenance=Provenance(name="euroscore2.calc"),
            explanation=["Operatsion o'lim xavfi: 3.45%"],
        )
    )

    # ExoKG EF
    ep.add(
        Evidence(
            kind="echo.ef",
            value=45.0,
            risk=RiskLevel.MODERATE,
            source=Source.RULE,
            provenance=Provenance(name="echo.simpson"),
            explanation=["EF 45% (Mo''tadil pasaygan)"],
        )
    )

    digest = {"overall_risk": "moderate", "discussion": []}
    bundle = export_episode_to_fhir(ep, digest)

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    assert bundle["identifier"]["value"] == ep.id

    entries = bundle["entry"]
    assert len(entries) >= 5

    # 1. First entry must be Composition (FHIR Document Bundle requirement)
    first_res = entries[0]["resource"]
    assert first_res["resourceType"] == "Composition"
    assert first_res["type"]["coding"][0]["code"] == "11488-4"

    # Find resources by type
    res_map = {}
    observations = []
    for entry in entries:
        res = entry["resource"]
        t = res["resourceType"]
        if t == "Observation":
            observations.append(res)
        else:
            res_map[t] = res

    # 2. Patient
    assert "Patient" in res_map
    assert res_map["Patient"]["identifier"][0]["value"] == "BEMOR-FHIR-777"

    # 3. Consent
    assert "Consent" in res_map
    assert res_map["Consent"]["identifier"][0]["value"] == "V-2026-999"
    assert res_map["Consent"]["performer"][0]["display"] == "Dr. Akromov"

    # 4. RiskAssessment
    assert "RiskAssessment" in res_map
    pred = res_map["RiskAssessment"]["prediction"][0]
    assert pred["qualitativeRisk"]["coding"][0]["code"] == "moderate"

    # 5. Observations check
    kinds = {obs["code"]["text"] for obs in observations}
    assert "ecg.intervals" in kinds
    assert "risk.kdigo" in kinds
    assert "risk.euroscore2" in kinds
    assert "echo.ef" in kinds

    # Verify LOINC codes inside observations
    ecg_obs = next(obs for obs in observations if obs["code"]["text"] == "ecg.intervals")
    comp_codes = {c["code"]["coding"][0]["code"] for c in ecg_obs["component"]}
    assert "8633-0" in comp_codes  # QTc
    assert "8625-6" in comp_codes  # PR
    assert "8631-4" in comp_codes  # QRS


def test_fhir_api_endpoint(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "test_fhir.db"))
    app = create_app(store=store, pcg=None, auth=False)
    client = TestClient(app)

    # Epizod ochish
    res = client.post("/episodes", json={"patient_ref": "FHIR-PAT-001", "actor": "dr_test"})
    assert res.status_code == 201
    eid = res.json()["id"]

    # Rozilik kiritish
    client.post(
        f"/episodes/{eid}/consent",
        json={
            "clinician": "Kardiolog Karimov",
            "paper_ref": "SH-789",
            "consent_type": "surgery_and_ai",
            "actor": "dr_test",
        },
    )

    # FHIR endpointni chaqirish
    fhir_res = client.get(f"/episodes/{eid}/fhir")
    assert fhir_res.status_code == 200
    bundle = fhir_res.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    assert any(e["resource"]["resourceType"] == "Composition" for e in bundle["entry"])
    assert any(e["resource"]["resourceType"] == "Consent" for e in bundle["entry"])
