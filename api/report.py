"""Rasmiy kardiologik klinik xulosa va epikrizni chop etish (Print / PDF) generatori.

Xususiyatlari:
  * Rasmiy A4 formatiga moslangan (@page margin 15mm, @media print);
  * Shifoxona va klinika blanki dizayni;
  * Bemorning to'liq klinik yo'li: Skrining, EKG, ExoKG, Angiografiya, Xavf, Guardian;
  * Deterministik qoidalar va AI natijalari solishtiruvi (Concordance);
  * Shifokor imzosi, muhr va CDSS tibbiy ogohlantirish (Disclaimer).
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Optional

from core.consent import get_clinical_consent
from core.episode import Episode
from core.evidence import DISCLAIMER


def render_clinical_report(ep: Episode, digest: dict) -> str:
    """Bemor epizodi uchun A4 print/PDF formatidagi HTML hisobotni generatsiya qiladi."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    overall = digest.get("overall_risk") or "baholanmagan"
    badge_colors = {
        "low": "#16a34a",
        "moderate": "#d97706",
        "high": "#dc2626",
        "very_high": "#991b1b",
        "baholanmagan": "#4b5563",
    }
    badge_bg = badge_colors.get(overall, "#4b5563")

    # Evidence ro'yxati
    ev_rows = []
    for ev in ep.evidence:
        expl = "; ".join(ev.explanation) if ev.explanation else "—"
        r_badge = f'<span style="padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px; background:#f3f4f6; color:#1f2937;">{ev.risk.value.upper()}</span>'
        if ev.abstained:
            r_badge = '<span style="padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px; background:#e5e7eb; color:#4b5563;">ABSTAIN</span>'
        elif ev.risk.value in ("high", "very_high"):
            r_badge = f'<span style="padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px; background:#fee2e2; color:#991b1b;">{ev.risk.value.upper()}</span>'
        elif ev.risk.value == "moderate":
            r_badge = f'<span style="padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px; background:#fef3c7; color:#92400e;">{ev.risk.value.upper()}</span>'

        date_short = ev.created_at[:16].replace("T", " ") if ev.created_at else "—"
        ev_rows.append(f"""
        <tr>
            <td style="padding:6px 10px; border-bottom:1px solid #e5e7eb; font-weight:600; font-size:12px;">{html.escape(ev.kind)}</td>
            <td style="padding:6px 10px; border-bottom:1px solid #e5e7eb; font-size:12px;">{html.escape(expl)}</td>
            <td style="padding:6px 10px; border-bottom:1px solid #e5e7eb; text-align:center;">{r_badge}</td>
            <td style="padding:6px 10px; border-bottom:1px solid #e5e7eb; font-size:11px; color:#6b7280; text-align:right;">{date_short}</td>
        </tr>
        """)

    # Muhokama punktlari (Discussion)
    disc_items = []
    for d in digest.get("discussion", []):
        disc_items.append(f'<li style="margin-bottom:4px; font-size:12px; color:#b45309;"><strong>{html.escape(d.get("reason", ""))}</strong></li>')
    disc_html = f'<ul style="margin:6px 0; padding-left:20px;">{"".join(disc_items)}</ul>' if disc_items else '<p style="font-size:12px; color:#16a34a; margin:4px 0;">Muhokama talab etiladigan ziddiyatlar yo‘q.</p>'

    # Yo'llanmalar (Handoffs)
    handoff_rows = []
    for h in ep.handoffs:
        author = h.author or "shifokor"
        note = h.note or "—"
        dt = h.created_at[:16].replace("T", " ") if h.created_at else "—"
        handoff_rows.append(f"""
        <div style="font-size:12px; margin-bottom:6px; padding:6px 8px; background:#f9fafb; border-left:3px solid #3b82f6;">
            <strong>{html.escape(h.from_stage)} → {html.escape(h.to_stage)}</strong> ({dt}, {html.escape(author)})<br>
            <span style="color:#4b5563;">Izoh: {html.escape(note)}</span>
        </div>
        """)
    handoffs_html = "".join(handoff_rows) if handoff_rows else '<p style="font-size:12px; color:#6b7280;">Boshlang‘ich bosqichda.</p>'

    # Klinik rozilik holati
    c_info = get_clinical_consent(ep)
    if c_info:
        p_ref = html.escape(str(c_info.get("paper_ref", "—")))
        c_doc = html.escape(str(c_info.get("clinician", "shifokor")))
        c_dt = html.escape(str(c_info.get("consented_at", ""))[:10])
        consent_box = (
            f'<div style="margin-top:6px; padding:6px 12px; background:#ecfdf5; border:1px solid #a7f3d0; border-radius:6px; font-size:11px; color:#065f46;">'
            f'<strong>✅ Rasmiy yozma rozilik:</strong> Blank № {p_ref} '
            f'(Oluvchi shifokor: {c_doc}, Sana: {c_dt})'
            f'</div>'
        )
    else:
        consent_box = (
            f'<div style="margin-top:6px; padding:6px 12px; background:#fff7ed; border:1px solid #fed7aa; border-radius:6px; font-size:11px; color:#9a3412;">'
            "<strong>⚠️ Yozma rozilik:</strong> Qog&#x27;oz blank qayd etilmagan (Qonun 24-moddasi talabi)"
            f'</div>'
        )


    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="utf-8">
