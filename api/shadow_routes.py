"""Shadow mode endpointlari: yorliq kutayotgan EKG'lar (model javobisiz), shifokor yorlig'i, umumlashgan hisobot."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from core.shadow import RHYTHM_LABELS, ShadowStore


class LabelIn(BaseModel):
    actor: str
    rhythm: str = Field(description=", ".join(RHYTHM_LABELS))
    note: str = Field("", max_length=300)


def register(app: FastAPI, shadow: ShadowStore, model_keys: list[str]) -> None:
    @app.get("/shadow-ui", response_class=HTMLResponse, include_in_schema=False)
    def page() -> str:
        return (Path(__file__).parent / "static" / "shadow.html").read_text(encoding="utf-8")

    @app.get("/shadow/pending")
    def pending(limit: int = Query(50, ge=1, le=500)) -> dict:
        return {"items": shadow.pending(limit), "labels": list(RHYTHM_LABELS)}

    @app.post("/shadow/{run_id}/label")
    def label(run_id: int, body: LabelIn) -> dict:
        try:
            ok = shadow.label(run_id, body.rhythm, body.actor, body.note)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if not ok:
            raise HTTPException(404, "shadow yozuvi topilmadi")
        return {"run_id": run_id, "rhythm": body.rhythm}

    @app.get("/shadow/report")
    def report() -> dict:
        return {"shadow_models": model_keys, **shadow.report()}
