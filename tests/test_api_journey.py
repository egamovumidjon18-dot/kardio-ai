"""To'liq bemor yo'li API orqali: skrining → ... → Heart Team → ... → Guardian → yopish."""
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.store import SqliteEpisodeStore
from guardian.escalation import LogNotifier

EUROSCORE = dict(age=58, female=False, weight_kg=75, creatinine_umol_l=90, nyha=2, lvef_percent=45,
                 urgency="elective", weight_of_intervention="single_non_cabg")
AKI = dict(female=False, congestive_heart_failure=False, lvef_percent=45, preop_iabp=False, copd=False,
           insulin_diabetes=False, previous_cardiac_surgery=False, emergency=False, surgery="valve",
           creatinine_umol_l=90)


@pytest.fixture
def ctx(tmp_path):
    notifier = LogNotifier()
    client = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "j.db")), None, None, notifier))
    return client, notifier


def move(client, eid, frm, to, ids=(), questions=()):
    r = client.post(f"/episodes/{eid}/transition", json={"from_stage": frm, "to_stage": to, "author": "dr",
                                                         "evidence_ids": list(ids), "open_questions": list(questions)})
    assert r.status_code == 200, r.text


def test_full_patient_journey(ctx):
    client, notifier = ctx
    eid = client.post("/episodes", json={"patient_ref": "PSV-900", "population": "adult"}).json()["id"]
    assert client.post(f"/episodes/{eid}/risk", json={"actor": "dr", "euroscore": EUROSCORE, "aki": AKI}).status_code == 409

    move(client, eid, "screening", "workup")
    move(client, eid, "workup", "heart_team", questions=["Mitral klapan: plastika yoki protez?"])
    r = client.post(f"/episodes/{eid}/risk", json={"actor": "dr.k", "euroscore": EUROSCORE, "aki": AKI})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence"][0]["kind"] == "risk.euroscore2" and body["evidence"][0]["value"] > 0.5
    assert body["aki_concordance"]["status"] == "rule_only"

    proto = client.get(f"/episodes/{eid}/heart-team-protocol")
    assert proto.status_code == 200 and "Mitral klapan" in proto.text and "EuroSCORE II" in proto.text

    for frm, to in [("heart_team", "procedure"), ("procedure", "icu"), ("icu", "discharge"), ("discharge", "guardian_30d")]:
        move(client, eid, frm, to)

    ok = client.post(f"/episodes/{eid}/guardian/checkin",
                     json={"actor": "patient", "measured_at": "2026-11-01T08:00:00", "weight_kg": 70,
                           "heart_rate": 78, "spo2": 97})
    assert ok.json()["escalation"]["alert"] == "green" and notifier.sent == []

    bad = client.post(f"/episodes/{eid}/guardian/checkin",
                      json={"actor": "patient", "measured_at": "2026-11-03T08:00:00+00:00", "weight_kg": 72.4,
                            "wound_signs": ["purulent_discharge"]})
    esc = bad.json()["escalation"]
    assert esc["alert"] == "red" and esc["notified"] and len(notifier.sent) == 1
    assert "3 kun" not in esc["patient_message"] and "103" in esc["patient_message"]
    assert any("≥2 kg" in r for r in esc["reasons"])

    inr = client.post(f"/episodes/{eid}/guardian/inr",
                      json={"actor": "patient", "indication": "mechanical_mitral", "ocr_text": "MNO: 2,9"})
    assert inr.json()["escalation"]["alert"] == "green" and inr.json()["evidence"][0]["value"] == 2.9

    assert client.post(f"/episodes/{eid}/guardian/checkin", json={"actor": "p"}).status_code == 422
    move(client, eid, "guardian_30d", "closed")
    assert client.post(f"/episodes/{eid}/guardian/inr", json={"actor": "p", "indication": "af", "value": 2.5}).status_code == 409

    actions = [a["action"] for a in client.get(f"/episodes/{eid}/audit").json()]
    assert actions.count("guardian.checkin") == 2 and "risk.assess" in actions
