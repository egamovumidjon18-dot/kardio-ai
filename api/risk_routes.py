"""Operatsiya oldi xavf (Heart Team) endpointlari."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core.episode import Episode, Stage
from core.store import EpisodeStore
from risk.aki import AKIInput, AKIModel, thakar
from risk.euroscore2 import EuroScoreInput, euroscore2
from risk.protocol import aki_concordance, heart_team_protocol


class RiskIn(BaseModel):
    actor: str
    euroscore: EuroScoreInput
    aki: AKIInput


def register(app: FastAPI, store: EpisodeStore, get: Callable[[str], Episode], aki_model: Optional[AKIModel]) -> None:
    @app.post("/episodes/{eid}/risk")
    def assess_risk(eid: str, body: RiskIn) -> dict:
        ep = get(eid)
        if ep.stage not in (Stage.HEART_TEAM, Stage.ICU):
            raise HTTPException(409, f"xavf baholash HEART_TEAM yoki ICU bosqichida (hozir: {ep.stage.value})")
        added = [euroscore2(body.euroscore), thakar(body.aki)]
        if aki_model is not None:
            added.append(aki_model.analyze(body.aki))
        for ev in added:
            ep.add(ev)
        conc = aki_concordance(ep)
        store.save(ep, body.actor, "risk.assess",
                   {"euroscore2": added[0].value, "thakar": added[1].value,
                    "aki_concordance": conc.status.value if conc else None})
        return {"evidence": [e.to_dict() for e in added],
                "aki_concordance": conc.to_dict() if conc else None,
                "evidence_ids": [e.id for e in added]}

    @app.get("/episodes/{eid}/heart-team-protocol", response_class=PlainTextResponse)
    def protocol(eid: str) -> str:
        return heart_team_protocol(get(eid))
