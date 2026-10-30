"""Epizod xulosasi (digest): bir bemorning barcha qoida va AI natijalari, zidliklar va muhokama punktlari bitta joyda.

Hech narsa yangidan hisoblanmaydi va uydirilmaydi: hammasi epizod Evidence'laridan olinadi. Ekran (kelajakdagi
dizayn) va Heart Team protokoli bir xil manbadan foydalanadi — ikki joyda ikki xil javob chiqmaydi.
`discussion[].code` — mashina o'qiydigan kod (ekran uni istalgan tilga tarjima qiladi); `reason` — o'zbekcha matn.
"""
from __future__ import annotations

from typing import Optional

from core.episode import ALLOWED, Episode, Stage
from core.evidence import Evidence
from integration.concordances import aki_concordance, ef_concordance

# AI modullari: ichki nom → Evidence turi
AI_KINDS = {"pcg": "screening.pcg", "ecg": "ecg.afib", "angio": "angio.stenosis_assist", "echo_ef": "echo.ef"}


def brief(ev: Evidence) -> dict:
    return {"id": ev.id, "kind": ev.kind, "value": ev.value, "unit": ev.unit, "risk": ev.risk.value,
            "source": ev.source.value, "abstained": ev.abstained, "explanation": ev.explanation,
            "created_at": ev.created_at, "model": ev.provenance.name, "model_version": ev.provenance.version}


def _ai_state(ev: Optional[Evidence]) -> dict:
    if ev is None:
        return {"state": "not_run", "risk": None, "evidence_id": None, "summary": None}
    if ev.abstained:
        return {"state": "abstained", "risk": None, "evidence_id": ev.id, "summary": "; ".join(ev.explanation)}
    return {"state": "ok", "risk": ev.risk.value, "evidence_id": ev.id, "summary": ev.explanation[0] if ev.explanation else None}


def _screening_concordance(ep: Episode) -> Optional[dict]:
    triage = next((e for e in reversed(ep.evidence) if e.kind == "screening.triage"), None)
    if triage is None or not isinstance(triage.value, dict):
        return None
    status = triage.value.get("concordance")
    return {"question": "TYN skriningi: qoida vs PCG-AI", "status": status, "final_risk": triage.risk.value,
            "needs_discussion": status in ("disagree", "ai_abstained"), "evidence_id": triage.id,
            "message": "; ".join(triage.explanation)}


def episode_digest(ep: Episode, alerts: Optional[list[dict]] = None) -> dict:
    latest: dict[str, Evidence] = {}
    for ev in ep.evidence:
        latest[ev.kind] = ev

    concordance, discussion = [], []

    def add_discussion(code: str, topic: str, reason: str, ids: list[str]) -> None:
        discussion.append({"code": code, "topic": topic, "reason": reason, "evidence_ids": [i for i in ids if i]})

    aki = aki_concordance(ep)
    if aki:
        concordance.append(aki.to_dict())
        if aki.needs_discussion:
            add_discussion("aki_" + aki.status.value, "AKI xavfi", aki.message,
                           [aki.rule.id, aki.ai.id if aki.ai else None])
    ef = ef_concordance(ep)
    if ef:
        concordance.append(ef.to_dict())
        if ef.needs_discussion:
            add_discussion("ef_" + ef.status.value, "LVEF", ef.message, [ef.rule.id, ef.ai.id if ef.ai else None])
    scr = _screening_concordance(ep)
    if scr:
        concordance.append(scr)
        if scr["needs_discussion"]:
            add_discussion("screening_" + scr["status"], "TYN skriningi", scr["message"], [scr["evidence_id"]])

    if ep.stage == Stage.HEART_TEAM and "risk.euroscore2" not in latest:
        add_discussion("euroscore_missing", "EuroSCORE II", "EuroSCORE II hisoblanmagan.", [])
    assumed = latest.get("risk.assumptions")
    if assumed is not None:
        add_discussion("assumed_defaults", "EuroSCORE II kiritishlari",
                       "Quyidagi maydonlar kiritilmadi, eng past xavfli standart qiymat olindi (xavf kam baholangan bo'lishi mumkin): "
                       + "; ".join(assumed.explanation), [assumed.id])
    afib = latest.get("ecg.afib")
    if afib is not None and not afib.abstained and afib.risk.value in ("high", "very_high"):
        add_discussion("afib_high", "EKG", "EKGda bo'lmachalar fibrillyatsiyasi ehtimoli yuqori (AI) — shifokor EKGni "
                       "ko'rib tasdiqlaydi.", [afib.id])
    angio = latest.get("angio.stenosis_assist")
    if angio is not None and not angio.abstained and isinstance(angio.value, dict) and angio.value.get("n_candidates"):
        add_discussion("angio_candidates", "Angiografiya",
                       f"Kadrda {angio.value['n_candidates']} ta stenoz nomzodi (SYNTAX kalkulyatori emas) — "
                       "Heart Team angiogrammani o'zi ko'rib chiqadi.", [angio.id])

    suggestions = []
    ef_ai = latest.get("echo.ef")
    if ef_ai is not None and not ef_ai.abstained and "clinician.lvef" not in latest:
        suggestions.append({"code": "enter_lvef", "text": f"ExoKG videodan AI EF ≈ {ef_ai.value:.0f}% mavjud. Xavf baholashda "
                            "LVEF ni ExoKG shifokorining o'lchovi bilan kiriting; AI qiymati o'zi to'ldirilmaydi."})

    return {
        "episode": {"id": ep.id, "patient_ref": ep.patient_ref, "population": ep.population, "stage": ep.stage.value,
                    "created_at": ep.created_at},
        "next_stages": sorted(s.value for s in ALLOWED[ep.stage]),
        "latest": {k: brief(v) for k, v in latest.items()},
        "ai": {name: _ai_state(latest.get(kind)) for name, kind in AI_KINDS.items()},
        "concordance": concordance,
        "discussion": discussion,
        "suggestions": suggestions,
        # bir xil savol bir necha yo'llanmada takrorlansa, bir marta (tartib saqlanadi)
        "open_questions": list(dict.fromkeys(q for h in ep.handoffs for q in h.open_questions)),
        "open_alerts": [a for a in (alerts or []) if not a.get("acknowledged")],
        "counts": {"evidence": len(ep.evidence), "handoffs": len(ep.handoffs)},
    }
