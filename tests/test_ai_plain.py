import re

import pytest

from api.ai_plain import T, plain_ai
from core.evidence import Evidence, Provenance, RiskLevel, Source

P = Provenance(name="t")
LANGS = ("uz", "ru", "en")
TECH = re.compile(r"abstain|\becg\.[a-z]|p=|AFIB|ONNX|Evidence|\bangio\.[a-z]|\becho\.[a-z]", re.IGNORECASE)


def ev(kind, risk, value=None, abstained=False, reason="x"):
    return Evidence(kind=kind, value=value, source=Source.MODEL, provenance=P, risk=risk, abstained=abstained,
                    explanation=[reason])


CASES = [
    ev("ecg.afib", RiskLevel.HIGH, {"p_afib": 0.9}),
    ev("ecg.afib", RiskLevel.MODERATE, {"other_codes": ["MI", "CD"]}),
    ev("ecg.afib", RiskLevel.LOW, {}),
    ev("ecg.afib", RiskLevel.UNKNOWN, abstained=True, reason="sifatsiz EKG: x"),
    ev("ecg.afib", RiskLevel.UNKNOWN, abstained=True, reason="yosh 9: model"),
    ev("angio.stenosis_assist", RiskLevel.MODERATE, {"n_candidates": 2}),
    ev("angio.stenosis_assist", RiskLevel.UNKNOWN, {"n_candidates": 0}),
    ev("angio.stenosis_assist", RiskLevel.UNKNOWN, abstained=True, reason="kadr yaroqsiz: x"),
    ev("guardian.inr", RiskLevel.LOW, 2.6),
    ev("guardian.inr", RiskLevel.MODERATE, 3.9),
    ev("guardian.inr", RiskLevel.VERY_HIGH, 8.4),
    ev("guardian.inr", RiskLevel.UNKNOWN, abstained=True),
    ev("echo.ef", RiskLevel.LOW, 60.0),
    ev("echo.ef", RiskLevel.VERY_HIGH, 22.0),
    ev("echo.ef", RiskLevel.UNKNOWN, abstained=True, reason="yosh 7"),
    ev("echo.ef", RiskLevel.UNKNOWN, abstained=True, reason="video o'qilmadi"),
]


@pytest.mark.parametrize("e", CASES)
def test_all_languages_complete_and_free_of_jargon(e):
    seen = set()
    for lang in LANGS:
        p = plain_ai(e, lang)
        assert p["lang"] == lang and p["level"] in ("red", "yellow", "green", "grey")
        assert p["headline"] and p["todo"] and p["items"] and not TECH.search(" ".join([p["headline"], p["todo"], p["items"][0]["text"]]))
        seen.add(p["headline"])
    assert len(seen) == 3                       # har til o'z matniga ega


def test_translation_tables_have_all_languages():
    assert all(set(v) == set(LANGS) for v in T.values())


def test_levels_and_unknown_lang_default():
    assert plain_ai(CASES[0], "en")["level"] == "red"
    assert plain_ai(CASES[6], "uz")["level"] == "grey"            # nomzod yo'q — tinchlantirmaydi
    assert plain_ai(CASES[3], "xx")["lang"] == "uz"
    assert "Dozani" in plain_ai(CASES[10], "uz")["todo"] and "o'zingiz o'zgartirmang" in plain_ai(CASES[10], "uz")["todo"]


def test_inr_unread_is_amber_level_for_patient():
    assert plain_ai(CASES[11], "ru")["level"] == "yellow"
