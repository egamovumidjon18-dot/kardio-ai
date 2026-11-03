"""HL7 FHIR R4 Ingestion moduli testlari."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode
from core.fhir_ingest import ingest_fhir_data, LOINC_SYSTEM
from core.store import SqliteEpisodeStore


def test_fhir_ingest_troponin_and_ntprobnp():
    ep = Episode(patient_ref="BEMOR-FHIR-1", population="adult")
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {
                        "coding": [{"system": LOINC_SYSTEM, "code": "49563-0", "display": "Troponin I.cardiac [Mass/volume]"}]
                    },
                    "valueQuantity": {"value": 75.0, "unit": "ng/L"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {
                        "coding": [{"system": LOINC_SYSTEM, "code": "33762-6", "display": "NT-proBNP"}]
                    },
                    "valueQuantity": {"value": 2400.0, "unit": "pg/mL"},
                }
            },
        ],
    }

    res = ingest_fhir_data(bundle, episode=ep)
    assert res.success is True
    assert res.resources_processed == 2
    assert len(res.evidence_created) >= 1

    bio_ev = next(e for e in ep.evidence if e.kind == "lab.biomarkers")
    assert bio_ev.value["troponin_0h_ng_l"] == 75.0
    assert bio_ev.value["nt_probnp_pg_ml"] == 2400.0
    assert bio_ev.risk.value in ("high", "very_high")


def test_fhir_ingest_creatinine_unit_conversion():
    ep = Episode(patient_ref="BEMOR-FHIR-2", population="adult")
    # 2.0 mg/dL -> ~176.84 umol/L
    obs = {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{"system": LOINC_SYSTEM, "code": "2160-0", "display": "Creatinine"}]
        },
        "valueQuantity": {"value": 2.0, "unit": "mg/dL"},
    }

    res = ingest_fhir_data(obs, episode=ep)
    assert res.success is True
    kdigo_ev = next(e for e in ep.evidence if e.kind == "risk.kdigo")
    # mg/dL dan umol/L ga o'girilganligini tekshirish
    assert kdigo_ev.value["current_creatinine_umol_l"] == pytest.approx(176.84, abs=0.5)


def test_fhir_ingest_vitals_panel():
    ep = Episode(patient_ref="BEMOR-FHIR-3", population="adult")
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": LOINC_SYSTEM, "code": "85354-9"}]},
                    "component": [
                        {
                            "code": {"coding": [{"system": LOINC_SYSTEM, "code": "8480-6"}]},
                            "valueQuantity": {"value": 82.0, "unit": "mmHg"},  # Gipotoniya
                        },
                        {
                            "code": {"coding": [{"system": LOINC_SYSTEM, "code": "8462-4"}]},
                            "valueQuantity": {"value": 50.0, "unit": "mmHg"},
                        },
                    ],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": LOINC_SYSTEM, "code": "8867-4"}]},
                    "valueQuantity": {"value": 128.0, "unit": "/min"},  # Taxikardiya
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": LOINC_SYSTEM, "code": "59408-5"}]},
                    "valueQuantity": {"value": 88.0, "unit": "%"},      # Gipoksiya
                }
            },
        ],
    }

    res = ingest_fhir_data(bundle, episode=ep)
    assert res.success is True
    vitals_ev = next(e for e in ep.evidence if e.kind == "vitals.fhir")
    assert vitals_ev.risk.value == "very_high"
    assert any("Gipoksiya" in exp for exp in vitals_ev.explanation)
    assert any("Gipotoniya" in exp for exp in vitals_ev.explanation)


def test_fhir_ingest_api_endpoint(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "fhir_api.db"))
    app = create_app(store, None)
    client = TestClient(app)

    res_ep = client.post("/episodes", json={"patient_ref": "PAT-FHIR-777", "actor": "nurse"})
    eid = res_ep.json()["id"]

    fhir_obs = {
        "resourceType": "Observation",
        "code": {"coding": [{"system": LOINC_SYSTEM, "code": "6301-6"}]},
        "valueQuantity": {"value": 3.8, "unit": "{ratio}"},
    }

    res_post = client.post(f"/episodes/{eid}/fhir/ingest", json=fhir_obs)
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["success"] is True
    assert data["resources_processed"] == 1

    # Bemor dalillari tekshirish
    ep_data = client.get(f"/episodes/{eid}").json()
    assert any(e["kind"] == "guardian.inr" for e in ep_data["evidence"])
