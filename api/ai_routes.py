"""EKG, angiografiya, MNO-rasm OCR va ExoKG EF endpointlari. Har bir modul ixtiyoriy: ulanmagan bo'lsa 503."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from adapters.echo_ef import EchoEFAdapter
from api.alerts import record_alert
from angio.model import AngioModel
from api.ai_plain import plain_ai
from api.guardian_routes import _postop_day
from core.episode import Episode, Stage
from core.evidence import Evidence
from core.store import EpisodeStore
from ecg.model import ECGModel
from ecg.signal import read_csv
from guardian.escalation import Notifier, escalate
from guardian.inr import Indication
from guardian.ocr import Engine, assess_inr_image

MAX_UPLOAD = 25 * 1024 * 1024
MAX_VIDEO = 100 * 1024 * 1024


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
             ocr_engine: Optional[Engine] = None) -> None:
    def _need(model, name: str) -> None:
        if model is None:
            raise HTTPException(503, f"{name} moduli ulanmagan (og'irliklar yo'q) — qoidalar ishlashda davom etadi")

    def _save(ep: Episode, actor: str, action: str, ev: Evidence) -> dict:
        ep.add(ev)
        store.save(ep, actor, action, {"kind": ev.kind, "abstained": ev.abstained, "risk": ev.risk.value})
        return ev.to_dict()

    @app.get("/models")
    def models() -> dict:
        def card(m):
            return m.card.to_dict() if m else None
        return {
            "ecg": card(ecg), "angio": card(angio), "echo_ef": card(ef),
            "inr_ocr": {"available": ocr_engine is not None or _ocr_available()},
            "blocked": {
                "csa_aki_ml": "MIMIC-IV (PhysioNet credentialed) kerak — risk/aki.py AKIModel interfeysi tayyor",
                "ecg_low_ef": "MIMIC-IV-ECHO/ECG (PhysioNet credentialed) kerak — ecg/low_ef.py",
                "wound_image_cv": "ochiq sternotomiya dataseti yo'q — guardian/wound_cv.py",
            },
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
