"""Modullararo solishtiruvlar: bir savol bo'yicha qoida/shifokor va AI natijasini yonma-yon qo'yish.

Barcha solishtiruv `core.concordance.compare` orqali: AI xavfni hech qachon pasaytirmaydi, zidlik yashirilmaydi.
"""
from __future__ import annotations

from typing import Optional

from adapters.echo_ef import ef_risk
from core.concordance import Agreement, ConcordanceResult, compare
from core.episode import Episode
from core.evidence import Evidence, Provenance, Source


def lvef_evidence(percent: float) -> Evidence:
    """Shifokor kiritgan LVEF (ExoKG o'lchovi) — AI EF bilan solishtirish uchun «qoida tomoni»."""
    return Evidence(kind="clinician.lvef", value=round(float(percent), 1), unit="%", source=Source.CLINICIAN,
                    provenance=Provenance(name="clinician_input", reference="xavf baholashda kiritilgan LVEF (ExoKG)"),
                    risk=ef_risk(float(percent)),
                    explanation=[f"shifokor kiritgan LVEF {percent:.0f}%"])


def aki_concordance(ep: Episode) -> Optional[ConcordanceResult]:
    rule = ep.latest("risk.aki.rule")
    if rule is None:
        return None
    # Thakar (dializli O'BYe) va ML (KDIGO AKI) turli natijalar → qo'shni toifa farqi "mos".
    return compare("AKI xavfi: Thakar vs ML", rule, ep.latest("risk.aki.model"), tolerance=1)


def ef_concordance(ep: Episode) -> Optional[ConcordanceResult]:
    """Shifokor kiritgan LVEF vs ExoKG videodan AI EF. Ikkalasi ham bo'lmasa — None (solishtirib bo'lmaydi)."""
    rule, ai = ep.latest("clinician.lvef"), ep.latest("echo.ef")
    if rule is None or ai is None:
        return None
    res = compare("LVEF: shifokor vs AI (ExoKG video)", rule, ai, tolerance=0)
    if ai.abstained or not isinstance(ai.value, (int, float)):
        return res
    delta = float(ai.value) - float(rule.value)
    note = f" Shifokor {rule.value:.0f}%, AI {ai.value:.0f}% (farq {delta:+.0f} punkt; AI xatosi ±{ai.uncertainty or 0:.0f}%)."
    if res.status == Agreement.AGREE and abs(delta) >= 10:
        note += " Toifa mos, lekin farq 10 punktdan katta — ExoKG o'lchovini qayta tekshiring."
    res.message += note
    return res
