"""Epizod xulosasi (digest): bir bemorning barcha qoida va AI natijalari, zidliklar va muhokama punktlari bitta joyda.

Hech narsa yangidan hisoblanmaydi va uydirilmaydi: hammasi epizod Evidence'laridan olinadi. Ekran (kelajakdagi
dizayn) va Heart Team protokoli bir xil manbadan foydalanadi — ikki joyda ikki xil javob chiqmaydi.
`discussion[].code` — mashina o'qiydigan kod (ekran uni istalgan tilga tarjima qiladi); `reason` — o'zbekcha matn.
"""
from __future__ import annotations

from typing import Optional
import math

from core.episode import ALLOWED, Episode, Stage
from core.evidence import Evidence, risk_rank
from integration.concordances import aki_concordance, ecg_lvef_concordance, ef_concordance

# AI modullari: ichki nom → Evidence turi
AI_KINDS = {"pcg": "screening.pcg", "ecg": "ecg.afib", "ecg_low_ef": "ecg.low_ef", "ecg_shd": "ecg.shd",
            "angio": "angio.stenosis_assist", "echo_ef": "echo.ef", "cxr": "cxr.findings"}


def brief(ev: Evidence) -> dict:
    return {"id": ev.id, "kind": ev.kind, "value": ev.value, "unit": ev.unit, "risk": ev.risk.value,
            "source": ev.source.value, "abstained": ev.abstained, "explanation": ev.explanation,
            "created_at": ev.created_at, "measured_at": ev.measured_at,
            "model": ev.provenance.name, "model_version": ev.provenance.version}


