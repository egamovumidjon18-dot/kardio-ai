"""ExoKG klapanlar gemodinamikasi (AS, MR, AR, sPAP) testlari."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode, Stage
from core.evidence import RiskLevel
from core.store import SqliteEpisodeStore
from echo.valves import ValvularEchoInput, evaluate_valvular_echo


def test_severe_aortic_stenosis():
    inp = ValvularEchoInput(as_vmax=4.3, as_mean_gradient=46.0, as_ava=0.75)
    ev = evaluate_valvular_echo(inp)
    assert not ev.abstained
    assert ev.risk == RiskLevel.VERY_HIGH
    assert ev.value["aortic_stenosis"]["grade"] == "severe"
    assert ev.value["aortic_stenosis"]["severe"] is True
    assert "SAVR yoki TAVI" in "; ".join(ev.explanation)


def test_low_flow_low_gradient_as():
    # AVA <= 1.0, mean grad < 40, EF < 50%
    inp = ValvularEchoInput(as_vmax=3.4, as_mean_gradient=28.0, as_ava=0.70, lvef=35.0)
    ev = evaluate_valvular_echo(inp)
    assert not ev.abstained
    assert ev.risk == RiskLevel.VERY_HIGH
    assert ev.value["aortic_stenosis"]["grade"] == "severe_lflg"
    assert "LFLG-AS" in "; ".join(ev.explanation)


def test_severe_mitral_regurgitation():
    inp_primary = ValvularEchoInput(mr_eroa=45.0, mr_reg_vol=65.0, mr_etiology="primary")
    ev1 = evaluate_valvular_echo(inp_primary)
    assert ev1.risk == RiskLevel.VERY_HIGH
    assert ev1.value["mitral_regurgitation"]["grade"] == "severe"

    inp_secondary = ValvularEchoInput(mr_eroa=25.0, mr_reg_vol=35.0, mr_etiology="secondary")
    ev2 = evaluate_valvular_echo(inp_secondary)
    assert ev2.risk == RiskLevel.VERY_HIGH
    assert ev2.value["mitral_regurgitation"]["grade"] == "severe"


def test_severe_pulmonary_hypertension():
    # sPAP = 4 * (3.6)^2 + 10 = 51.84 + 10 = 61.8 mmHg (> 50 -> severe)
    inp = ValvularEchoInput(tr_vmax=3.6, rap=10.0)
    ev = evaluate_valvular_echo(inp)
    assert not ev.abstained
    assert ev.risk == RiskLevel.VERY_HIGH
    assert ev.value["pulmonary_hypertension"]["spap_mmhg"] == 61.8
    assert ev.value["pulmonary_hypertension"]["severe"] is True
    assert "EuroSCORE II" in "; ".join(ev.explanation)


def test_normal_valves():
    inp = ValvularEchoInput(as_vmax=1.3, tr_vmax=2.0, rap=5.0)
    ev = evaluate_valvular_echo(inp)
    assert not ev.abstained
    assert ev.risk == RiskLevel.LOW
    assert ev.value["aortic_stenosis"]["grade"] == "none"
    assert ev.value["pulmonary_hypertension"]["spap_mmhg"] == 21.0


def test_plausibility_abstain():
    inp = ValvularEchoInput(as_vmax=20.0)  # Fiziologik imkonsiz
    ev = evaluate_valvular_echo(inp)
    assert ev.abstained
    assert "biologik oraliqdan tashqarida" in "; ".join(ev.explanation)


def test_echo_valves_api(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "test_valves.db"))
    app = create_app(store=store, pcg=None, auth=False)
    client = TestClient(app)

    res_ep = client.post("/episodes", json={"patient_ref": "PAT-VALVE-01", "actor": "doctor"})
    assert res_ep.status_code == 201
    eid = res_ep.json()["id"]

    res = client.post(f"/episodes/{eid}/echo/valves", json={
        "actor": "dr_cardiologist",
        "as_vmax": 4.2,
        "as_mean_gradient": 45.0,
        "as_ava": 0.85,
        "tr_vmax": 3.4,
        "rap": 5.0,
        "lvef": 52.0
    })
    assert res.status_code == 200
    data = res.json()
    assert "evidence" in data
    assert data["evidence"]["kind"] == "echo.valves"
    assert data["evidence"]["risk"] == "very_high"

    reloaded = store.get(eid)
    assert reloaded.latest("echo.valves") is not None
