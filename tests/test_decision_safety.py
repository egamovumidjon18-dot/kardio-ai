"""Regression cases where incomplete or invalid evidence must not look reassuring."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
import pytest

from core.evidence import Evidence
from core.measurements import measurement_time
from tests.test_ecg import fake_ecg, model as ecg_model
from tests.test_low_ef import model as lowef_model
from tests.test_shd import model as shd_model
from tests.test_screening import CARD, const_backend
from screening.model import PCGModel, Recording
from tests.test_risk import aki_in, base
from risk.aki import thakar
from risk.euroscore2 import euroscore2
from learning.dataset import split_children, usable
from tests.test_integration import (env, heart_team_episode, risk, inject, echo_ef, ES, AKI,
                                    guardian_episode, checkin)


@pytest.mark.parametrize("age", [None, float("nan"), float("inf"), -1, 121, 8])
def test_ecg_models_require_an_eligible_known_age(age):
    for model in [ecg_model([.01, .9, .1, .1, .1, .1]), lowef_model(.01), shd_model(.01, .01, .01, .01)]:
        model.backend = lambda x: pytest.fail("ineligible input reached inference")
        assert model.analyze(fake_ecg(), 500, age_years=age).abstained


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -.1, 1.1])
def test_invalid_probabilities_never_become_low_risk(value, wav_factory):
    models = [ecg_model([value, .9, .1, .1, .1, .1]), lowef_model(value), shd_model(value, .01, .01, .01)]
    for model in models:
        ev = model.analyze(fake_ecg(), 500, age_years=60)
        assert ev.abstained and ev.risk.value == "unknown"
        json.dumps(ev.to_dict(), allow_nan=False)
    ev = PCGModel(CARD, const_backend(value)).analyze([Recording("MV", wav_factory())], age_days=900)
    assert ev.abstained
    json.dumps(ev.to_dict(), allow_nan=False)


def test_wrong_output_shape_abstains():
    model = ecg_model([.1])
    assert model.analyze(fake_ecg(), 500, age_years=60).abstained


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, 101])
def test_invalid_lvef_never_generates_a_score(value):
    assert euroscore2(base(lvef_percent=value)).abstained
    assert thakar(aki_in(lvef_percent=value)).abstained


def test_corrected_risk_assumptions_disappear(env):
    client, _ = env
    eid = heart_team_episode(client)
    response = client.post(f"/episodes/{eid}/risk", json={"actor": "dr", "euroscore":
                           dict(age=60, female=False, weight_kg=80, creatinine_umol_l=90), "aki": AKI})
    assert response.status_code == 200
    assert risk(client, eid).status_code == 200
    digest = client.get(f"/episodes/{eid}/digest").json()
    assert not any(d["code"] == "assumed_defaults" for d in digest["discussion"])
    assert digest["latest"]["risk.assumptions"]["value"] == []


def test_invalid_or_conflicting_risk_is_not_saved(env):
    client, store = env
    eid = heart_team_episode(client)
    before = len(store.get(eid).evidence)
    for changes in [{"lvef_percent": 150}, {"female": True}, {"creatinine_umol_l": 100}]:
        response = client.post(f"/episodes/{eid}/risk", json={"actor": "dr", "euroscore": ES, "aki": {**AKI, **changes}})
        assert response.status_code == 422
        assert len(store.get(eid).evidence) == before


def test_measurement_date_not_upload_date_controls_comparison(env):
    client, store = env
    eid = heart_team_episode(client)
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    response = client.post(f"/episodes/{eid}/risk", json={"actor": "dr", "euroscore": ES, "aki": AKI,
                                                       "lvef_measured_at": old})
    assert response.status_code == 200
    inject(store, eid, echo_ef(25))
    result = client.get(f"/episodes/{eid}/digest").json()
    ef = next(c for c in result["concordance"] if c["question"].startswith("LVEF"))
    assert ef["status"] == "not_comparable" and "90 kun" in ef["message"]
    saved = store.get(eid).latest("clinician.lvef")
    assert saved.measured_at == old and saved.created_at != old


def test_missing_measurement_date_is_not_assumed_today(env):
    client, store = env
    eid = heart_team_episode(client)
    client.post(f"/episodes/{eid}/risk", json={"actor": "dr", "euroscore": ES, "aki": AKI})
    inject(store, eid, echo_ef(25))
    ef = next(c for c in client.get(f"/episodes/{eid}/digest").json()["concordance"] if c["question"].startswith("LVEF"))
    assert ef["status"] == "not_comparable"
    assert "noma'lum" in ef["message"]


def test_measurement_time_rejects_future_and_naive_dates():
    for dt in [datetime.now(), datetime.now(timezone.utc) + timedelta(days=1)]:
        with pytest.raises(ValueError):
            measurement_time(dt)


def test_old_evidence_still_deserializes(env):
    _, store = env
    ev = echo_ef(55).to_dict()
    ev.pop("measured_at")
    assert Evidence.from_dict(ev).measured_at is None


def test_backdated_weight_preserves_submitted_value(env):
    client, store = env
    eid = guardian_episode(client)
    now = datetime.now(timezone.utc)
    assert checkin(client, eid, weight_kg=80, measured_at=now.isoformat()).status_code == 200
    old = (now - timedelta(days=1)).isoformat()
    assert checkin(client, eid, weight_kg=75, measured_at=old).status_code == 200
    ev = store.get(eid).latest("guardian.weight")
    assert ev.value == 75 and ev.created_at == old


def test_same_patient_never_crosses_learning_partitions():
    children = [{"eid": str(i), "patient_key": "same-patient", "age_days": 900, "dx": "VSD"} for i in range(100)]
    split = split_children(children)
    assert sorted(len(rows) for rows in split.values()) == [0, 0, 100]
    assert usable([{**children[0], "age_days": None}]) == []
    assert usable([{k: v for k, v in children[0].items() if k != "patient_key"}]) == []


def test_rounding_does_not_turn_uncertain_predictions_into_decisions(wav_factory):
    assert ecg_model([.69999, .1, .1, .1, .1, .1]).analyze(fake_ecg(), 500, age_years=60).abstained
    assert lowef_model(.59999).analyze(fake_ecg(), 500, age_years=60).abstained
    assert shd_model(.59999, .1, .1, .1).analyze(fake_ecg(), 500, age_years=60).abstained
    assert PCGModel(CARD, const_backend(.69999)).analyze([Recording("MV", wav_factory())], age_days=900).abstained


def test_documented_age_band_must_be_entirely_eligible(wav_factory):
    model = PCGModel(CARD, const_backend(.1))
    recs = [Recording("MV", wav_factory())]
    assert not model.analyze(recs, age_range_days=(365, 12 * 366)).abstained
    assert model.analyze(recs, age_range_days=(28, 365)).abstained
    assert model.analyze(recs, age_range_days=(1000, 100)).abstained


def test_api_rejects_population_mismatch_and_abstains_without_age(tmp_path):
    from tests.test_ai_api import make_client, ecg_csv
    client = make_client(tmp_path)
    eid = client.post("/episodes", json={"patient_ref": "CHILD", "population": "pediatric"}).json()["id"]
    files = {"file": ("e.csv", ecg_csv(), "text/csv")}
    assert client.post(f"/episodes/{eid}/ecg", data={"actor": "dr", "fs": "100", "age_years": "60"}, files=files).status_code == 422
    response = client.post(f"/episodes/{eid}/ecg", data={"actor": "dr", "fs": "100"}, files=files)
    assert response.status_code == 200 and response.json()["evidence"]["abstained"]


def test_collection_deduplicates_patient_visits(tmp_path):
    from core.store import SqliteEpisodeStore
    from core.episode import Episode
    from screening.collection import save_recordings, echo_diagnosis
    from research.export_local import collect_children
    store = SqliteEpisodeStore(str(tmp_path / "clinic.db"))
    recordings = tmp_path / "recordings"
    for ref in ["P-001", " p-001 "]:
        ep = Episode(patient_ref=ref)
        ep.add(save_recordings(recordings, ep.id, [("MV", b"fixture")], 900, "S1"))
        ep.add(echo_diagnosis("NORMAL"))
        store.save(ep, "dr", "fixture")
    children, skipped = collect_children(store, recordings)
    assert len(children) == 1 and skipped["takroriy bemor epizodi"] == 1


def test_old_local_model_cannot_train_on_changed_split(tmp_path):
    from learning.versions import ModelVersions
    from learning.cycle import run_cycle
    from core.store import SqliteEpisodeStore
    versions = ModelVersions(tmp_path / "models")
    version = versions.add_candidate({}, {"gates": {"passed": True}})
    versions.promote(version, "Dr.Test")
    store = SqliteEpisodeStore(str(tmp_path / "empty.db"))
    result = run_cycle(store, tmp_path / "rec", versions, tmp_path, object())
    assert result["status"] == "split_migration_required"


@pytest.mark.parametrize("kind", ["pcg", "ecg", "angio"])
def test_installed_onnx_models_produce_serializable_evidence(kind, wav_factory):
    if not (Path("weights") / kind / "model_card.json").exists():
        pytest.skip("installed model weights unavailable")
    if kind == "pcg":
        ev = PCGModel.from_dir("weights/pcg").analyze([Recording("MV", wav_factory())], age_days=900)
    elif kind == "ecg":
        from ecg.model import ECGModel
        ev = ECGModel.from_dir("weights/ecg").analyze(fake_ecg(), 500, age_years=60)
    else:
        from angio.model import AngioModel
        from tests.test_angio import fake_frame
        ev = AngioModel.from_dir("weights/angio").analyze(fake_frame())
    # This verifies execution and output validity, not diagnostic accuracy.
    json.dumps(ev.to_dict(), allow_nan=False)
    assert ev.provenance.name and (not ev.abstained or ev.risk.value == "unknown")
