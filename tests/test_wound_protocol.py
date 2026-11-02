"""Sternotomiya yarasi standart protokoli va eskalatsiya testlari (CDC NHSN / ASEPSIS)."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode, Handoff, Stage
from core.evidence import RiskLevel
from core.store import SqliteEpisodeStore
from guardian.checkin import assess_wound_protocol
from guardian.escalation import Alert, LogNotifier


def test_assess_wound_protocol_clean_healing():
    ev = assess_wound_protocol(
        erythema="none",
        edema="none",
        discharge="none",
        pain="mild_expected",
        warmth="normal",
        dehiscence="none",
        sternal_instability=False,
        fever=False,
    )
    assert ev.kind == "guardian.wound_protocol"
    assert ev.risk == RiskLevel.LOW
    assert not ev.abstained
    assert "yara holati qoniqarli" in ev.explanation[0]


def test_assess_wound_protocol_purulent_discharge_is_high():
    ev = assess_wound_protocol(
        discharge="purulent",
        erythema="spreading_over_2cm",
    )
    assert ev.risk == RiskLevel.HIGH
    assert any("yiringli ajralma" in exp for exp in ev.explanation)


def test_assess_wound_protocol_sternal_instability_is_high():
    ev = assess_wound_protocol(sternal_instability=True)
    assert ev.risk == RiskLevel.HIGH
    assert any("to'sh suyagi" in exp for exp in ev.explanation)


def test_assess_wound_protocol_fever_with_spreading_redness_is_high():
    # Spreading redness is moderate, but combined with fever becomes HIGH (deep SSI suspect)
    ev = assess_wound_protocol(erythema="spreading_over_2cm", fever=True)
    assert ev.risk == RiskLevel.HIGH
    assert any("isitma" in exp for exp in ev.explanation)


def test_assess_wound_protocol_mild_inflammatory_signs_are_moderate():
    ev = assess_wound_protocol(erythema="spreading_over_2cm", pain="increasing")
    assert ev.risk == RiskLevel.MODERATE


def test_wound_protocol_api_and_escalation(tmp_path):
    db = str(tmp_path / "wound_test.db")
    store = SqliteEpisodeStore(db)
    notifier = LogNotifier()
    client = TestClient(create_app(store, None, notifier=notifier))

    # 1. Epizod ochish va GUARDIAN_30D bosqichiga o'tkazish
    r = client.post("/episodes", json={"patient_ref": "P-WOUND-10", "population": "adult", "actor": "dr1"})
    assert r.status_code == 201
    eid = r.json()["id"]

    for st_from, st_to in [("screening", "workup"), ("workup", "heart_team"), ("heart_team", "procedure"), ("procedure", "icu"), ("icu", "discharge"), ("discharge", "guardian_30d")]:
        r_tr = client.post(f"/episodes/{eid}/transition", json={"from_stage": st_from, "to_stage": st_to, "author": "dr1"})
        assert r_tr.status_code == 200

    # 2. Toza yara tekshiruvi yuborish
    r_w1 = client.post(
        f"/episodes/{eid}/guardian/wound-protocol",
        json={
            "actor": "patient",
            "erythema": "none",
            "edema": "none",
            "discharge": "none",
            "pain": "mild_expected",
            "warmth": "normal",
        },
    )
    assert r_w1.status_code == 200
    assert r_w1.json()["escalation"]["alert"] == Alert.GREEN.value

    # 3. Kritik yiringli yara va to'sh beqarorligi yuborish -> RED Alert
    r_w2 = client.post(
        f"/episodes/{eid}/guardian/wound-protocol",
        json={
            "actor": "patient",
            "discharge": "purulent",
            "sternal_instability": True,
            "photo_ref": "photo_wound_001.jpg",
        },
    )
    assert r_w2.status_code == 200
    assert r_w2.json()["escalation"]["alert"] == Alert.RED.value
    assert len(notifier.sent) >= 1
    assert "P-WOUND-10" in notifier.sent[-1]
