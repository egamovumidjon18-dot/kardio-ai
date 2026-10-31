import pytest

from core.evidence import RiskLevel
from guardian.checkin import vitals_and_symptoms, weight_trend, wound
from guardian.escalation import Alert, LogNotifier, escalate
from guardian.inr import assess_inr, parse_inr_text


@pytest.mark.parametrize("text,expected", [
    ("Protrombin vaqti 18 s\nMNO: 2,7\nFibrinogen 3.1", 2.7),
    ("INR = 3.1", 3.1),
    ("МНО 1,9", 1.9),
    ("MHO 2.4", 2.4),                      # OCR kirillni lotin deb o'qigan
    ("Fibrinogen 3.1", None),
    ("INR 2.1 ... INR 3.4", None),         # ikki xil qiymat → noaniq
])
def test_parse_inr_text(text, expected):
    assert parse_inr_text(text) == expected


@pytest.mark.parametrize("value,indication,risk", [
    (3.0, "mechanical_mitral", RiskLevel.LOW),
    (2.2, "mechanical_mitral", RiskLevel.MODERATE),
    (1.6, "mechanical_mitral", RiskLevel.HIGH),      # < 2.5 - 0.5 → tromboz xavfi
    (1.6, "af", RiskLevel.MODERATE),                 # mexanik emas
    (2.4, "mechanical_aortic", RiskLevel.LOW),
    (5.5, "mechanical_aortic", RiskLevel.HIGH),
    (8.5, "mechanical_aortic", RiskLevel.VERY_HIGH),
])
def test_inr_targets(value, indication, risk):
    assert assess_inr(value, indication).risk == risk


def test_inr_abstains_on_unreadable_or_implausible():
    assert assess_inr(None, "af").abstained
    assert assess_inr(27.0, "af").abstained


def test_weight_trend():
    assert weight_trend([("2026-11-01T08:00:00+00:00", 70.0), ("2026-11-03T08:00:00+00:00", 72.3)]).risk == RiskLevel.HIGH
    assert weight_trend([("2026-11-01T08:00:00+00:00", 70.0), ("2026-11-02T08:00:00+00:00", 71.1)]).risk == RiskLevel.MODERATE
    assert weight_trend([("2026-11-01T08:00:00+00:00", 70.0), ("2026-11-08T08:00:00+00:00", 72.5)]).risk == RiskLevel.LOW
    assert weight_trend([("2026-11-01T08:00:00+00:00", 70.0)]).risk == RiskLevel.LOW


def test_vitals_and_wound_rules():
    assert vitals_and_symptoms(130, 97, None, []).risk == RiskLevel.HIGH
    assert vitals_and_symptoms(80, 92, None, []).risk == RiskLevel.MODERATE
    assert vitals_and_symptoms(80, 97, 36.6, []).risk == RiskLevel.LOW
    assert vitals_and_symptoms(80, 97, None, ["orthopnea"]).risk == RiskLevel.HIGH
    assert vitals_and_symptoms(None, None, None, ["bogus"]).abstained
    assert wound(["purulent_discharge"]).risk == RiskLevel.HIGH
    assert wound(["spreading_redness"]).risk == RiskLevel.MODERATE
    assert wound(["spreading_redness"], fever=True).risk == RiskLevel.HIGH
    assert wound([], photo_ref="img-1").risk == RiskLevel.LOW


def test_escalation_levels_and_privacy():
    n = LogNotifier()
    assert escalate("PSV-1", 4, [wound([])], n).alert == Alert.GREEN and n.sent == []
    esc = escalate("PSV-1", 4, [assess_inr(1.4, "mechanical_mitral")], n)
    assert esc.alert == Alert.RED and esc.notified and "103" in esc.patient_message
    assert "PSV-1" in n.sent[-1] and "4-kun" in n.sent[-1]
    assert escalate("PSV-1", 5, [assess_inr(None, "af")], n).alert == Alert.AMBER   # o'qilmagan → inson ko'rigi
    assert "doza" not in " ".join(e.patient_message for e in [esc])                   # bemorga doza aytilmaydi


def test_unsure_answer_is_not_treated_as_no():
    from guardian.checkin import vitals_and_symptoms, wound
    from core.evidence import RiskLevel
    ev = vitals_and_symptoms(None, None, None, [], unsure=["syncope"])
    assert ev.risk == RiskLevel.MODERATE and any("aniq emas" in x for x in ev.explanation)
    assert vitals_and_symptoms(None, None, None, [], unsure=["palpitations"]).risk != RiskLevel.HIGH
    assert wound([], unsure=["dehiscence"]).risk == RiskLevel.MODERATE
    assert wound([], unsure=[]).risk == RiskLevel.LOW
    assert vitals_and_symptoms(None, None, None, ["syncope"], unsure=["syncope"]).risk == RiskLevel.HIGH   # «ha» ustun


def test_guardian_page_is_served_and_safe(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app
    from core.store import SqliteEpisodeStore
    html = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "g.db")), None)).get("/guardian").text
    assert "tel:103" in html and "unsure_symptoms" in html and "guardian/checkin" in html
    texts = html[html.index("const T = {"):html.index("let lang")]      # bemorga ko'rinadigan matnlar
    assert "AI" not in texts and "ИИ" not in texts and "tashxis" not in texts       # AI so'zi va tashxis yo'q
