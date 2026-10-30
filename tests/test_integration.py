"""AI modullarni tizimga ulash: EF solishtiruvi, kiritilmagan maydonlar, epizod xulosasi (digest), Heart Team protokoli."""
import pytest
from fastapi.testclient import TestClient

from adapters.echo_ef import ef_risk
from api.main import create_app
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.store import SqliteEpisodeStore

ES = dict(age=60, female=False, weight_kg=80, creatinine_umol_l=90, nyha=2, urgency="elective",
          weight_of_intervention="single_non_cabg", pa_systolic_mmhg=30)
AKI = dict(female=False, congestive_heart_failure=False, lvef_percent=55, preop_iabp=False, copd=False,
           insulin_diabetes=False, previous_cardiac_surgery=False, emergency=False, surgery="valve", creatinine_umol_l=90)


@pytest.fixture
def env(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "i.db"))
    return TestClient(create_app(store, None)), store


def to_stage(client, eid, *stages):
    cur = client.get(f"/episodes/{eid}").json()["stage"]
    for s in stages:
        r = client.post(f"/episodes/{eid}/transition", json={"from_stage": cur, "to_stage": s, "author": "dr"})
        assert r.status_code == 200, r.text
        cur = s


def heart_team_episode(client, ref="HT-1"):
    eid = client.post("/episodes", json={"patient_ref": ref, "population": "adult"}).json()["id"]
    to_stage(client, eid, "workup", "heart_team")
    return eid


def risk(client, eid, lvef=55, es_extra=None, **aki):
    body = {"actor": "dr", "euroscore": {**ES, **(es_extra or {})}, "aki": {**AKI, "lvef_percent": lvef, **aki}}
    return client.post(f"/episodes/{eid}/risk", json=body)


def inject(store, eid, ev):
    ep = store.get(eid)
    ep.add(ev)
    store.save(ep, "test", "inject")
    return ev


def echo_ef(value=None, abstained=False):
    prov = Provenance(name="echo_ef_r2plus1d", version="t")
    if abstained:
        return Evidence.abstain("echo.ef", Source.MODEL, prov, "kontrast past")
    return Evidence(kind="echo.ef", value=value, unit="%", source=Source.MODEL, provenance=prov,
                    risk=ef_risk(value), uncertainty=5.8, explanation=[f"EF ≈ {value:.0f}%"])


# ---- EF: shifokor vs AI
def test_ef_agree_disagree_abstain(env):
    client, store = env
    cases = [(55, echo_ef(52), "agree", False), (55, echo_ef(28), "disagree", True), (55, echo_ef(abstained=True), "ai_abstained", True)]
    for i, (lvef, ev, status, discuss) in enumerate(cases):
        eid = heart_team_episode(client, f"EF-{i}")
        assert risk(client, eid, lvef=lvef).status_code == 200
        inject(store, eid, ev)
        d = client.get(f"/episodes/{eid}/digest").json()
        ef = next(c for c in d["concordance"] if c["question"].startswith("LVEF"))
        assert ef["status"] == status and ef["needs_discussion"] is discuss
        assert any(x["code"] == f"ef_{status}" for x in d["discussion"]) is discuss
        assert ("LVEF (shifokor vs AI):** " + status) in client.get(f"/episodes/{eid}/heart-team-protocol").text


def test_ef_disagreement_never_lowers_risk_and_shows_numbers(env):
    client, store = env
    eid = heart_team_episode(client)
    risk(client, eid, lvef=55)
    inject(store, eid, echo_ef(28))
    ef = next(c for c in client.get(f"/episodes/{eid}/digest").json()["concordance"] if c["question"].startswith("LVEF"))
    assert ef["final_risk"] == "very_high"                        # AI yomonroq → xavf oshadi
    assert "Shifokor 55%, AI 28% (farq -27" in ef["message"]
    eid2 = heart_team_episode(client, "EF-2")
    risk(client, eid2, lvef=25)
    inject(store, eid2, echo_ef(60))
    ef2 = next(c for c in client.get(f"/episodes/{eid2}/digest").json()["concordance"] if c["question"].startswith("LVEF"))
    assert ef2["status"] == "disagree" and ef2["final_risk"] == "very_high"   # AI yaxshiroq desa ham xavf pasaymaydi


def test_ef_same_category_but_big_gap_is_noted(env):
    client, store = env
    eid = heart_team_episode(client)
    risk(client, eid, lvef=62)
    inject(store, eid, echo_ef(50))
    ef = next(c for c in client.get(f"/episodes/{eid}/digest").json()["concordance"] if c["question"].startswith("LVEF"))
    assert ef["status"] == "agree" and "10 punktdan katta" in ef["message"]


def test_no_ef_concordance_without_both_sides(env):
    client, store = env
    eid = heart_team_episode(client)
    d = client.get(f"/episodes/{eid}/digest").json()
    assert not any(c["question"].startswith("LVEF") for c in d["concordance"])
    inject(store, eid, echo_ef(40))                                # AI bor, shifokor LVEF'i yo'q
    d = client.get(f"/episodes/{eid}/digest").json()
    assert not any(c["question"].startswith("LVEF") for c in d["concordance"])
    assert d["suggestions"][0]["code"] == "enter_lvef" and "AI qiymati o'zi to'ldirilmaydi" in d["suggestions"][0]["text"]


