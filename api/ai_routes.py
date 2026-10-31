"""EKG, angiografiya, MNO-rasm OCR va ExoKG EF endpointlari. Har bir modul ixtiyoriy: ulanmagan bo'lsa 503."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
import logging
from typing import Callable, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from adapters.echo_ef import EchoEFAdapter
from api.alerts import record_alert
from angio.model import AngioModel
from api.ai_plain import plain_ai
from api.guardian_routes import _postop_day
from core.episode import Episode, Stage
from core.evidence import Evidence
from core.shadow import ShadowRhythmModel, ShadowStore, input_hash
from core.store import EpisodeStore
from ecg.low_ef import LowEFFromECG
from ecg.model import ECGModel
from ecg.shd import StructuralFromECG
from ecg.signal import read_csv
from guardian.escalation import Notifier, escalate
from guardian.inr import Indication
from guardian.ocr import Engine, assess_inr_image

MAX_UPLOAD = 25 * 1024 * 1024
MAX_VIDEO = 100 * 1024 * 1024
log = logging.getLogger(__name__)


async def _read(f: UploadFile, limit: int) -> bytes:
    data = await f.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"fayl juda katta (>{limit // (1024 * 1024)} MB)")
    return data


def _ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def register(app: FastAPI, store: EpisodeStore, get: Callable[[str], Episode], notifier: Notifier,
             ecg: Optional[ECGModel], angio: Optional[AngioModel], ef: Optional[EchoEFAdapter],
             ocr_engine: Optional[Engine] = None, low_ef: Optional[LowEFFromECG] = None,
             shd: Optional[StructuralFromECG] = None, shadow_models: Optional[list[ShadowRhythmModel]] = None,
             shadow_store: Optional[ShadowStore] = None) -> None:
    def _need(model, name: str) -> None:
        if model is None:
            raise HTTPException(503, f"{name} moduli ulanmagan (og'irliklar yo'q) — qoidalar ishlashda davom etadi")

    def _save(ep: Episode, actor: str, action: str, ev: Evidence) -> dict:
        ep.add(ev)
        store.save(ep, actor, action, {"kind": ev.kind, "abstained": ev.abstained, "risk": ev.risk.value})
        return ev.to_dict()

    def _shadow(ep: Episode, sig, fs: float, leads, age_years: Optional[float], ev: Evidence) -> None:
        """Shadow modellar: natija faqat shadow jadvaliga yoziladi. Xato asosiy yo'lni hech qachon buzmaydi."""
        if not shadow_models or shadow_store is None:
            return
        try:
            v = ev.value if isinstance(ev.value, dict) else {}
            live = {"abstained": True} if ev.abstained else {
                "afib_call": ev.risk.value in ("high", "very_high"), "p_afib": v.get("p_afib"), "model": ecg.card.name}
            outs = {}
            for m in shadow_models:
                try:
                    outs[m.key] = m.run(sig, fs, leads)
                except Exception as exc:              # noqa: BLE001 — bitta shadow model xatosi boshqalarini to'xtatmasin
                    log.warning("shadow model %s xatosi: %s", m.key, exc)
                    outs[m.key] = {"error": type(exc).__name__}
            shadow_store.add_run(ep.id, "ecg.rhythm", input_hash(sig, fs), age_years, live, outs)
        except Exception as exc:                      # noqa: BLE001
            log.warning("shadow yozuvi saqlanmadi: %s", exc)

    @app.get("/models")
    def models() -> dict:
        def card(m):
            return m.card.to_dict() if m else None
        blocked = {
            "csa_aki_ml": "MIMIC-IV (PhysioNet credentialed) kerak — risk/aki.py AKIModel interfeysi tayyor",
            "wound_image_cv": "ochiq sternotomiya dataseti yo'q; SurgWound sinovi rad etildi — guardian/wound_cv.py",
        }
        if low_ef is None:
            blocked["ecg_low_ef"] = "og'irliklar yo'q yoki qabul mezonlaridan o'tmagan (yoki product rejimi) — ecg/low_ef.py"
        return {
            "ecg": card(ecg), "angio": card(angio), "echo_ef": card(ef), "ecg_low_ef": card(low_ef), "ecg_shd": card(shd),
            "ecg_shd_enabled": shd.enabled if shd else [],
            "inr_ocr": {"available": ocr_engine is not None or _ocr_available()},
            "blocked": blocked,
        }

    @app.post("/episodes/{eid}/ecg")
    async def ecg_endpoint(eid: str, actor: str = Form(...), lang: str = Form("uz", pattern="^(uz|ru|en)$"), fs: float = Form(500, gt=50, le=2000),
                           age_years: Optional[float] = Form(None, ge=0, le=120),
                           file: UploadFile = File(..., description="CSV: 1-qator tarmoq nomlari (I,II,...,V6), mV")) -> dict:
        ep = get(eid)
        _need(ecg, "EKG")
        try:
            sig, leads = read_csv(await _read(file, MAX_UPLOAD), fs)
        except ValueError as exc:
            raise HTTPException(422, f"EKG faylini o'qib bo'lmadi: {exc}") from None
        ev = ecg.analyze(sig, fs, leads, age_years)
        out = {"evidence": _save(ep, actor, "ecg.analyze", ev), "plain": plain_ai(ev, lang)}
        _shadow(ep, sig, fs, leads, age_years, ev)      # javob QAYTARILMAYDI, faqat yoziladi
        if low_ef is not None:                       # xuddi shu EKG'dan past EF skriningi (alohida dalil)
            lev = low_ef.analyze(sig, fs, leads, age_years)
            out["low_ef"] = {"evidence": _save(ep, actor, "ecg.low_ef", lev), "plain": plain_ai(lev, lang)}
        if shd is not None:                          # tuzilmaviy kasalliklar (faqat mezondan o'tgan yorliqlar)
            sev = shd.analyze(sig, fs, leads, age_years)
            out["structural"] = {"evidence": _save(ep, actor, "ecg.shd", sev), "plain": plain_ai(sev, lang)}
        if ep.stage == Stage.GUARDIAN_30D:           # POAF / operatsiyadan keyingi nazorat
            esc = escalate(ep.patient_ref, _postop_day(ep, datetime.now(timezone.utc)), [ev], notifier)
            alert = record_alert(store, ep, esc, "guardian.ecg")
            store.save(ep, actor, "guardian.ecg", {"alert": esc.alert.value, "notified": esc.notified,
                                                   "alert_id": alert["id"] if alert else None})
            out["escalation"] = esc.to_dict()
            out["alert_id"] = alert["id"] if alert else None
        return out

    @app.post("/episodes/{eid}/angio")
    async def angio_endpoint(eid: str, actor: str = Form(...), lang: str = Form("uz", pattern="^(uz|ru|en)$"), file: UploadFile = File(...)) -> dict:
        ep = get(eid)
        _need(angio, "Angiografiya")
        try:
            ev = angio.analyze(await _read(file, MAX_UPLOAD))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return {"evidence": _save(ep, actor, "angio.analyze", ev), "plain": plain_ai(ev, lang)}

    @app.post("/episodes/{eid}/guardian/inr-image")
    async def inr_image(eid: str, actor: str = Form(...), lang: str = Form("uz", pattern="^(uz|ru|en)$"), indication: Indication = Form(...),
                        file: UploadFile = File(...)) -> dict:
        ep = get(eid)
        if ep.stage != Stage.GUARDIAN_30D:
            raise HTTPException(409, f"Guardian faqat GUARDIAN_30D bosqichida (hozir: {ep.stage.value})")
        ev = assess_inr_image(await _read(file, MAX_UPLOAD), indication, ocr_engine)
        ep.add(ev)
        esc = escalate(ep.patient_ref, _postop_day(ep, datetime.now(timezone.utc)), [ev], notifier)
        alert = record_alert(store, ep, esc, "guardian.inr_image")
        store.save(ep, actor, "guardian.inr_image", {"alert": esc.alert.value, "notified": esc.notified,
                                                     "alert_id": alert["id"] if alert else None})
        return {"escalation": esc.to_dict(), "evidence": [ev.to_dict()], "plain": plain_ai(ev, lang),
                "alert_id": alert["id"] if alert else None}

    @app.post("/episodes/{eid}/echo-ef")
    async def echo_ef(eid: str, actor: str = Form(...), lang: str = Form("uz", pattern="^(uz|ru|en)$"), age_years: Optional[float] = Form(None, ge=0, le=120),
                      file: UploadFile = File(..., description="ExoKG videosi (apikal 4 kamera)")) -> dict:
        ep = get(eid)
        _need(ef, "ExoKG EF")
        data = await _read(file, MAX_VIDEO)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.avi"
            path.write_bytes(data)
            ev = ef.analyze(path, age_years)
        return {"evidence": _save(ep, actor, "echo.ef", ev), "plain": plain_ai(ev, lang)}
