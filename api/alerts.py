"""Signallar (alerts): Guardian eskalatsiyalari saqlanadi, jarroh/navbatchi ko'radi va «qabul qildim» deb belgilaydi.

Telegram xabari bir martalik; bu esa doimiy ro'yxat: xabar o'tib ketsa ham ochiq signal yo'qolmaydi.
Eskalatsiya YASHIL bo'lsa, signal yaratilmaydi.
"""
from __future__ import annotations

from typing import Callable, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from core.episode import Episode
from core.store import AlertAckError, EpisodeStore
from guardian.escalation import Alert, Escalation


def record_alert(store: EpisodeStore, ep: Episode, esc: Escalation, source: str) -> Optional[dict]:
    """Sariq yoki qizil eskalatsiyani saqlaydi; yashil bo'lsa None."""
    if esc.alert == Alert.GREEN:
        return None
    return store.add_alert(ep.id, ep.patient_ref, esc.alert.value, source, esc.reasons)


class AckIn(BaseModel):
    actor: str = Field(min_length=1, max_length=64)
    note: str = Field("", max_length=500)


def register(app: FastAPI, store: EpisodeStore, get: Callable[[str], Episode]) -> None:
    @app.get("/alerts")
    def list_alerts(status: Literal["open", "acknowledged", "all"] = "open",
                    level: Optional[Literal["red", "amber"]] = None, episode_id: Optional[str] = None,
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict:
        """Ochiq signallar: avval qizil, keyin eng yangisi. Qabul qilinganlari `status=acknowledged`."""
        total, items = store.alerts(status=status, level=level, episode_id=episode_id, limit=limit, offset=offset)
        return {"total": total, "limit": limit, "offset": offset, "items": items}

    @app.post("/alerts/{alert_id}/ack")
    def ack_alert(alert_id: int, body: AckIn) -> dict:
        try:
            alert = store.ack_alert(alert_id, body.actor.strip(), body.note.strip())
        except AlertAckError as exc:
            raise HTTPException(409, str(exc)) from None
        if alert is None:
            raise HTTPException(404, "signal topilmadi")
        return alert

    @app.get("/episodes/{eid}/alerts")
    def episode_alerts(eid: str, status: Literal["open", "acknowledged", "all"] = "all") -> dict:
        get(eid)
        total, items = store.alerts(status=status, episode_id=eid, limit=200)
        return {"total": total, "items": items}
