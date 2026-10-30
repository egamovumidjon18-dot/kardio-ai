"""CardioPath AI — FastAPI ilova.

Ishga tushirish:  uvicorn api.main:default_app --factory --port 8010
Muhit: CARDIOPATH_DB (sqlite fayl), CARDIOPATH_WEIGHTS (PCG og'irliklari papkasi),
       CARDIOPATH_AKI_WEIGHTS, CARDIOPATH_MODE=research|product,
       CARDIOPATH_TG_TOKEN + CARDIOPATH_TG_CHAT (Guardian eskalatsiyasi),
       CARDIOPATH_RECORDINGS (rozilik bilan saqlanadigan PCG yozuvlari papkasi),
       CARDIOPATH_ECG_WEIGHTS, CARDIOPATH_ANGIO_WEIGHTS, CARDIOPATH_EF_WEIGHTS (NeuroSon heart_echonet.onnx)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from api import ai_routes, guardian_routes, risk_routes
from core.episode import Episode, Stage, TransitionError
from core.evidence import DISCLAIMER
from core.handoff import Handoff
from core.registry import deploy_mode
from core.store import EpisodeStore, SqliteEpisodeStore, episode_to_dict
from guardian.escalation import LogNotifier, Notifier, TelegramNotifier
from adapters.echo_ef import EchoEFAdapter
from angio.model import AngioModel
from ecg.model import ECGModel
from guardian.ocr import Engine
from risk.aki import AKIModel
from screening.collection import ECHO_DIAGNOSES, echo_diagnosis, save_recordings
from screening.model import LOCATIONS, PCGModel, Recording
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
               ef_model: Optional[EchoEFAdapter] = None, ocr_engine: Optional[Engine] = None) -> FastAPI:
    app = FastAPI(title="CardioPath AI", version="0.1.0",
                  description="Kardiologiya va kardioxirurgiya yagona AI-CDSS platformasi. " + DISCLAIMER)

    def _get(eid: str) -> Episode:
        ep = store.get(eid)
        if ep is None:
            raise HTTPException(404, "epizod topilmadi")
        return ep

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def screening_page() -> str:
        return (Path(__file__).parent / "static" / "screening.html").read_text(encoding="utf-8")

    risk_routes.register(app, store, _get, aki_model)
    notifier = notifier or LogNotifier()
    guardian_routes.register(app, store, _get, notifier)
    ai_routes.register(app, store, _get, notifier, ecg_model, angio_model, ef_model, ocr_engine)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "mode": deploy_mode(),
                "pcg_model": pcg.card.to_dict() if pcg else None,
                "aki_model": aki_model.card.to_dict() if aki_model else None}

    @app.post("/episodes", status_code=201)
    def create_episode(body: EpisodeIn) -> dict:
        ep = Episode(patient_ref=body.patient_ref, population=body.population)
        store.save(ep, body.actor, "episode.create")
        return episode_to_dict(ep)

    @app.get("/episodes/{eid}")
    def get_episode(eid: str) -> dict:
        return episode_to_dict(_get(eid))

    @app.get("/episodes/{eid}/audit")
    def get_audit(eid: str) -> list[dict]:
        _get(eid)
        return store.audit(eid)

    @app.post("/episodes/{eid}/transition")
    def transition(eid: str, body: TransitionIn) -> dict:
        ep = _get(eid)
        handoff = Handoff(**body.model_dump())
        try:
            ep.transition(handoff)
        except TransitionError as exc:
            raise HTTPException(409, str(exc)) from None
        store.save(ep, body.author, "episode.transition", handoff.to_dict())
        return episode_to_dict(ep)

    @app.get("/screening/red-flags")
    def list_red_flags() -> dict:
        return {code: {"name": name, "major": major} for code, (name, major) in RED_FLAGS.items()}

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


def default_app() -> FastAPI:
    """uvicorn api.main:default_app --factory --port 8010"""
    store = SqliteEpisodeStore(os.environ.get("CARDIOPATH_DB", "cardiopath.db"))
    pcg = PCGModel.from_dir(os.environ.get("CARDIOPATH_WEIGHTS", "weights/pcg"))
    aki = AKIModel.from_dir(os.environ.get("CARDIOPATH_AKI_WEIGHTS", "weights/aki"))
    rec_dir = os.environ.get("CARDIOPATH_RECORDINGS")
    return create_app(store, pcg, aki, TelegramNotifier.from_env() or LogNotifier(),
                      Path(rec_dir) if rec_dir else None,
                      ecg_model=ECGModel.from_dir(os.environ.get("CARDIOPATH_ECG_WEIGHTS", "weights/ecg")),
                      angio_model=AngioModel.from_dir(os.environ.get("CARDIOPATH_ANGIO_WEIGHTS", "weights/angio")),
                      ef_model=_load_ef())
