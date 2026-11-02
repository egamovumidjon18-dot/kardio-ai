"""Oddiy tildagi xulosa: shifokor ko'radigan matn to'g'ri va texnik kodlarsiz bo'lishi kerak."""
import re

import numpy as np
import pytest

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard
from screening.model import PCGModel, Recording
from screening.plain import plain_report
from screening.rules import newborn_pulse_ox, red_flags, resting_spo2
from screening.triage import triage

CARD = ModelCard(name="t", version="0", task="t", dataset="CirCor DigiScope", weights="none")
TECH = re.compile(r"screening\.|abstain|concordance|moderate|very_high|\bp=|PASS|FAIL|REPEAT")


def report(rules, pcg=None, uploaded=0, ready=True):
    return plain_report(triage(rules, pcg), rules, pcg, uploaded, ready)


def no_tech(r):
    text = " ".join([r["headline"], r["todo"], r["attention"] or ""] + [i["text"] for i in r["items"]])
    assert not TECH.search(text), text


def test_fail_is_red_and_urgent():
    r = report([newborn_pulse_ox(85, 95), red_flags([])])
    assert r["level"] == "red" and "Kritik" in r["headline"] and "uyga javob bermang" in r["todo"]
    assert r["items"][0]["level"] == "red" and "85%" in r["items"][0]["text"]
    no_tech(r)


def test_repeat_asks_to_measure_again():
    r = report([newborn_pulse_ox(93, 93), red_flags([])])
    assert r["level"] == "yellow" and "qayta o'lchash" in r["headline"] and "Urinish: 2" in r["todo"]
    no_tech(r)


def test_normal_is_green_with_plain_items():
    r = report([resting_spo2(98), red_flags([])])
    assert r["level"] == "green" and r["attention"] is None
    assert [i["title"] for i in r["items"]] == ["SpO₂ (tinch holatda)", "Klinik belgilar", "Yurak tovushi (AI)"]
    assert r["items"][2]["text"] == "Yozuv yuklanmagan."
    no_tech(r)


def test_flags_listed_by_name():
    r = report([red_flags(["cyanosis", "recurrent_pneumonia"])])
    assert "markaziy sianoz (jiddiy)" in r["items"][0]["text"] and r["level"] == "red"


def test_ai_murmur_and_disagreement(wav_factory):
    pcg = PCGModel(CARD, lambda x: (np.full(len(x), 0.95, np.float32), np.zeros(len(x), np.float32))) \
        .analyze([Recording("MV", wav_factory())], age_days=900)
    r = report([resting_spo2(98), red_flags([])], pcg, uploaded=1)
    assert r["level"] == "yellow" and "mitral" in r["items"][-1]["text"] and r["attention"]
    no_tech(r)


def test_ai_abstain_reasons_are_actionable(wav_factory):
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.1, np.float32), np.zeros(len(x), np.float32)))
    newborn = report([red_flags([])], model.analyze([Recording("MV", wav_factory())], age_days=5), uploaded=1)
    assert "1 oydan kichik" in newborn["items"][-1]["text"]
    short = report([red_flags([])], model.analyze([Recording("MV", wav_factory(seconds=2))], age_days=900), uploaded=1)
    assert "Qayta yozib ko'ring" in short["items"][-1]["text"]
    no_tech(newborn); no_tech(short)


def test_model_missing_message():
    r = report([red_flags([])], None, uploaded=1, ready=False)
    assert "o'rnatilmagan" in r["items"][-1]["text"]


def test_all_texts_have_three_languages():
    from screening.plain import FLAG_NAMES, LOCATIONS, T
    from screening.rules import RED_FLAGS
    for key, d in {**T, **LOCATIONS}.items():
        assert set(d) == {"uz", "ru", "en"} and all(d.values()), key
    assert set(FLAG_NAMES) == set(RED_FLAGS)


UZ_WORDS = re.compile(r"\b(va|uchun|yurak|qayta|kerak|bola|shovqin|yozuv)\b", re.I)


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_russian_and_english_have_no_uzbek(lang, wav_factory):
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.95, np.float32), np.zeros(len(x), np.float32)))
    cases = [
        ([newborn_pulse_ox(85, 95), red_flags(["cyanosis"])], None, 0),
        ([newborn_pulse_ox(93, 93), red_flags([])], None, 0),
        ([resting_spo2(98), red_flags([])], model.analyze([Recording("MV", wav_factory())], age_days=900), 1),
        ([red_flags([])], model.analyze([Recording("MV", wav_factory(seconds=2))], age_days=900), 1),
    ]
    for rules, pcg, up in cases:
        r = plain_report(triage(rules, pcg), rules, pcg, up, True, lang)
        text = " ".join([r["headline"], r["todo"], r["attention"] or ""] + [i["title"] + " " + i["text"] for i in r["items"]])
        assert r["lang"] == lang and not UZ_WORDS.search(text), text
        no_tech(r)


def test_unknown_language_falls_back_to_uzbek():
    r = report([red_flags([])])
    assert plain_report(triage([red_flags([])], None), [red_flags([])], None, 0, True, "de")["headline"] == r["headline"]


def test_every_risk_level_has_verdict():
    for lvl in RiskLevel:
        ev = Evidence(kind="screening.red_flags", value=[], source=Source.RULE, provenance=Provenance(name="t"), risk=lvl)
        r = plain_report(triage([ev], None), [ev], None, 0, True)
        assert r["headline"] and r["todo"]