# ---- kiritish tekshiruvlari
def test_repeated_open_question_is_listed_once(env):
    client, _ = env
    eid = client.post("/episodes", json={"patient_ref": "Q-1", "population": "adult"}).json()["id"]
    for frm, to in (("screening", "workup"), ("workup", "heart_team")):
        client.post(f"/episodes/{eid}/transition", json={"from_stage": frm, "to_stage": to, "author": "dr",
                                                         "open_questions": ["Mitral: plastika yoki protez?", f"savol {to}"]})
    assert client.get(f"/episodes/{eid}/digest").json()["open_questions"] == [
        "Mitral: plastika yoki protez?", "savol workup", "savol heart_team"]


def test_conflicting_lvef_is_rejected(env):
    client, _ = env
    eid = heart_team_episode(client)
    r = client.post(f"/episodes/{eid}/risk", json={"actor": "dr", "euroscore": {**ES, "lvef_percent": 45}, "aki": {**AKI, "lvef_percent": 50}})
    assert r.status_code == 422 and "LVEF ikki blokda har xil" in r.json()["detail"]


def test_euroscore_uses_aki_lvef_when_omitted_and_flags_other_defaults(env):
    client, _ = env
    eid = heart_team_episode(client)
    body = {"actor": "dr", "euroscore": dict(age=60, female=False, weight_kg=80, creatinine_umol_l=90), "aki": {**AKI, "lvef_percent": 25}}
    r = client.post(f"/episodes/{eid}/risk", json=body).json()
    assert set(r["assumed_defaults"]) == {"nyha", "urgency", "weight_of_intervention", "pa_systolic_mmhg"}
    assert r["evidence"][0]["kind"] == "risk.euroscore2"            # mavjud mijozlar tartibi buzilmagan
    assert any("EF 25%" in line for line in r["evidence"][0]["explanation"])     # LVEF AKI blokidan olindi
    d = client.get(f"/episodes/{eid}/digest").json()
    assert any(x["code"] == "assumed_defaults" and "nyha" in x["reason"] for x in d["discussion"])
    protocol = client.get(f"/episodes/{eid}/heart-team-protocol").text
    assert "nyha: kiritilmadi → NYHA I (simptom yo'q) deb olindi" in protocol    # protokolda muhokama punkti sifatida ko'rinadi


def test_fully_specified_euroscore_has_no_assumptions(env):
    client, _ = env
    eid = heart_team_episode(client)
    r = risk(client, eid, lvef=55).json()
    assert r["assumed_defaults"] == []
    assert not any(x["code"] == "assumed_defaults" for x in client.get(f"/episodes/{eid}/digest").json()["discussion"])


# ---- digest
def test_digest_structure_and_ai_states(env):
    client, store = env
    eid = heart_team_episode(client)
    risk(client, eid)
    inject(store, eid, Evidence(kind="ecg.afib", value={"p_afib": 0.93, "other_findings": []}, source=Source.MODEL,
                                provenance=Provenance(name="ecg_cnn_ptbxl", version="t"), risk=RiskLevel.HIGH, explanation=["AFIB 0.93"]))
    inject(store, eid, Evidence(kind="angio.stenosis_assist", value={"n_candidates": 2}, source=Source.MODEL,
                                provenance=Provenance(name="angio_stenosis_unet", version="t"), risk=RiskLevel.MODERATE, explanation=["2 ta nomzod"]))
    d = client.get(f"/episodes/{eid}/digest").json()
    assert d["episode"]["stage"] == "heart_team" and d["next_stages"] == ["closed", "procedure", "workup"]
    assert d["ai"]["ecg"]["state"] == "ok" and d["ai"]["ecg"]["risk"] == "high"
    assert d["ai"]["angio"]["state"] == "ok" and d["ai"]["pcg"]["state"] == "not_run" and d["ai"]["echo_ef"]["state"] == "not_run"
    codes = {x["code"] for x in d["discussion"]}
    assert {"afib_high", "angio_candidates"} <= codes
    # EuroSCORE II, Thakar, shifokor LVEF'i + qo'lda qo'shilgan EKG va angiografiya (hamma maydon kiritilgan → taxmin yo'q)
    assert d["latest"]["risk.euroscore2"]["value"] > 0 and d["counts"]["evidence"] == 5
    assert "risk.assumptions" not in d["latest"]
    assert client.get("/episodes/nope/digest").status_code == 404


