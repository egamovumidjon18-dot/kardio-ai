"""Heart Team konsiliumi protokoli — epizod vaqt chizig'idan yig'iladi.

Tuzilma qat'iy: raqamlar faqat Evidence'dan olinadi (LLM yo'q). Ziddiyatlar
va AI abstain holatlari alohida "majburiy muhokama" bo'limiga chiqariladi.
"""
from __future__ import annotations

from core.concordance import ConcordanceResult, compare
from core.episode import Episode
from core.evidence import DISCLAIMER, Evidence


def aki_concordance(ep: Episode) -> ConcordanceResult | None:
    rule = ep.latest("risk.aki.rule")
    if rule is None:
        return None
    # Thakar (dializli O'BYe) va ML (KDIGO AKI) turli natijalar → qo'shni toifa farqi "mos".
    return compare("AKI xavfi: Thakar vs ML", rule, ep.latest("risk.aki.model"), tolerance=1)


def _line(ev: Evidence | None, label: str) -> str:
    if ev is None:
        return f"| {label} | — | kiritilmagan |"
    if ev.abstained:
        return f"| {label} | abstain | {'; '.join(ev.explanation)} |"
    return f"| {label} | {ev.value} {ev.unit} | {ev.risk.value} ({ev.provenance.name}) |"


def heart_team_protocol(ep: Episode) -> str:
    es, aki_rule, aki_ml = ep.latest("risk.euroscore2"), ep.latest("risk.aki.rule"), ep.latest("risk.aki.model")
    conc = aki_concordance(ep)
    discussion = []
    if conc and conc.needs_discussion:
        discussion.append(conc.message)
    for ev in ep.evidence:
        if ev.kind.endswith("triage") and ev.value and ev.value.get("concordance") in ("disagree", "ai_abstained"):
            discussion.append(f"{ev.kind}: {'; '.join(ev.explanation)}")
    if es is None:
        discussion.append("EuroSCORE II hisoblanmagan.")
    questions = [q for h in ep.handoffs for q in h.open_questions]

    lines = [
        "# Heart Team konsiliumi protokoli",
        f"Bemor: `{ep.patient_ref}` · epizod `{ep.id[:8]}` · bosqich: **{ep.stage.value}**",
        "",
        "## Xavf baholash",
        "| Ko'rsatkich | Qiymat | Xavf (manba) |",
        "|---|---|---|",
        _line(es, "EuroSCORE II (o'lim)"),
        _line(aki_rule, "Thakar (dializli O'BYe)"),
        _line(aki_ml, "ML: KDIGO AKI"),
        "",
        f"**AKI concordance:** {conc.status.value + ' — ' + conc.message if conc else '—'}",
        "",
        "## Majburiy muhokama punktlari",
        *([f"- [ ] {d}" for d in discussion] or ["- (yo'q)"]),
        "",
        "## Oldingi bosqichlardan ochiq savollar",
        *([f"- {q}" for q in questions] or ["- (yo'q)"]),
        "",
        "## Qaror (konsilium to'ldiradi)",
        "- [ ] Jarrohlik  - [ ] Intervensiya  - [ ] Medikamentoz  - [ ] Qo'shimcha tekshiruv",
        "",
        "Kardiolog: ____________   Kardioxirurg: ____________   Anesteziolog: ____________",
        "",
        f"> {DISCLAIMER}",
    ]
    return "\n".join(lines)