<title>Klinik Xulosa — {html.escape(ep.patient_ref)}</title>
<style>
    @page {{
        size: A4 portrait;
        margin: 12mm 15mm 15mm 15mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #111827;
        background: #ffffff;
        margin: 0;
        padding: 20px;
        line-height: 1.4;
    }}
    .no-print {{
        background: #f3f4f6;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border: 1px solid #e5e7eb;
    }}
    .print-btn {{
        background: #2563eb;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        font-size: 14px;
    }}
    .print-btn:hover {{
        background: #1d4ed8;
    }}
    @media print {{
        .no-print {{ display: none !important; }}
        body {{ padding: 0 !important; }}
        .page-break {{ page-break-before: always; }}
    }}
    .header {{
        border-bottom: 2px solid #111827;
        padding-bottom: 10px;
        margin-bottom: 16px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }}
    .meta-box {{
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 16px;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px 16px;
        font-size: 12px;
    }}
    .section-title {{
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        color: #1f2937;
        border-bottom: 1px solid #d1d5db;
        padding-bottom: 4px;
        margin: 16px 0 8px 0;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 14px;
    }}
    th {{
        background: #f3f4f6;
        padding: 6px 10px;
        text-align: left;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        border-bottom: 2px solid #d1d5db;
    }}
</style>
</head>
<body>

<div class="no-print">
    <div>
        <strong>CardioPath AI — Rasmiy Klinik Xulosa</strong> (A4 format)
    </div>
    <div>
        <button class="print-btn" onclick="window.print()">🖨️ Chop etish / PDF sifatida saqlash</button>
    </div>
</div>

<div class="header">
    <div>
        <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.05em; color: #4b5563;">O'ZBEKISTON RESPUBLIKASI SOG'LIQNI SAQLASH VAZIRLIGI</div>
        <div style="font-size: 18px; font-weight: 800; margin-top: 2px;">RESPUBLIKA IXTISOSLASHTIRILGAN XIRURGIYA ILMIY-AMALIY TIBBIYOT MARKAZI</div>
        <div style="font-size: 12px; color: #4b5563;">CardioPath AI — Integratsiyalashgan Kardiologik Epikriz</div>
    </div>
    <div style="text-align: right;">
        <span style="display:inline-block; padding: 4px 12px; border-radius: 6px; color: white; background: {badge_bg}; font-weight: 800; font-size: 13px; text-transform: uppercase;">
            Xavf: {overall.upper()}
        </span>
    </div>
</div>

{consent_box}

<div class="meta-box">
    <div><strong>Bemor kodi (ID):</strong> {html.escape(ep.patient_ref)}</div>
    <div><strong>Epizod kodi:</strong> {html.escape(ep.id[:12])}...</div>
    <div><strong>Populyatsiya:</strong> {html.escape(ep.population.capitalize())}</div>
    <div><strong>Amaldagi bosqich:</strong> {html.escape(ep.stage.value.upper())}</div>
    <div><strong>Boshlangan sana:</strong> {ep.created_at[:16].replace("T", " ")}</div>
    <div><strong>Hujjat sanasi:</strong> {now_str}</div>
</div>

<div class="section-title">1. Klinik Dalillar va AI Diagnostik Tahlili (Evidence Timeline)</div>
<table>
    <thead>
        <tr>
            <th style="width: 28%;">Tekshiruv turi</th>
            <th style="width: 48%;">Xulosa va Parametrlar</th>
            <th style="width: 12%; text-align: center;">Xavf</th>
            <th style="width: 12%; text-align: right;">Vaqti</th>
        </tr>
    </thead>
    <tbody>
        {"".join(ev_rows) if ev_rows else '<tr><td colspan="4" style="text-align:center; padding:12px; color:#6b7280;">Hali tekshiruvlar o‘tkazilmagan</td></tr>'}
    </tbody>
</table>

<div class="section-title">2. Konsilium va Konsordans (Heart Team Discussion)</div>
<div style="background:#fffbeb; border:1px solid #fef3c7; border-radius:6px; padding:10px 14px; margin-bottom:14px;">
    {disc_html}
</div>

<div class="section-title">3. Bosqichlararo Yo‘llanmalar (Handoff History)</div>
{handoffs_html}

<div style="margin-top: 30px; padding-top: 16px; border-top: 1px dashed #9ca3af; display: flex; justify-content: space-between; font-size: 12px;">
    <div>
        <strong>Davolovchi shifokor:</strong> _______________________<br>
        <span style="font-size:10px; color:#6b7280;">(F.I.Sh., imzo va shaxsiy muhr)</span>
    </div>
    <div style="text-align: right;">
        <strong>Bo'lim mudiri / Jarroh:</strong> _______________________<br>
        <span style="font-size:10px; color:#6b7280;">(Imzo va sana)</span>
    </div>
</div>

<div style="margin-top: 24px; font-size: 9px; color: #6b7280; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 8px;">
    <strong>Diqqat:</strong> {DISCLAIMER} Tizim shifokorning klinik fikrini almashtirmaydi.
</div>

</body>
</html>
"""
