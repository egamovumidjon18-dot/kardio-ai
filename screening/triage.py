"""TYN triaji: qoida treki + AI (PCG) treki → Concordance → yo'nalish.

AI xavfni faqat oshira oladi. CCHD FAIL har doim eng ustun.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.concordance import ConcordanceResult, compare
from core.evidence import DISCLAIMER, Evidence, Provenance, RiskLevel, Source, risk_rank

ACTIONS = {
    RiskLevel.VERY_HIGH: "DARHOL: neonatolog/pediatrik kardiolog, ExoKG gacha javob bermaslik",
    RiskLevel.HIGH: "SHOSHILINCH: pediatrik kardiolog ko'rigi va ExoKG (mahalliy protokol muddatida)",
    RiskLevel.MODERATE: "REJALI: ExoKG ga yo'llanma",
    RiskLevel.LOW: "Muntazam kuzatuv; belgilar paydo bo'lsa qayta skrining",
    RiskLevel.NORMAL: "Muntazam kuzatuv",
    RiskLevel.UNKNOWN: "Ma'lumot yetarli emas — shifokor qaror qiladi",
}


@dataclass
class TriageResult:
    rule: Evidence
    concordance: ConcordanceResult
    action: str
    summary: Evidence

    def to_dict(self) -> dict:
        return {"action": self.action, "final_risk": self.concordance.final_risk.value,
                "concordance": self.concordance.to_dict(), "summary": self.summary.to_dict(),
                "disclaimer": DISCLAIMER}


def combine_rules(items: list[Evidence]) -> Evidence:
    """Bir nechta qoida natijasini bitta qoida-trekiga birlashtiradi (maksimal xavf)."""
    usable = [e for e in items if not e.abstained and risk_rank(e.risk) is not None]
    trace = [f"{e.kind}: {e.risk.value if not e.abstained else 'abstain'} — {'; '.join(e.explanation)}"
             for e in items]
    prov = Provenance(name="screening_rules", reference="; ".join(sorted({e.provenance.name for e in items})))
    if not usable:
        return Evidence(kind="screening.rule", value=None, source=Source.RULE, provenance=prov,
                        risk=RiskLevel.UNKNOWN, explanation=trace or ["qoida ma'lumoti kiritilmagan"])
    worst = max(usable, key=lambda e: risk_rank(e.risk))
    return Evidence(kind="screening.rule", value={"driver": worst.kind}, source=Source.RULE,
                    provenance=prov, risk=worst.risk, explanation=trace)


def triage(rule_items: list[Evidence], pcg: Optional[Evidence]) -> TriageResult:
    rule = combine_rules(rule_items)
    conc = compare("TYN skriningi: qoida vs PCG-AI", rule, pcg)
    final = conc.final_risk
    # CCHD FAIL — kritik TYN gumoni: eng yuqori daraja.
    if any(e.kind == "screening.cchd" and e.value == "fail" for e in rule_items):
        final = RiskLevel.VERY_HIGH
        conc.final_risk = final
    action = ACTIONS[final]
    summary = Evidence(kind="screening.triage", value={"action": action, "concordance": conc.status.value},
                       source=Source.RULE, provenance=Provenance(name="chd_triage"),
                       risk=final, explanation=[conc.message])
    return TriageResult(rule=rule, concordance=conc, action=action, summary=summary)