def overall_risk(latest: dict[str, Evidence]) -> Optional[str]:
    """Eng yuqori xavf: har bir turdagi oxirgi, abstain qilinmagan natijalar orasidan (AI pasaytira olmaydi — faqat maksimum).
    Hech qanday baholangan natija bo'lmasa None (bu «xavf yo'q» degani EMAS)."""
    ranks = [(risk_rank(ev.risk), ev.risk.value) for k, ev in latest.items()
             if not ev.abstained and k != "risk.assumptions" and risk_rank(ev.risk) is not None]
    return max(ranks)[1] if ranks else None


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
    ecg_ef = ecg_lvef_concordance(ep)
    if ecg_ef:
        concordance.append(ecg_ef)
        if ecg_ef["needs_discussion"]:
            add_discussion("ecg_lvef_disagree", "LVEF", ecg_ef["message"], ecg_ef["evidence_ids"])
    scr = _screening_concordance(ep)
    if scr:
        concordance.append(scr)
        if scr["needs_discussion"]:
            add_discussion("screening_" + scr["status"], "TYN skriningi", scr["message"], [scr["evidence_id"]])

    if ep.stage == Stage.HEART_TEAM and "risk.euroscore2" not in latest:
        add_discussion("euroscore_missing", "EuroSCORE II", "EuroSCORE II hisoblanmagan.", [])
    assumed = latest.get("risk.assumptions")
    if assumed is not None and assumed.value:
        add_discussion("assumed_defaults", "EuroSCORE II kiritishlari",
                       "Quyidagi maydonlar kiritilmadi, eng past xavfli standart qiymat olindi (xavf kam baholangan bo'lishi mumkin): "
                       + "; ".join(assumed.explanation), [assumed.id])
    afib = latest.get("ecg.afib")
    if afib is not None and not afib.abstained and afib.risk.value in ("high", "very_high"):
        add_discussion("afib_high", "EKG", "EKGda bo'lmachalar fibrillyatsiyasi ehtimoli yuqori (AI) — shifokor EKGni "
                       "ko'rib tasdiqlaydi.", [afib.id])
    low_ef = latest.get("ecg.low_ef")
    def valid_lvef(kind: str) -> bool:
        ev = latest.get(kind)
        return (ev is not None and not ev.abstained and isinstance(ev.value, (int, float))
                and not isinstance(ev.value, bool) and math.isfinite(ev.value) and 0 < ev.value <= 100)

    if (low_ef is not None and not low_ef.abstained and low_ef.risk.value != "low"
            and not valid_lvef("clinician.lvef") and not valid_lvef("echo.ef")):
        add_discussion("lowef_echo_needed", "LVEF", "AI-EKG: past EF (≤45%) ehtimoli, LVEF hali o'lchanmagan — ExoKG kerak.",
                       [low_ef.id])
    # Failed or uncertain runs must remain visible even when another model has
    # a valid low-risk result. Presence of a failed echo is not an EF measurement.
    for name, kind in AI_KINDS.items():
        ev = latest.get(kind)
        if ev is not None and ev.abstained:
            add_discussion("ai_result_unavailable", name,
                           "AI xulosa bermadi: " + "; ".join(ev.explanation), [ev.id])
    shd = latest.get("ecg.shd")
    if shd is not None and not shd.abstained and isinstance(shd.value, dict) and shd.value.get("positive"):
        add_discussion("shd_echo", "Yurak tuzilishi",
                       "AI-EKG ehtimoli: " + ", ".join(shd.value.get("positive_names") or shd.value["positive"])
                       + " — ExoKG'da klapanlar va o'ng qorincha baholansin (EKG darajani aniqlamaydi).", [shd.id])

    # CXR Rentgen topilmalari
    cxr = latest.get("cxr.findings")
    if cxr is not None and not cxr.abstained and isinstance(cxr.value, dict):
        ctr = cxr.value.get("ctr_ratio", 0)
        if ctr >= 0.60:
            add_discussion("cxr_severe_cardio", "Rentgen (CXR)",
                           f"Og'ir kardiomegaliya (CTR={ctr:.2f} >= 0.60) — yurak bo'shliqlari kengayishi yoki gidroperikard.", [cxr.id])
        congest = cxr.value.get("pulmonary_congestion")
        if congest in ("moderate", "severe"):
            add_discussion("cxr_congestion", "Rentgen (CXR)",
                           f"O'pka dimlanishi ({congest}) — dekompensatsiyalangan yurak yetishmovchiligi belgilari.", [cxr.id])

    # Biomarkerlar (Troponin / NT-proBNP)
    bio = latest.get("lab.biomarkers")
    if bio is not None and not bio.abstained and isinstance(bio.value, dict):
        if bio.value.get("troponin_decision") == "rule_in":
            add_discussion("bio_acs_rule_in", "Biomarkerlar (O'KS)",
                           "hs-cTnI o'tkir dinamikasi (Rule-In) — o'tkir koronar sindrom / infarkt shubhasi, shoshilinch KShSh/koronarografiya.", [bio.id])
        if bio.value.get("nt_probnp_decision") in ("decompensation_very_likely", "decompensation_likely"):
            add_discussion("bio_hf_decomp", "Biomarkerlar (YuYe)",
                           "NT-proBNP / BNP yuqori — yurak yetishmovchiligi dekompensatsiyasi laborator tasdiqlangan.", [bio.id])

    # ExoKG Klapanlar va sPAP
    valves = latest.get("echo.valves")
    if valves is not None and not valves.abstained and isinstance(valves.value, dict):
        as_info = valves.value.get("aortic_stenosis", {})
        if as_info.get("severe"):
            add_discussion("echo_severe_as", "ExoKG Klapanlar",
                           "Og'ir aortal stenoz — Heart Team konsiliumida SAVR yoki TAVI ko'rib chiqilsin.", [valves.id])
        mr_info = valves.value.get("mitral_regurgitation", {})
        if mr_info.get("severe"):
            add_discussion("echo_severe_mr", "ExoKG Klapanlar",
                           "Og'ir mitral yetishmovchilik — mitral qopqoq rekonstruksiyasi yoki protezlash ko'rsatmasi.", [valves.id])
        ph_info = valves.value.get("pulmonary_hypertension", {})
        if ph_info.get("severe"):
            add_discussion("echo_severe_ph", "O'pka Gipertenziyasi",
                           f"Og'ir o'pka gipertenziyasi (sPAP={ph_info.get('spap_mmhg')} mmHg) — yuqori jarrohlik xavfi omili.", [valves.id])

    # Koronar tomirlar va LMS
    vessels = latest.get("angio.vessels")
    if vessels is not None and not vessels.abstained and isinstance(vessels.value, dict):
        if vessels.value.get("lms_stenosis_pct", 0) >= 50:
            add_discussion("angio_lms_stenosis", "Koronarografiya (LMS)",
                           f"Chap asosiy poya (LMS) {vessels.value.get('lms_stenosis_pct')}% stenozi — shoshilinch jarrohlik (KShSh) konsiliumi.", [vessels.id])

    # EKG intervallari (QTc)
    intervals = latest.get("ecg.intervals")
    if intervals is not None and not intervals.abstained and isinstance(intervals.value, dict):
        qtc = intervals.value.get("qtc_bazett_ms", 0)
        if qtc >= 500:
            add_discussion("ecg_long_qtc", "EKG Intervallari",
                           f"Xavfli QTc uzayishi ({qtc} ms >= 500 ms) — torsades de pointes va to'satdan aritmik o'lim xavfi.", [intervals.id])

    # Kross-modal klinik ziddiyatlar (Cross-modality discordance)
    if bio is not None and not bio.abstained and isinstance(bio.value, dict) and bio.value.get("troponin_decision") == "rule_in":
        afib_ev = latest.get("ecg.afib")
        if afib_ev is not None and not afib_ev.abstained and afib_ev.risk.value == "low":
            add_discussion("bio_ecg_discordance", "Klinik Ziddiyat",
                           "Troponin bo'yicha o'tkir miokard shikastlanishi (Rule-In), lekin EKG ritmi sokin — og'riqsiz O'KS yoki mikrotomirlar patologiyasi shubhasi.", [bio.id, afib_ev.id])

    if cxr is not None and not cxr.abstained and isinstance(cxr.value, dict) and (cxr.value.get("ctr_ratio", 0) >= 0.60 or cxr.value.get("pulmonary_congestion") in ("moderate", "severe")):
        ef_val = None
        if valid_lvef("clinician.lvef"):
            ef_val = latest["clinician.lvef"].value
        elif valid_lvef("echo.ef"):
            ef_val = latest["echo.ef"].value
        if ef_val is not None and ef_val >= 50:
            add_discussion("cxr_echo_discordance", "Klinik Ziddiyat",
                           f"Rentgenda kardiomegaliya yoki o'pka dimlanishi, lekin LVEF saqlangan ({ef_val:.0f}%) — HFpEF (diastolik yetishmovchilik) yoki gidroperikard istisno qilinsin.", [cxr.id])

    angio = latest.get("angio.stenosis_assist")
    if angio is not None and not angio.abstained and isinstance(angio.value, dict) and angio.value.get("n_candidates"):
        add_discussion("angio_candidates", "Angiografiya",
                       f"Kadrda {angio.value['n_candidates']} ta stenoz nomzodi (SYNTAX kalkulyatori emas) — "
                       "Heart Team angiogrammani o'zi ko'rib chiqadi.", [angio.id])

    suggestions = []
    ef_ai = latest.get("echo.ef")
    if valid_lvef("echo.ef") and not valid_lvef("clinician.lvef"):
        suggestions.append({"code": "enter_lvef", "text": f"ExoKG videodan AI EF ≈ {ef_ai.value:.0f}% mavjud. Xavf baholashda "
                            "LVEF ni ExoKG shifokorining o'lchovi bilan kiriting; AI qiymati o'zi to'ldirilmaydi."})

    return {
        "episode": {"id": ep.id, "patient_ref": ep.patient_ref, "population": ep.population, "stage": ep.stage.value,
                    "created_at": ep.created_at},
        "next_stages": sorted(s.value for s in ALLOWED[ep.stage]),
        "overall_risk": overall_risk(latest),
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
