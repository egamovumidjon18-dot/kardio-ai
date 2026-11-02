"""Bemorning yozma klinik roziligi registri testlari (ISO 13485 / O'zR Qonuni 24-moddasi)."""
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.consent import ConsentInput, get_clinical_consent, record_clinical_consent
from core.episode import Episode, Stage
from core.evidence import RiskLevel, Source
from core.store import SqliteEpisodeStore


def test_record_clinical_consent_valid():
    ep = Episode(patient_ref="P-ROZ-01", population="pediatric")
    inp = ConsentInput(
        clinician="Dr. Karimov A.B., kardioxirurg",
        paper_ref="ROZ-2026/0891",
        consent_type="treatment_and_ai",
        patient_or_guardian="guardian",
        guardian_relation="onasi",
        notes="Operatsiya va AI tahlili haqida to'liq tushuntirildi",
    )
    ev = record_clinical_consent(ep, inp, actor="dr_karimov")
    assert ev.kind == "consent.clinical"
    assert ev.risk == RiskLevel.LOW
    assert ev.source == Source.CLINICIAN
    assert ev.value["consented"] is True
    assert ev.value["paper_ref"] == "ROZ-2026/0891"
    assert ev.value["clinician"] == "Dr. Karimov A.B., kardioxirurg"
    assert ev.value["guardian_relation"] == "onasi"

    ep.add(ev)
    retrieved = get_clinical_consent(ep)
    assert retrieved is not None
    assert retrieved["paper_ref"] == "ROZ-2026/0891"


def test_record_clinical_consent_invalid_fields():
    ep = Episode(patient_ref="P-ROZ-02", population="pediatric")
    with pytest.raises(ValueError, match="shifokor F.I.Sh."):
        record_clinical_consent(ep, ConsentInput(clinician="", paper_ref="BLANK-1"), actor="dr")

    with pytest.raises(ValueError, match="Qog'oz rozilik blanki"):
        record_clinical_consent(ep, ConsentInput(clinician="Dr. X", paper_ref="   "), actor="dr")


def test_consent_api_endpoint_and_report_integration(tmp_path):
    db = str(tmp_path / "consent_test.db")
    store = SqliteEpisodeStore(db)
    client = TestClient(create_app(store, None))

    # 1. Epizod ochish
    r = client.post("/episodes", json={"patient_ref": "P-TEST-CONSENT", "population": "pediatric", "actor": "dr1"})
    assert r.status_code == 201
    eid = r.json()["id"]

    # 2. Hisobotda dastlab rozilik yo'qligi ogohlantirishi bor
    r_rep1 = client.get(f"/episodes/{eid}/report")
    assert r_rep1.status_code == 200
    assert "Yozma rozilik:</strong>" in r_rep1.text
    assert "Qog&#x27;oz blank qayd etilmagan" in r_rep1.text

    # 3. Yozma rozilik kiritish
    r_c = client.post(
        f"/episodes/{eid}/consent",
        json={
            "actor": "dr1",
            "clinician": "Dr. Rustamov S.",
            "paper_ref": "BLANK-2026-999",
            "consent_type": "treatment_and_ai",
            "patient_or_guardian": "patient",
        },
    )
    assert r_c.status_code == 200
    assert r_c.json()["evidence"]["kind"] == "consent.clinical"
    assert r_c.json()["evidence"]["value"]["paper_ref"] == "BLANK-2026-999"

    # 4. Hisobotda endi rozilik tasdiqlangan
    r_rep2 = client.get(f"/episodes/{eid}/report")
    assert r_rep2.status_code == 200
    assert "BLANK-2026-999" in r_rep2.text
    assert "Dr. Rustamov S." in r_rep2.text
