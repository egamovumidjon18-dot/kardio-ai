"""Koronar tomir shoxlari va chap asosiy poya (LMS) xavf eskalatsiyasi testlari (ESC/EACTS)."""
from fastapi.testclient import TestClient

from angio.model import AngioModel
from angio.vessels import CoronaryLesion, assess_coronary_anatomy
from api.main import create_app
from core.evidence import RiskLevel
from core.registry import ModelCard
from core.store import SqliteEpisodeStore
from tests.test_angio import blob_backend, fake_frame, png

CARD = ModelCard(name="angio_test", version="0", task="t", dataset="ARCADE", weights="none",
                 thresholds={"prob": 0.5, "min_area_px": 20})


def test_assess_coronary_anatomy_lms_critical():
    lesions = [
        CoronaryLesion(vessel="LMS", stenosis_percent=65.0, is_bifurcation=True),
    ]
    ev = assess_coronary_anatomy(lesions, ai_candidate_count=1)
    assert ev.kind == "angio.anatomy"
    assert ev.risk == RiskLevel.VERY_HIGH
    assert ev.value["lms_involved"] is True
    assert any("LMS" in exp and "CABG" in exp for exp in ev.explanation)


def test_assess_coronary_anatomy_proximal_lad():
    lesions = [
        CoronaryLesion(vessel="LAD_PROX", stenosis_percent=80.0),
    ]
    ev = assess_coronary_anatomy(lesions, ai_candidate_count=1)
    assert ev.risk == RiskLevel.HIGH
    assert any("Proksimal LAD" in exp for exp in ev.explanation)


def test_assess_coronary_anatomy_multivessel_three_vessels():
    lesions = [
        CoronaryLesion(vessel="LAD_MID_DIST", stenosis_percent=75.0),
        CoronaryLesion(vessel="LCX", stenosis_percent=70.0),
        CoronaryLesion(vessel="RCA", stenosis_percent=85.0),
    ]
    ev = assess_coronary_anatomy(lesions, ai_candidate_count=3)
    assert ev.risk == RiskLevel.VERY_HIGH
    assert any("3 tomirli" in exp for exp in ev.explanation)


def test_assess_coronary_anatomy_mild():
    lesions = [
        CoronaryLesion(vessel="RCA", stenosis_percent=55.0),
    ]
    ev = assess_coronary_anatomy(lesions, ai_candidate_count=0)
    assert ev.risk == RiskLevel.LOW


def test_angio_endpoint_with_vessel_parameters(tmp_path):
    db_path = str(tmp_path / "angio_vessels_test.db")
    store = SqliteEpisodeStore(db_path)
    model = AngioModel(CARD, blob_backend([(150, 150, 15)]))
    client = TestClient(create_app(store, None, angio_model=model))

    # Epizod ochish va WORKUP bosqichiga o'tkazish
    r = client.post("/episodes", json={"patient_ref": "P-ANGIO-01", "population": "adult", "actor": "dr1"})
    assert r.status_code == 201
    eid = r.json()["id"]
    client.post(f"/episodes/{eid}/transition", json={"from_stage": "screening", "to_stage": "workup", "author": "dr1"})

    # LMS stenoz bilan angiografiya yuborish
    frame_bytes = png(fake_frame())
    r_angio = client.post(
        f"/episodes/{eid}/angio",
        data={
            "actor": "dr_cath",
            "lang": "uz",
            "vessel_segment": "LMS",
            "stenosis_percent": "70",
            "is_bifurcation": "true",
        },
        files={"file": ("frame.png", frame_bytes, "image/png")},
    )
    assert r_angio.status_code == 200
    res = r_angio.json()
    assert res["anatomy"] is not None
    assert res["anatomy"]["risk"] == RiskLevel.VERY_HIGH.value
    assert res["anatomy"]["value"]["lms_involved"] is True
