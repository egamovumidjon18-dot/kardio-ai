import pytest

from core.concordance import Agreement, compare
from core.episode import Episode, Stage, TransitionError
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.handoff import Handoff
from core.registry import LicenseError, ModelCard, check_license
from core.store import SqliteEpisodeStore


def ev(risk, source=Source.RULE, abstained=False):
    return Evidence(kind="x", value=1, source=source, provenance=Provenance(name="t"),
                    risk=risk, abstained=abstained)


# ---- Episode holat mashinasi
def test_valid_path_to_guardian_and_close():
    ep = Episode(patient_ref="P1")
    path = ["workup", "heart_team", "procedure", "icu", "discharge", "guardian_30d", "closed"]
    for nxt in path:
        ep.transition(Handoff(from_stage=ep.stage.value, to_stage=nxt, author="dr"))
    assert ep.stage == Stage.CLOSED and len(ep.handoffs) == len(path)


@pytest.mark.parametrize("frm,to", [("screening", "procedure"), ("procedure", "closed"), ("closed", "workup")])
def test_invalid_transitions_rejected(frm, to):
    ep = Episode(patient_ref="P1", stage=Stage(frm))
    with pytest.raises(TransitionError):
        ep.transition(Handoff(from_stage=frm, to_stage=to, author="dr"))
    assert ep.stage == Stage(frm)


def test_transition_stage_mismatch_and_unknown_evidence():
    ep = Episode(patient_ref="P1")
    with pytest.raises(TransitionError):
        ep.transition(Handoff(from_stage="workup", to_stage="heart_team", author="dr"))
    with pytest.raises(TransitionError):
        ep.transition(Handoff(from_stage="screening", to_stage="workup", author="dr", evidence_ids=["nope"]))
    with pytest.raises(TransitionError):
        ep.transition(Handoff(from_stage="screening", to_stage="mars", author="dr"))


# ---- Concordance
def test_concordance_four_states():
    rule = ev(RiskLevel.MODERATE)
    assert compare("q", rule, None).status == Agreement.RULE_ONLY
    assert compare("q", rule, ev(RiskLevel.UNKNOWN, Source.MODEL, abstained=True)).status == Agreement.AI_ABSTAINED
    assert compare("q", rule, ev(RiskLevel.MODERATE, Source.MODEL)).status == Agreement.AGREE
    assert compare("q", rule, ev(RiskLevel.HIGH, Source.MODEL)).status == Agreement.DISAGREE
    assert compare("q", rule, ev(RiskLevel.HIGH, Source.MODEL), tolerance=1).status == Agreement.AGREE


def test_ai_never_downgrades_rule():
    r = compare("q", ev(RiskLevel.HIGH), ev(RiskLevel.LOW, Source.MODEL))
    assert r.status == Agreement.DISAGREE and r.final_risk == RiskLevel.HIGH and r.needs_discussion
    up = compare("q", ev(RiskLevel.LOW), ev(RiskLevel.HIGH, Source.MODEL))
    assert up.final_risk == RiskLevel.HIGH


def test_abstained_ai_keeps_rule_risk():
    r = compare("q", ev(RiskLevel.LOW), ev(RiskLevel.HIGH, Source.MODEL, abstained=True))
    assert r.status == Agreement.AI_ABSTAINED and r.final_risk == RiskLevel.LOW


# ---- Saqlash
def test_store_roundtrip_and_audit(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "t.db"))
    ep = Episode(patient_ref="P9")
    e = ep.add(ev(RiskLevel.HIGH))
    store.save(ep, "dr.a", "create")
    ep.transition(Handoff(from_stage="screening", to_stage="workup", author="dr.a", evidence_ids=[e.id]))
    store.save(ep, "dr.a", "transition", {"to": "workup"})
    back = store.get(ep.id)
    assert back.stage == Stage.WORKUP and back.evidence[0].risk == RiskLevel.HIGH
    assert back.handoffs[0].evidence_ids == [e.id]
    assert [a["action"] for a in store.audit(ep.id)] == ["create", "transition"]
    assert store.get("missing") is None


# ---- Litsenziya
def test_product_mode_blocks_research_only_dataset(monkeypatch):
    research = ModelCard(name="ef", version="1", task="ef", dataset="EchoNet-Dynamic", weights="x.onnx")
    open_card = ModelCard(name="pcg", version="1", task="pcg", dataset="CirCor DigiScope", weights="x.onnx")
    monkeypatch.setenv("CARDIOPATH_MODE", "product")
    with pytest.raises(LicenseError):
        check_license(research)
    check_license(open_card)
    monkeypatch.setenv("CARDIOPATH_MODE", "research")
    check_license(research)
