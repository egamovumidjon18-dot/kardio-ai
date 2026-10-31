"""RACHS-1: toifalar, yoshga bog'liq qoidalar, eng yuqori toifa qoidasi, istisnolar, API va protokol."""
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.evidence import RiskLevel
from core.store import SqliteEpisodeStore
from risk.rachs1 import MORTALITY_2002, PROCEDURES, Rachs1Input, rachs1


def cat(procs, age=200, **kw):
    return rachs1(Rachs1Input(procedures=procs, age_days=age, **kw))


@pytest.mark.parametrize("procs,age,expected", [
    (["asd_repair"], 1000, 1), (["vsd_repair"], 200, 2), (["tof_repair"], 200, 2), (["glenn"], 150, 2),
    (["fontan"], 1500, 3), (["arterial_switch"], 7, 3), (["avsd_repair"], 150, 3),
    (["truncus_repair"], 10, 4), (["truncus_iaa_repair"], 10, 5), (["norwood"], 5, 6),
])
def test_known_categories(procs, age, expected):
    e = cat(procs, age)
    assert not e.abstained and e.value == expected and e.provenance.name == "rachs1"


def test_age_dependent_procedures():
    assert cat(["coarctation_repair"], 10).value == 2 and cat(["coarctation_repair"], 60).value == 1
    assert cat(["aortic_valvotomy"], 20).value == 4 and cat(["aortic_valvotomy"], 400).value == 2
    assert cat(["tapvc_repair"], 30).value == 4 and cat(["tapvc_repair"], 31).value == 2      # chegara: ≤ 30 kun
    assert cat(["ebstein_repositioning"], 3).value == 5 and cat(["ebstein_repositioning"], 3000).value == 3


def test_multiple_procedures_take_highest_category():
    e = cat(["vsd_repair", "arterial_switch"], 10)
    assert e.value == 3 and any("eng yuqori toifa" in x for x in e.explanation)


def test_risk_levels_and_mortality_wording():
    assert cat(["asd_repair"]).risk == RiskLevel.LOW and cat(["vsd_repair"]).risk == RiskLevel.MODERATE
    assert cat(["fontan"], 1500).risk == RiskLevel.HIGH and cat(["norwood"], 5).risk == RiskLevel.VERY_HIGH
    e = cat(["norwood"], 5)
    assert "47.7%" in e.explanation[-1] and "shaxsiy xavfi emas" in e.explanation[-1]
    assert "baholanmagan" in cat(["truncus_iaa_repair"], 10).explanation[-1]          # 5-toifa: holat kam
    assert MORTALITY_2002[5] is None


@pytest.mark.parametrize("procs,age,kw,why", [
    ([], 100, {}, "ko'rsatilmagan"),
    (["xyz"], 100, {}, "ro'yxatda yo'q"),
    (["heart_transplant"], 100, {}, "ko'chirib"),
    (["pda_closure"], 10, {"premature": True}, "chala"),
    (["pda_closure"], 10, {}, "toifa berilmagan"),
    (["vsd_repair"], 20 * 365, {}, "EuroSCORE"),
])
def test_abstain_cases(procs, age, kw, why):
    e = cat(procs, age, **kw)
    assert e.abstained and why in " ".join(e.explanation)


def test_every_procedure_has_valid_categories():
    for code, (name, neo, older) in PROCEDURES.items():
        assert name and older in range(1, 7) and (neo is None or neo in range(1, 7)), code


def test_api_and_protocol(tmp_path):
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "a.db")), None))
    eid = c.post("/episodes", json={"patient_ref": "R-1", "actor": "dr", "population": "pediatric"}).json()["id"]
    assert c.post(f"/episodes/{eid}/rachs1", json={"actor": "dr", "procedures": ["norwood"], "age_days": 5}).status_code == 409
    for f, t in [("screening", "workup"), ("workup", "heart_team")]:
        assert c.post(f"/episodes/{eid}/transition", json={"from_stage": f, "to_stage": t, "author": "dr"}).status_code == 200
    items = c.get("/rachs1/procedures").json()["items"]
    assert any(i["code"] == "norwood" and i["category_gt30d"] == 6 for i in items)
    r = c.post(f"/episodes/{eid}/rachs1", json={"actor": "dr", "procedures": ["norwood"], "age_days": 5})
    assert r.status_code == 200 and r.json()["evidence"]["value"] == 6
    assert c.post(f"/episodes/{eid}/rachs1", json={"actor": "dr", "procedures": [], "age_days": 5}).status_code == 422
    proto = c.get(f"/episodes/{eid}/heart-team-protocol").text
    assert "RACHS-1" in proto and "| 6 -toifa (1–6) |" in proto
