"""Tests for risk/kdigo.py — KDIGO Acute Kidney Injury staging."""
import pytest

from core.evidence import RiskLevel
from risk.kdigo import KDIGOInput, assess_kdigo


def test_kdigo_stage_0():
    inp = KDIGOInput(baseline_creatinine=80.0, current_creatinine=85.0)
    ev = assess_kdigo(inp)
    assert not ev.abstained
    assert ev.value["stage"] == 0
    assert ev.risk == RiskLevel.LOW


def test_kdigo_stage_1_by_ratio():
    # 80 -> 130 is > 1.5x
    inp = KDIGOInput(baseline_creatinine=80.0, current_creatinine=130.0)
    ev = assess_kdigo(inp)
    assert ev.value["stage"] == 1
    assert ev.risk == RiskLevel.MODERATE


def test_kdigo_stage_1_by_48h_rise():
    inp = KDIGOInput(baseline_creatinine=90.0, current_creatinine=118.0, creatinine_48h_rise=28.0)
    ev = assess_kdigo(inp)
    assert ev.value["stage"] == 1
    assert ev.risk == RiskLevel.MODERATE


def test_kdigo_stage_2_by_ratio():
    # 80 -> 180 is 2.25x
    inp = KDIGOInput(baseline_creatinine=80.0, current_creatinine=180.0)
    ev = assess_kdigo(inp)
    assert ev.value["stage"] == 2
    assert ev.risk == RiskLevel.HIGH


def test_kdigo_stage_2_by_urine_output():
    # <0.5 ml/kg/h for 14 hours
    inp = KDIGOInput(baseline_creatinine=80.0, current_creatinine=90.0, urine_output_ml_kg_h=0.4, urine_hours=14.0)
    ev = assess_kdigo(inp)
    assert ev.value["stage"] == 2
    assert ev.risk == RiskLevel.HIGH


def test_kdigo_stage_3_by_ratio():
    # 80 -> 250 is > 3.0x
    inp = KDIGOInput(baseline_creatinine=80.0, current_creatinine=250.0)
    ev = assess_kdigo(inp)
    assert ev.value["stage"] == 3
    assert ev.risk == RiskLevel.VERY_HIGH


def test_kdigo_stage_3_by_rrt():
    inp = KDIGOInput(baseline_creatinine=80.0, current_creatinine=90.0, rrt=True)
    ev = assess_kdigo(inp)
    assert ev.value["stage"] == 3
    assert ev.risk == RiskLevel.VERY_HIGH


def test_kdigo_invalid_inputs_abstains():
    inp = KDIGOInput(baseline_creatinine=-10.0, current_creatinine=90.0)
    ev = assess_kdigo(inp)
    assert ev.abstained
