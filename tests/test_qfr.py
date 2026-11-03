"""Virtual QFR (Quantitative Flow Ratio) matematik va klinik testlari."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from angio.qfr import QfrInput, calculate_virtual_qfr, assess_qfr_evidence
from api.main import create_app
from core.evidence import RiskLevel
from core.store import SqliteEpisodeStore


def test_qfr_non_ischemic_lesion():
    # Yengil torayish: 3.2 mm tomirda 2.7 mm lümen (15.6% DS)
    inp = QfrInput(
        vessel="LAD",
        reference_diameter_mm=3.2,
        minimal_lumen_diameter_mm=2.7,
        lesion_length_mm=12.0,
        aortic_pressure_mmhg=90.0,
    )
    res = calculate_virtual_qfr(inp)
    assert res.qfr > 0.85
    assert res.is_ischemic is False
    assert res.risk_level == RiskLevel.NORMAL
    assert "talab etilmaydi" in res.clinical_recommendation


def test_qfr_critical_ischemic_lesion():
    # Og'ir torayish: 3.0 mm tomirda 0.85 mm lümen (71.7% DS), uzunligi 24 mm
    inp = QfrInput(
        vessel="LAD_PROX",
        reference_diameter_mm=3.0,
        minimal_lumen_diameter_mm=0.85,
        lesion_length_mm=24.0,
        aortic_pressure_mmhg=85.0,
    )
    res = calculate_virtual_qfr(inp)
    assert res.qfr <= 0.75
    assert res.is_ischemic is True
    assert res.risk_level == RiskLevel.VERY_HIGH
    assert "PCI" in res.clinical_recommendation or "CABG" in res.clinical_recommendation


def test_qfr_borderline_gray_zone():
    # Chegara holati: 0.75 < QFR <= 0.80
    inp = QfrInput(
        vessel="LAD",
        reference_diameter_mm=3.0,
        minimal_lumen_diameter_mm=1.1,
        lesion_length_mm=18.0,
        aortic_pressure_mmhg=90.0,
    )
    res = calculate_virtual_qfr(inp)
    assert 0.75 <= res.qfr <= 0.80
    assert res.is_ischemic is True
    assert res.risk_level == RiskLevel.HIGH

    ev = assess_qfr_evidence(inp)
    assert ev.kind == "angio.qfr"
    assert "Virtual QFR" in ev.explanation[0]


def test_qfr_api_endpoint(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "qfr_api.db"))
    app = create_app(store, None)
    client = TestClient(app)

    res_ep = client.post("/episodes", json={"patient_ref": "PAT-QFR-01", "actor": "dr_cath"})
    eid = res_ep.json()["id"]

    qfr_payload = {
        "actor": "dr_cath",
        "vessel": "LAD_PROX",
        "reference_diameter_mm": 3.0,
        "minimal_lumen_diameter_mm": 1.0,
        "lesion_length_mm": 18.0,
        "aortic_pressure_mmhg": 90.0,
    }

    res = client.post(f"/episodes/{eid}/angio/qfr", json=qfr_payload)
    assert res.status_code == 200
    data = res.json()
    assert "qfr" in data
    assert data["qfr"]["qfr"] <= 0.80
    assert data["evidence"]["kind"] == "angio.qfr"

    # Epizod audit logida qayd etilganini tekshirish
    audit_events = store.audit(eid)
    assert any(a["action"] == "angio.qfr" for a in audit_events)
