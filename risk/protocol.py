"""Heart Team konsiliumi protokoli — epizod vaqt chizig'idan yig'iladi.

Tuzilma qat'iy: raqamlar faqat Evidence'dan olinadi (LLM yo'q). Ziddiyatlar, AI abstain holatlari va kiritilmagan
maydonlar alohida "majburiy muhokama" bo'limiga chiqariladi (integration.digest bilan bir xil manba).
"""
from __future__ import annotations

from core.episode import Episode
from core.evidence import DISCLAIMER, Evidence
from integration.concordances import aki_concordance, ef_concordance  # noqa: F401  (risk_routes va testlar shu yerdan oladi)
from integration.digest import episode_digest


def _line(ev: Evidence | None, label: str) -> str:
    if ev is None:
        return f"| {label} | — | kiritilmagan |"
    if ev.abstained:
        return f"| {label} | abstain | {'; '.join(ev.explanation)} |"
    return f"| {label} | {ev.value} {ev.unit} | {ev.risk.value} ({ev.provenance.name}) |"


def _ai_row(label: str, ev: Evidence | None, what) -> str:
    if ev is None:
        return f"| {label} | — | bajarilmagan |"
    if ev.abstained:
        return f"| {label} | AI javob bermadi | {'; '.join(ev.explanation)} |"
    return f"| {label} | {what(ev)} | {ev.risk.value} ({ev.provenance.name} {ev.provenance.version}) |"


def _ecg_text(ev: Evidence) -> str:
    v = ev.value or {}
    other = v.get("other_findings") or []
    return f"AFIB ehtimoli {v.get('p_afib', 0):.2f}" + (f"; boshqa: {', '.join(other)}" if other else "")


def _lowef_text(ev: Evidence) -> str:
    p = (ev.value or {}).get("p_low_ef", 0)
    return ("past EF (≤45%) ehtimoli" if ev.risk.value != "low" else "past EF belgisi yo'q") + f" (p={p:.2f})"


def _shd_text(ev: Evidence) -> str:
    names = (ev.value or {}).get("positive_names") or []
    return ("ehtimoli: " + ", ".join(names)) if names else "tekshirilgan belgilar topilmadi"


def _angio_text(ev: Evidence) -> str:
    n = (ev.value or {}).get("n_candidates", 0)
    return f"{n} ta stenoz nomzodi (SYNTAX kalkulyatori emas)" if n else "nomzod topilmadi («stenoz yo'q» degani emas)"


def heart_team_protocol(ep: Episode) -> str:
    es, aki_rule, aki_ml = ep.latest("risk.euroscore2"), ep.latest("risk.aki.rule"), ep.latest("risk.aki.model")
    conc, ef_conc = aki_concordance(ep), ef_concordance(ep)
    digest = episode_digest(ep)
    discussion = [f"{d['topic']}: {d['reason']}" for d in digest["discussion"]]
    questions = digest["open_questions"]

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
        "## AI yordamchi topilmalari (tadqiqot rejimi, qaror shifokorniki)",
        "| Modul | Natija | Xavf (model) |",
        "|---|---|---|",
        _ai_row("EKG (bo'lmachalar fibrillyatsiyasi)", ep.latest("ecg.afib"), _ecg_text),
        _ai_row("AI-EKG: past EF", ep.latest("ecg.low_ef"), _lowef_text),
        _ai_row("AI-EKG: yurak tuzilishi (klapanlar, o'ng qorincha)", ep.latest("ecg.shd"), _shd_text),
        _ai_row("Angiografiya (SYNTAX-ga yordamchi)", ep.latest("angio.stenosis_assist"), _angio_text),
        _ai_row("ExoKG videosidan EF", ep.latest("echo.ef"), lambda e: f"EF ≈ {e.value:.0f}% (±{e.uncertainty or 0:.0f}%)"),
        "",
        f"**LVEF (shifokor vs AI):** {ef_conc.status.value + ' — ' + ef_conc.message if ef_conc else '— (solishtirib bo\'lmaydi: ikkalasi ham kerak)'}",
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
