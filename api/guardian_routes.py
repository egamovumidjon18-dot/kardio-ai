"""30 kunlik Post-Op Guardian endpointlari (Telegram Mini App / PWA shu yerga yozadi)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from api.alerts import record_alert
from core.episode import Episode, Stage
from core.evidence import Evidence
from core.store import EpisodeStore
from guardian.checkin import vitals_and_symptoms, weight_trend, wound
from guardian.escalation import Notifier, escalate
from guardian.inr import Indication, assess_inr, parse_inr_text


class InrIn(BaseModel):
    actor: str
    indication: Indication
    value: Optional[float] = None
    ocr_text: Optional[str] = Field(None, max_length=5000)


class CheckinIn(BaseModel):
    actor: str
    measured_at: Optional[datetime] = None
    weight_kg: Optional[float] = Field(None, gt=0, lt=400)
    heart_rate: Optional[float] = Field(None, gt=0, lt=300)
    spo2: Optional[float] = Field(None, ge=50, le=100)
    temperature_c: Optional[float] = Field(None, ge=30, le=45)
    symptoms: list[str] = []
    wound_signs: list[str] = []
    fever: bool = False
    photo_ref: Optional[str] = None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _postop_day(ep: Episode, at: datetime) -> Optional[int]:
    start = next((h for h in reversed(ep.handoffs) if h.to_stage == Stage.GUARDIAN_30D.value), None)
    return (at - _aware(datetime.fromisoformat(start.created_at))).days if start else None


def register(app: FastAPI, store: EpisodeStore, get: Callable[[str], Episode], notifier: Notifier) -> None:
    def _guardian(eid: str) -> Episode:
        ep = get(eid)
        if ep.stage != Stage.GUARDIAN_30D:
            raise HTTPException(409, f"Guardian faqat GUARDIAN_30D bosqichida (hozir: {ep.stage.value})")
        return ep

    def _finish(ep: Episode, actor: str, action: str, items: list[Evidence], at: datetime) -> dict:
        for ev in items:
            ep.add(ev)
        esc = escalate(ep.patient_ref, _postop_day(ep, at), items, notifier)
        alert = record_alert(store, ep, esc, action)
        store.save(ep, actor, action, {"alert": esc.alert.value, "notified": esc.notified,
                                       "alert_id": alert["id"] if alert else None})
        return {"escalation": esc.to_dict(), "evidence": [e.to_dict() for e in items],
                "alert_id": alert["id"] if alert else None}

    @app.post("/episodes/{eid}/guardian/inr")
    def inr(eid: str, body: InrIn) -> dict:
        ep = _guardian(eid)
        value = body.value if body.value is not None else parse_inr_text(body.ocr_text or "")
        ev = assess_inr(value, body.indication, body.ocr_text or "")
        return _finish(ep, body.actor, "guardian.inr", [ev], datetime.now(timezone.utc))

    @app.post("/episodes/{eid}/guardian/checkin")
    def checkin(eid: str, body: CheckinIn) -> dict:
        ep = _guardian(eid)
        at = _aware(body.measured_at or datetime.now(timezone.utc))
        items = []
        if body.weight_kg is not None:
            history = [(e.created_at, e.value) for e in ep.evidence if e.kind == "guardian.weight"]
            history = [(_aware(datetime.fromisoformat(d)).isoformat(), w) for d, w in history]
            ev = weight_trend(history + [(at.isoformat(), body.weight_kg)])
            ev.created_at = at.isoformat()            # o'lchov vaqti — keyingi trendlar uchun
            items.append(ev)
        if any(v is not None for v in (body.heart_rate, body.spo2, body.temperature_c)) or body.symptoms:
            items.append(vitals_and_symptoms(body.heart_rate, body.spo2, body.temperature_c, body.symptoms))
        if body.wound_signs or body.photo_ref or body.fever:
            items.append(wound(body.wound_signs, body.fever, body.photo_ref))
        if not items:
            raise HTTPException(422, "check-in bo'sh — kamida bitta ko'rsatkich kiriting")
        return _finish(ep, body.actor, "guardian.checkin", items, at)