def test_protocol_contains_ai_section_and_blocks_nothing(env):
    client, store = env
    eid = heart_team_episode(client)
    risk(client, eid)
    inject(store, eid, Evidence(kind="ecg.afib", value={"p_afib": 0.93, "other_findings": ["ST-T o'zgarishlari"]}, source=Source.MODEL,
                                provenance=Provenance(name="ecg_cnn_ptbxl", version="t"), risk=RiskLevel.HIGH, explanation=["x"]))
    inject(store, eid, echo_ef(abstained=True))
    text = client.get(f"/episodes/{eid}/heart-team-protocol").text
    assert "AI yordamchi topilmalari" in text and "AFIB ehtimoli 0.93; boshqa: ST-T o'zgarishlari" in text
    assert "AI javob bermadi" in text and "kontrast past" in text           # abstain yashirilmaydi
    assert "Angiografiya (SYNTAX-ga yordamchi) | — | bajarilmagan" in text
    assert "YAKUNIY TASHXIS EMAS" in text


# ---- signallar
def guardian_episode(client, ref="G-1"):
    eid = client.post("/episodes", json={"patient_ref": ref, "population": "adult"}).json()["id"]
    to_stage(client, eid, "workup", "heart_team", "procedure", "icu", "discharge", "guardian_30d")
    return eid


def checkin(client, eid, **kw):
    return client.post(f"/episodes/{eid}/guardian/checkin", json={"actor": "patient", **kw})


def test_alerts_created_listed_and_acknowledged(env):
    client, _ = env
    a, b, c = guardian_episode(client, "G-A"), guardian_episode(client, "G-B"), guardian_episode(client, "G-C")
    assert checkin(client, a, heart_rate=110).json()["alert_id"] is not None            # sariq
    red = checkin(client, b, wound_signs=["purulent_discharge"]).json()
    assert red["escalation"]["alert"] == "red" and red["alert_id"] is not None
    assert checkin(client, c, heart_rate=78, spo2=97).json()["alert_id"] is None        # yashil → signal yo'q

    body = client.get("/alerts").json()
    assert body["total"] == 2 and [x["level"] for x in body["items"]] == ["red", "amber"]   # qizil birinchi
    top = body["items"][0]
    assert top["patient_ref"] == "G-B" and top["acknowledged"] is False and top["reasons"] and top["source"] == "guardian.checkin"
    assert [x["level"] for x in client.get("/alerts", params={"level": "amber"}).json()["items"]] == ["amber"]
    assert client.get("/alerts", params={"level": "blue"}).status_code == 422

    summary = {i["patient_ref"]: i for i in client.get("/episodes").json()["items"]}
    assert summary["G-B"]["open_alert_level"] == "red" and summary["G-B"]["open_alerts"] == 1
    assert summary["G-A"]["open_alert_level"] == "amber" and summary["G-C"]["open_alert_level"] is None

    ack = client.post(f"/alerts/{top['id']}/ack", json={"actor": "dr.surgeon", "note": "bog'landim"})
    assert ack.status_code == 200 and ack.json()["acknowledged"] is True and ack.json()["ack_by"] == "dr.surgeon"
    assert client.post(f"/alerts/{top['id']}/ack", json={"actor": "dr.other"}).status_code == 409   # ikki marta emas
    assert client.post("/alerts/99999/ack", json={"actor": "dr"}).status_code == 404
    assert client.post(f"/alerts/{top['id']}/ack", json={"actor": ""}).status_code == 422

    assert [x["level"] for x in client.get("/alerts").json()["items"]] == ["amber"]
    assert client.get("/alerts", params={"status": "acknowledged"}).json()["total"] == 1
    assert client.get("/alerts", params={"status": "all"}).json()["total"] == 2
    summary = {i["patient_ref"]: i for i in client.get("/episodes").json()["items"]}
    assert summary["G-B"]["open_alert_level"] is None and summary["G-B"]["open_alerts"] == 0
    assert any(x["action"] == "alert.ack" and x["detail"]["note"] == "bog'landim" for x in client.get(f"/episodes/{b}/audit").json())


def test_digest_lists_only_open_alerts_and_episode_alerts_endpoint(env):
    client, _ = env
    eid = guardian_episode(client)
    checkin(client, eid, wound_signs=["dehiscence"])
    aid = client.get(f"/episodes/{eid}/digest").json()["open_alerts"][0]["id"]
    assert client.get(f"/episodes/{eid}/alerts").json()["total"] == 1
    client.post(f"/alerts/{aid}/ack", json={"actor": "dr"})
    assert client.get(f"/episodes/{eid}/digest").json()["open_alerts"] == []
    assert client.get(f"/episodes/{eid}/alerts", params={"status": "open"}).json()["total"] == 0
    assert client.get("/episodes/nope/alerts").status_code == 404


def test_red_before_amber_even_if_older_and_pagination(env):
    client, _ = env
    amber = [guardian_episode(client, f"AM-{i}") for i in range(3)]
    for e in amber:
        checkin(client, e, heart_rate=110)
    red = guardian_episode(client, "RED-LATE")
    checkin(client, red, wound_signs=["dehiscence"])
    items = client.get("/alerts").json()["items"]
    assert items[0]["patient_ref"] == "RED-LATE"
    page = client.get("/alerts", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2
