"""EKG, angiografiya, MNO-rasm OCR va ExoKG EF endpointlari. Har bir modul ixtiyoriy: ulanmagan bo'lsa 503."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
import logging
from functools import partial
from typing import Callable, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
import anyio

from adapters.echo_ef import EchoEFAdapter
from api.alerts import record_alert
from angio.model import AngioModel
from angio.image import load_gray
from api.ai_plain import plain_ai
from api.guardian_routes import _postop_day
from core.episode import Episode, Stage
from core.measurements import measurement_time
from core.model_safety import guarded_inference
from core.evidence import Evidence
from core.shadow import ShadowRhythmModel, ShadowStore, input_hash
from core.store import EpisodeStore
from ecg.low_ef import LowEFFromECG
from ecg.model import ECGModel
from cxr.model import CXRModel
from ecg.shd import StructuralFromECG
from ecg.signal import read_csv
from guardian.escalation import Alert, Notifier, escalate
from guardian.inr import Indication, parse_inr_text
from guardian.ocr import MIN_CONFIDENCE, Engine, assess_inr_image, rapid_engine, read_text

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
             shadow_store: Optional[ShadowStore] = None, cxr: Optional[CXRModel] = None) -> None:
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
            "ecg": card(ecg), "angio": card(angio), "echo_ef": card(ef), "ecg_low_ef": card(low_ef), "ecg_shd": card(shd), "cxr": card(cxr),
            "ecg_shd_enabled": shd.enabled if shd else [],
            "inr_ocr": {"available": ocr_engine is not None or _ocr_available()},
            "blocked": blocked,
        }

    @app.post("/episodes/{eid}/ecg")
    async def ecg_endpoint(eid: str, actor: str = Form(...), lang: str = Form("uz", pattern="^(uz|ru|en)$"), fs: float = Form(500, gt=50, le=2000),
                           age_years: Optional[float] = Form(None, ge=0, le=120),
                           measured_at: Optional[datetime] = Form(None),
                           file: UploadFile = File(..., description="CSV: 1-qator tarmoq nomlari (I,II,...,V6), mV")) -> dict:
        ep = get(eid)
        _need(ecg, "EKG")
        try:
            measured = measurement_time(measured_at)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if age_years is not None and (ep.population == "pediatric") != (age_years < 18):
            raise HTTPException(422, "yosh va epizod populyatsiyasi mos emas")
        try:
            data = await _read(file, MAX_UPLOAD)
            sig, leads = await anyio.to_thread.run_sync(partial(read_csv, data, fs), limiter=app.state.inference_limiter)
        except ValueError as exc:
            raise HTTPException(422, f"EKG faylini o'qib bo'lmadi: {exc}") from None
        def analyze_bundle():
            results = []
            for key, kind, model in ((None, "ecg.afib", ecg), ("low_ef", "ecg.low_ef", low_ef),
                                     ("structural", "ecg.shd", shd)):
                if model is not None:
                    result = guarded_inference(model, kind, partial(model.analyze, sig, fs, leads, age_years))
                    result.measured_at = measured
                    results.append((key, result))
            from ecg.intervals import measure_intervals
            interv = measure_intervals(sig, fs, leads)
            interv.measured_at = measured
            results.append(("intervals", interv))
            return results

        results = await anyio.to_thread.run_sync(analyze_bundle, limiter=app.state.inference_limiter)
        # Prepare the entire response before writing; store.save commits all model
        # evidence and its audit record in one transaction/revision.
        out = {}
        for key, result in results:
            section = {"evidence": result.to_dict(), "plain": plain_ai(result, lang)}
            if key is None:
                out.update(section)
            else:
                out[key] = section
            ep.add(result)
        store.save(ep, actor, "ecg.analyze", {"results": [
            {"kind": e.kind, "evidence_id": e.id, "abstained": e.abstained, "risk": e.risk.value}
            for _, e in results]})
        ev = results[0][1]
        await anyio.to_thread.run_sync(partial(_shadow, ep, sig, fs, leads, age_years, ev),
                                       limiter=app.state.inference_limiter)
        if ep.stage == Stage.GUARDIAN_30D:           # POAF / operatsiyadan keyingi nazorat
            esc = escalate(ep.patient_ref, _postop_day(ep, datetime.now(timezone.utc)), [ev], notifier)
            alert = store.save_with_alert(
                ep, actor, "guardian.ecg",
                level=esc.alert.value if esc.alert != Alert.GREEN else None,
                reasons=esc.reasons,
                message=esc.message,
                delivered=esc.notified if (esc.message and getattr(notifier, "is_external", True)) else None,
            )
            out["escalation"] = esc.to_dict()
            out["alert_id"] = alert["id"] if alert else None
        return out

    @app.post("/episodes/{eid}/angio")
    async def angio_endpoint(
        eid: str,
        actor: str = Form(...),
        lang: str = Form("uz", pattern="^(uz|ru|en)$"),
        vessel_segment: Optional[str] = Form(None),
        stenosis_percent: Optional[float] = Form(None),
        is_bifurcation: bool = Form(False),
        file: UploadFile = File(...),
    ) -> dict:
        ep = get(eid)
        _need(angio, "Angiografiya")
        try:
            data = await _read(file, MAX_UPLOAD)
            gray = await anyio.to_thread.run_sync(partial(load_gray, data), limiter=app.state.inference_limiter)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        ev = await anyio.to_thread.run_sync(partial(guarded_inference, angio, "angio.stenosis_assist",
                                                   partial(angio.analyze, gray)), limiter=app.state.inference_limiter)
        saved_ev = _save(ep, actor, "angio.analyze", ev)

        anatomy_ev = None
        if vessel_segment and stenosis_percent is not None:
            from angio.vessels import CoronaryLesion, assess_coronary_anatomy
            cands_count = len(ev.value.get("candidates", [])) if (ev and isinstance(ev.value, dict)) else 0
            lesion = CoronaryLesion(vessel=vessel_segment.strip(), stenosis_percent=stenosis_percent, is_bifurcation=is_bifurcation)
            anatomy_ev = assess_coronary_anatomy([lesion], ai_candidate_count=cands_count)
            _save(ep, actor, "angio.anatomy", anatomy_ev)

        return {
            "evidence": saved_ev,
            "plain": plain_ai(ev, lang),
            "anatomy": anatomy_ev.to_dict() if anatomy_ev else None,
        }

    @app.post("/episodes/{eid}/cxr")
    async def cxr_endpoint(
        eid: str,
        actor: str = Form(...),
        lang: str = Form("uz", pattern="^(uz|ru|en)$"),
        view_position: str = Form("PA"),
        file: UploadFile = File(..., description="Frontal ko'krak qafasi rentgenogrammasi (PA/AP)")
    ) -> dict:
        ep = get(eid)
        _need(cxr, "CXR")
        try:
            data = await _read(file, MAX_UPLOAD)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        ev = await anyio.to_thread.run_sync(
            partial(guarded_inference, cxr, "cxr.findings", partial(cxr.predict, data, view_position=view_position)),
            limiter=app.state.inference_limiter
        )
        saved_ev = _save(ep, actor, "cxr.analyze", ev)
        return {
            "evidence": saved_ev,
            "plain": plain_ai(ev, lang),
        }

    @app.post("/episodes/{eid}/guardian/inr-read")
    async def inr_read(eid: str, file: UploadFile = File(...)) -> dict:
        """Faqat o'qish (hech narsa saqlanmaydi): bemor OCR o'qigan raqamni qog'oz bilan solishtirib TASDIQLAYDI,
        keyin /guardian/inr ga yuboradi. Bir nechta raqam yoki past ishonch → value=None (qo'lda kiritadi)."""
        ep = get(eid)
        if ep.stage != Stage.GUARDIAN_30D:
            raise HTTPException(409, f"Guardian faqat GUARDIAN_30D bosqichida (hozir: {ep.stage.value})")
        engine = ocr_engine or rapid_engine()
        if engine is None:
            return {"value": None, "reason": "ocr_unavailable"}
        try:
            res = read_text(await _read(file, MAX_UPLOAD), engine)
        except Exception:                                  # noqa: BLE001 — o'qilmasa, bemor qo'lda kiritadi
            return {"value": None, "reason": "unreadable"}
        if res.n_lines == 0 or res.confidence < MIN_CONFIDENCE:
            return {"value": None, "reason": "low_confidence"}
        v = parse_inr_text(res.text)
        return {"value": v if v is not None and 0.8 <= v <= 12 else None, "reason": None if v is not None else "not_found",
                "text": res.text[:500]}

    @app.post("/episodes/{eid}/guardian/inr-image")
    async def inr_image(eid: str, actor: str = Form(...), lang: str = Form("uz", pattern="^(uz|ru|en)$"), indication: Indication = Form(...),
                        file: UploadFile = File(...)) -> dict:
        ep = get(eid)
        if ep.stage != Stage.GUARDIAN_30D:
            raise HTTPException(409, f"Guardian faqat GUARDIAN_30D bosqichida (hozir: {ep.stage.value})")
        ev = assess_inr_image(await _read(file, MAX_UPLOAD), indication, ocr_engine)
        ep.add(ev)
        esc = escalate(ep.patient_ref, _postop_day(ep, datetime.now(timezone.utc)), [ev], notifier)
        alert = store.save_with_alert(
            ep, actor, "guardian.inr_image",
            level=esc.alert.value if esc.alert != Alert.GREEN else None,
            reasons=esc.reasons,
            message=esc.message,
            delivered=esc.notified if (esc.message and getattr(notifier, "is_external", True)) else None,
        )
        return {"escalation": esc.to_dict(), "evidence": [ev.to_dict()], "plain": plain_ai(ev, lang),
                "alert_id": alert["id"] if alert else None}

    @app.post("/episodes/{eid}/echo-ef")
    async def echo_ef(eid: str, actor: str = Form(...), lang: str = Form("uz", pattern="^(uz|ru|en)$"), age_years: Optional[float] = Form(None, ge=0, le=120),
                      measured_at: Optional[datetime] = Form(None),
                      file: UploadFile = File(..., description="ExoKG videosi (apikal 4 kamera)")) -> dict:
        ep = get(eid)
        _need(ef, "ExoKG EF")
        try:
            measured = measurement_time(measured_at)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if age_years is not None and (ep.population == "pediatric") != (age_years < 18):
            raise HTTPException(422, "yosh va epizod populyatsiyasi mos emas")
        data = await _read(file, MAX_VIDEO)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.avi"
            path.write_bytes(data)
            ev = await anyio.to_thread.run_sync(partial(guarded_inference, ef, "echo.ef", partial(ef.analyze, path, age_years)),
                                                limiter=app.state.inference_limiter)
            ev.measured_at = measured
        return {"evidence": _save(ep, actor, "echo.ef", ev), "plain": plain_ai(ev, lang)}
