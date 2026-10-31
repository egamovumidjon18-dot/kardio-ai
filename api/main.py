"""CardioPath AI — FastAPI ilova.

Ishga tushirish:  uvicorn api.main:default_app --factory --port 8010
Muhit: CARDIOPATH_DB (sqlite fayl), CARDIOPATH_WEIGHTS (PCG og'irliklari papkasi),
       CARDIOPATH_AKI_WEIGHTS, CARDIOPATH_MODE=research|product,
       CARDIOPATH_TG_TOKEN + CARDIOPATH_TG_CHAT (Guardian eskalatsiyasi),
       CARDIOPATH_RECORDINGS (rozilik bilan saqlanadigan PCG yozuvlari papkasi),
       CARDIOPATH_ECG_WEIGHTS, CARDIOPATH_ANGIO_WEIGHTS, CARDIOPATH_EF_WEIGHTS (NeuroSon heart_echonet.onnx),
       CARDIOPATH_SHADOW (vergul bilan shadow model papkalari; bo'sh qiymat — o'chiq),
       CARDIOPATH_LEARNING_EVERY_H + CARDIOPATH_CIRCOR_DIR (o'z-o'zini o'rgatish jadvali; nomzod faqat tasdiq bilan)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fastapi import Depends

from api import ai_routes, auth_routes, guardian_routes, learning_routes, risk_routes, shadow_routes
from core.auth import AuthService
from core.identity import effective_actor
from learning.versions import resolve_weights_dir
from api import alerts as alerts_api
from integration.digest import episode_digest
from core.episode import Episode, Stage, TransitionError
from core.evidence import DISCLAIMER
from core.handoff import Handoff
from core.registry import deploy_mode
from core.store import EpisodeConflict, EpisodeStore, SqliteEpisodeStore, episode_to_dict
from guardian.escalation import LogNotifier, Notifier, TelegramNotifier
from adapters.echo_ef import EchoEFAdapter
from angio.model import AngioModel
from ecg.low_ef import LowEFFromECG
from ecg.model import ECGModel
from core.shadow import ShadowRhythmModel, ShadowStore
from ecg.shd import StructuralFromECG
from guardian.ocr import Engine
from risk.aki import AKIModel
from screening.collection import ECHO_DIAGNOSES, echo_diagnosis, save_recordings
from screening.model import LOCATIONS, PCGModel, Recording
from screening.plain import LANGS, flag_name, lang_of, plain_report
from screening.rules import RED_FLAGS, newborn_pulse_ox, red_flags, resting_spo2
from screening.triage import triage


class EpisodeIn(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=64, description="psevdonim, F.I.Sh. emas")
    population: str = Field(default="pediatric", pattern="^(pediatric|adult)$")
    actor: str = "unknown"


class TransitionIn(BaseModel):
    from_stage: str
    to_stage: str
    author: str
    evidence_ids: list[str] = []
    open_questions: list[str] = []
    note: str = ""


def _location(filename: str) -> str:
    """'2530_MV.wav' / '50782_MV_1.wav' / 'MV.wav' → 'MV'."""
    for token in Path(filename or "").stem.split("_"):
        if token in LOCATIONS:
            return token
    raise HTTPException(422, f"fayl nomidan auskultatsiya nuqtasi aniqlanmadi: {filename!r} "
                             f"(kutilgan: {', '.join(LOCATIONS)})")


class EchoIn(BaseModel):
    actor: str
    diagnosis: str = Field(description=", ".join(ECHO_DIAGNOSES))
    notes: str = Field("", max_length=500)


def create_app(store: EpisodeStore, pcg: Optional[PCGModel], aki_model: Optional[AKIModel] = None,
               notifier: Optional[Notifier] = None, recordings_dir: Optional[Path] = None,
               ecg_model: Optional[ECGModel] = None, angio_model: Optional[AngioModel] = None,
               ef_model: Optional[EchoEFAdapter] = None, ocr_engine: Optional[Engine] = None,
               models_dir: Optional[Path] = None, running_version: str = "baseline",
               auth: Optional[AuthService] = None, low_ef_model: Optional[LowEFFromECG] = None,
               shd_model: Optional[StructuralFromECG] = None, shadow_models: Optional[list[ShadowRhythmModel]] = None,
               shadow_store: Optional[ShadowStore] = None, delivery_retry_s: Optional[float] = None,
               learning_runner=None, learning_every_h: float = 0) -> FastAPI:
    # Kirish yoqilgan bo'lsa: har bir so'rov huquq jadvali bo'yicha tekshiriladi; API hujjatlari (/docs) ochiq qolmaydi.
    app = FastAPI(title="CardioPath AI", version="0.1.0",
                  description="Kardiologiya va kardioxirurgiya yagona AI-CDSS platformasi. " + DISCLAIMER,
                  dependencies=[Depends(auth_routes.make_dependency(auth))] if auth else None,
                  docs_url=None if auth else "/docs", redoc_url=None if auth else "/redoc",
                  openapi_url=None if auth else "/openapi.json")

    # Bitta bemorga keladigan o'zgartiruvchi so'rovlar navbat bilan bajariladi (o'qish → o'zgartirish → saqlash aralashmasin).
    # Bu bitta jarayon ichida; bir necha jarayon/server uchun store'dagi versiya tekshiruvi (EpisodeConflict) xavfsizlik to'ri.
    import re as _re
    import threading as _th

    import anyio
    _ep_locks: dict[str, _th.Lock] = {}
    _ep_locks_guard = _th.Lock()
    _ep_path = _re.compile(r"^/episodes/([^/]+)/")

    @app.middleware("http")
    async def serialize_episode_writes(request, call_next):
        m = _ep_path.match(request.url.path) if request.method != "GET" else None
        if not m:
            return await call_next(request)
        with _ep_locks_guard:
            lock = _ep_locks.setdefault(m.group(1), _th.Lock())
        await anyio.to_thread.run_sync(lock.acquire)          # hodisalar siklini bloklamasdan kutish
        try:
            return await call_next(request)
        finally:
            lock.release()

    @app.exception_handler(EpisodeConflict)
    async def _conflict(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.middleware("http")
    async def no_stale_pages(request, call_next):
        # HTML sahifalar keshlanmasin: yangilangandan keyin shifokor eski interfeysni ko'rmasin
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    def _get(eid: str) -> Episode:
        ep = store.get(eid)
        if ep is None:
            raise HTTPException(404, "epizod topilmadi")
        return ep

    # dizayn tizimi (cardiopath.css / .js): bemor ma'lumoti yo'q, kirishsiz ham ochiq
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/models-ui", response_class=HTMLResponse, include_in_schema=False)
    def models_page() -> str:
        return (Path(__file__).parent / "static" / "models.html").read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def app_page() -> str:
        return (Path(__file__).parent / "static" / "app.html").read_text(encoding="utf-8")

    @app.get("/guardian", response_class=HTMLResponse, include_in_schema=False)
    def guardian_page() -> str:
        """Bemor (yoki oila a'zosi) uchun uy kuzatuvi sahifasi: ?e=<epizod> yoki bemor login'i."""
        return (Path(__file__).parent / "static" / "guardian.html").read_text(encoding="utf-8")

    @app.get("/screening", response_class=HTMLResponse, include_in_schema=False)
    def screening_page() -> str:
        return (Path(__file__).parent / "static" / "screening.html").read_text(encoding="utf-8")

    risk_routes.register(app, store, _get, aki_model)
    notifier = notifier or LogNotifier()
    guardian_routes.register(app, store, _get, notifier)
    ai_routes.register(app, store, _get, notifier, ecg_model, angio_model, ef_model, ocr_engine, low_ef=low_ef_model, shd=shd_model,
                       shadow_models=shadow_models, shadow_store=shadow_store)
    if shadow_store is not None:
        shadow_routes.register(app, shadow_store, [m.key for m in shadow_models or []])
    alerts_api.register(app, store, _get, notifier)
    auth_routes.register_status(app, auth is not None)
    if auth is not None:
        auth_routes.register(app, auth, store)
    if models_dir is not None:
        learning_routes.register(app, store, models_dir, recordings_dir, running_version, auth_enabled=auth is not None)

    if delivery_retry_s:
        import asyncio
        import logging

        @app.on_event("startup")
        async def _delivery_loop() -> None:
            async def loop() -> None:
                while True:
                    try:
                        await asyncio.to_thread(alerts_api.retry_deliveries, store, notifier)
                    except Exception as exc:          # noqa: BLE001 — navbat to'xtab qolmasin
                        logging.getLogger("cardiopath.alerts").warning("qayta yuborish xatosi: %s", exc)
                    await asyncio.sleep(delivery_retry_s)
            app.state.delivery_task = asyncio.create_task(loop())

    if learning_runner is not None and learning_every_h > 0 and models_dir is not None:
        import asyncio
        from learning.schedule import maybe_run_cycle

        @app.on_event("startup")
        async def _learning_loop() -> None:
            async def loop() -> None:
                while True:
                    try:                              # soatda bir tekshiradi; nomzod faqat tasdiq uchun tayyorlanadi
                        await asyncio.to_thread(maybe_run_cycle, store, recordings_dir, models_dir, learning_every_h, learning_runner)
                    except Exception as exc:          # noqa: BLE001
                        import logging
                        logging.getLogger("cardiopath.learning").warning("sikl xatosi: %s", exc)
                    await asyncio.sleep(3600)
            app.state.learning_task = asyncio.create_task(loop())

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "mode": deploy_mode(), "pcg_version": running_version, "auth": "on" if auth else "off",
                "pcg_model": pcg.card.to_dict() if pcg else None,
                "aki_model": aki_model.card.to_dict() if aki_model else None}

    @app.post("/episodes", status_code=201)
    def create_episode(body: EpisodeIn) -> dict:
        ep = Episode(patient_ref=body.patient_ref, population=body.population)
        store.save(ep, body.actor, "episode.create")
        return episode_to_dict(ep)

    @app.get("/episodes")
    def list_episodes(stage: Optional[str] = None, q: Optional[str] = Query(None, max_length=64),
                      limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict:
        """Bemorlar (epizodlar) ro'yxati: yangisi birinchi; `stage` bo'yicha filtr, `q` — bemor kodidan qidiruv."""
        if stage is not None and stage not in {s.value for s in Stage}:
            raise HTTPException(422, f"noma'lum bosqich: {stage}")
        total, items = store.summaries(stage=stage, q=q.strip() if q else None, limit=limit, offset=offset)
        for it in items:                              # ekran uchun: umumiy xavf va muhokama punktlari soni
            ep = store.get(it["id"])
            d = episode_digest(ep) if ep else None
            it["overall_risk"] = d["overall_risk"] if d else None
            it["n_discussion"] = len(d["discussion"]) if d else 0
        return {"total": total, "limit": limit, "offset": offset, "items": items}

    @app.get("/episodes/{eid}")
    def get_episode(eid: str) -> dict:
        return episode_to_dict(_get(eid))

    @app.get("/episodes/{eid}/digest")
    def get_digest(eid: str) -> dict:
        """Bir bemorning barcha qoida va AI natijalari, zidliklar, muhokama punktlari, ochiq signallar — bitta javobda."""
        ep = _get(eid)
        _, open_alerts = store.alerts(status="open", episode_id=eid, limit=200)
        return episode_digest(ep, open_alerts)

    @app.get("/episodes/{eid}/audit")
    def get_audit(eid: str) -> list[dict]:
        _get(eid)
        return store.audit(eid)

    @app.post("/episodes/{eid}/transition")
    def transition(eid: str, body: TransitionIn) -> dict:
        ep = _get(eid)
        handoff = Handoff(**{**body.model_dump(), "author": effective_actor(body.author)})   # kirish yoqilgan bo'lsa — haqiqiy foydalanuvchi
        try:
            ep.transition(handoff)
        except TransitionError as exc:
            raise HTTPException(409, str(exc)) from None
        store.save(ep, body.author, "episode.transition", handoff.to_dict())
        return episode_to_dict(ep)

    @app.get("/screening/red-flags")
    def list_red_flags(lang: str = "uz") -> dict:
        L = lang_of(lang)
        return {code: {"name": flag_name(code, L), "major": major} for code, (_, major) in RED_FLAGS.items()}

    @app.post("/episodes/{eid}/screening")
    async def screening(
        eid: str,
        actor: str = Form(...),
        right_hand_spo2: Optional[float] = Form(None),
        foot_spo2: Optional[float] = Form(None),
        attempt: int = Form(1),
        age_hours: Optional[float] = Form(None),
        age_days: Optional[float] = Form(None, ge=0, le=365 * 21),
        resting: Optional[float] = Form(None, alias="resting_spo2"),
        flags: str = Form("", alias="red_flags", description="vergul bilan: cyanosis,hepatomegaly"),
        research_consent: bool = Form(False, description="ota-ona yozma roziligi — yozuvlar saqlanadi"),
        device: str = Form("", max_length=80, description="stetoskop modeli"),
        lang: str = Form("uz", pattern="^(uz|ru|en)$"),
        recordings: list[UploadFile] = File(default=[]),
    ) -> dict:
        ep = _get(eid)
        if ep.stage != Stage.SCREENING:
            raise HTTPException(409, f"skrining faqat SCREENING bosqichida (hozir: {ep.stage.value})")
        if (right_hand_spo2 is None) != (foot_spo2 is None):
            raise HTTPException(422, "CCHD skriningi uchun o'ng qo'l va oyoq SpO₂ ikkalasi kerak")

        rule_items = []
        if right_hand_spo2 is not None:
            rule_items.append(newborn_pulse_ox(right_hand_spo2, foot_spo2, attempt, age_hours))
        if resting is not None:
            rule_items.append(resting_spo2(resting))
        rule_items.append(red_flags([c.strip() for c in flags.split(",") if c.strip()]))

        raw = [(_location(f.filename), await f.read()) for f in recordings]
        if age_days is None and age_hours is not None:
            age_days = age_hours / 24
        pcg_ev = None
        if raw and pcg is not None:
            try:
                pcg_ev = pcg.analyze([Recording(loc, data) for loc, data in raw], age_days=age_days)
            except ValueError as exc:  # buzilgan WAV
                raise HTTPException(422, f"audio faylni o'qib bo'lmadi: {exc}") from None

        saved = None
        if raw and research_consent:
            if recordings_dir is None:
                raise HTTPException(409, "yozuvlarni saqlash o'chirilgan (CARDIOPATH_RECORDINGS sozlanmagan)")
            saved = save_recordings(recordings_dir, ep.id, raw, age_days, device)

        result = triage(rule_items, pcg_ev)
        added = [*rule_items, result.rule, *([pcg_ev] if pcg_ev else []), result.summary, *([saved] if saved else [])]
        for ev in added:
            ep.add(ev)
        store.save(ep, actor, "screening.triage",
                   {"final_risk": result.concordance.final_risk.value,
                    "concordance": result.concordance.status.value,
                    "pcg_uploaded": len(recordings), "pcg_model": pcg is not None,
                    "saved_for_research": saved is not None})
        out = result.to_dict()
        out["episode_id"] = ep.id
        out["evidence_ids"] = [e.id for e in added]
        if recordings and pcg is None:
            out["warning"] = "PCG modeli ulanmagan — audio tahlil qilinmadi, faqat qoidalar ishladi."
        out["saved_for_research"] = saved is not None
        out["plain"] = plain_report(result, rule_items, pcg_ev, len(raw), pcg is not None, lang)
        # sahifada til almashtirilganda qayta so'rov kerak bo'lmasin
        out["plain_i18n"] = {L: plain_report(result, rule_items, pcg_ev, len(raw), pcg is not None, L) for L in LANGS}
        return out

    @app.post("/episodes/{eid}/echo-diagnosis")
    def echo_dx(eid: str, body: EchoIn) -> dict:
        ep = _get(eid)
        if ep.stage not in (Stage.SCREENING, Stage.WORKUP):
            raise HTTPException(409, f"ExoKG tashxisi SCREENING/WORKUP bosqichida kiritiladi (hozir: {ep.stage.value})")
        try:
            ev = ep.add(echo_diagnosis(body.diagnosis, body.notes))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        store.save(ep, body.actor, "workup.echo_dx", {"diagnosis": ev.value})
        return ev.to_dict()

    return app


def _load_ef() -> Optional[EchoEFAdapter]:
    """EchoNet litsenziyasi product rejimida ruxsat bermaydi — o'sha holda modul o'chiriladi."""
    from core.registry import LicenseError

    try:
        return EchoEFAdapter.from_env()
    except LicenseError:
        return None


def _load_low_ef() -> Optional[LowEFFromECG]:
    """EchoNext litsenziyasi faqat tadqiqot — product rejimida modul o'chiriladi."""
    from core.registry import LicenseError

    try:
        return LowEFFromECG.from_dir(os.environ.get("CARDIOPATH_LOWEF_WEIGHTS", "weights/ecg_lowef"))
    except LicenseError:
        return None


def _load_shd() -> Optional[StructuralFromECG]:
    from core.registry import LicenseError

    try:
        return StructuralFromECG.from_dir(os.environ.get("CARDIOPATH_SHD_WEIGHTS", "weights/ecg_shd"))
    except LicenseError:
        return None


def _load_shadow() -> list[ShadowRhythmModel]:
    """Shadow modellar: javobi hech kimga ko'rsatilmaydi, faqat shifokor yorlig'i bilan solishtirish uchun yoziladi."""
    from core.registry import LicenseError

    out = []
    for d in filter(None, (x.strip() for x in os.environ.get("CARDIOPATH_SHADOW", "weights/ecg_afib_multi2").split(","))):
        try:
            m = ShadowRhythmModel.from_dir(d)
        except LicenseError:
            m = None
        if m is not None:
            out.append(m)
    return out


def _load_auth(db_path: str, store: EpisodeStore) -> Optional[AuthService]:
    """CARDIOPATH_AUTH=on bo'lsa kirish yoqiladi. Administrator bo'lmasa, ishga tushmaydi (tizim qulflanib qolmasin)."""
    if os.environ.get("CARDIOPATH_AUTH", "off").strip().lower() not in ("on", "1", "true", "yes"):
        return None
    auth = AuthService(db_path, log=store.log_event)
    if not auth.has_admin():
        raise SystemExit("CARDIOPATH_AUTH=on, lekin faol administrator yo'q. Avval yarating:\n"
                         "  python -m core.auth_cli create-user --username <nom> --role admin")
    return auth


def default_app() -> FastAPI:
    """uvicorn api.main:default_app --factory --port 8010"""
    db_path = os.environ.get("CARDIOPATH_DB", "cardiopath.db")
    store = SqliteEpisodeStore(db_path)
    auth = _load_auth(db_path, store)
    # PCG og'irliklari: aniq ko'rsatilgan (CARDIOPATH_WEIGHTS) > shifokor tasdiqlagan joriy versiya > bazaviy weights/pcg
    models_dir = Path(os.environ.get("CARDIOPATH_MODELS", "models/pcg"))
    weights_dir, running = resolve_weights_dir("weights/pcg", models_dir, os.environ.get("CARDIOPATH_WEIGHTS"))
    pcg = PCGModel.from_dir(weights_dir)
    aki = AKIModel.from_dir(os.environ.get("CARDIOPATH_AKI_WEIGHTS", "weights/aki"))
    rec_dir = os.environ.get("CARDIOPATH_RECORDINGS")
    every_h = float(os.environ.get("CARDIOPATH_LEARNING_EVERY_H", "0") or 0)
    circor = os.environ.get("CARDIOPATH_CIRCOR_DIR")
    runner = None
    if every_h > 0 and rec_dir and circor:
        from learning.schedule import real_runner
        runner = real_runner(store, Path(rec_dir), models_dir, Path(circor))
    return create_app(store, pcg, aki, TelegramNotifier.from_env() or LogNotifier(),
                      Path(rec_dir) if rec_dir else None, models_dir=models_dir, running_version=running,
                      ecg_model=ECGModel.from_dir(os.environ.get("CARDIOPATH_ECG_WEIGHTS", "weights/ecg")),
                      angio_model=AngioModel.from_dir(os.environ.get("CARDIOPATH_ANGIO_WEIGHTS", "weights/angio")),
                      ef_model=_load_ef(), auth=auth, low_ef_model=_load_low_ef(), shd_model=_load_shd(),
                      shadow_models=_load_shadow(), shadow_store=ShadowStore(db_path), delivery_retry_s=60,
                      learning_runner=runner, learning_every_h=every_h)
