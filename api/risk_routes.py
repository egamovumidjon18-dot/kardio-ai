"""Operatsiya oldi xavf (Heart Team) endpointlari."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from core.episode import Episode, Stage
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.store import EpisodeStore
from integration.concordances import aki_concordance, ef_concordance, lvef_evidence
from risk.aki import AKIInput, AKIModel, thakar
from risk.euroscore2 import EuroScoreInput, euroscore2
from risk.protocol import heart_team_protocol
from risk.rachs1 import PROCEDURES, Rachs1Input, rachs1

# EuroSCORE II'da shifokor kiritmasa jim «eng past xavf» qiymati olinadigan maydonlar (LVEF alohida: AKI blokidan olinadi).
SILENT_DEFAULTS = {
    "nyha": "NYHA I (simptom yo'q)",
    "urgency": "rejali operatsiya",
    "weight_of_intervention": "yagona izolyatsiyalangan KShSh",
    "pa_systolic_mmhg": "o'pka arteriyasi bosimi me'yorda",
}


FIELD_NAMES = {"nyha": "NYHA sinfi", "urgency": "shoshilinchlik", "weight_of_intervention": "aralashuv og'irligi",
               "pa_systolic_mmhg": "o'pka arteriyasi bosimi"}


class Rachs1In(BaseModel):
    actor: str
    procedures: list[str] = Field(min_length=1, max_length=10, description="GET /rachs1/procedures dagi kodlar")
    age_days: float = Field(ge=0, le=36500)
    premature: bool = False


class RiskIn(BaseModel):
    actor: str
    euroscore: EuroScoreInput
    aki: AKIInput


def register(app: FastAPI, store: EpisodeStore, get: Callable[[str], Episode], aki_model: Optional[AKIModel]) -> None:
    @app.post("/episodes/{eid}/risk")
    async def assess_risk(eid: str, body: RiskIn, request: Request) -> dict:
        ep = get(eid)
        if ep.stage not in (Stage.HEART_TEAM, Stage.ICU):
            raise HTTPException(409, f"xavf baholash HEART_TEAM yoki ICU bosqichida (hozir: {ep.stage.value})")
        raw_es = ((await request.json()).get("euroscore") or {})

        # Bitta bemor — bitta LVEF. AKI blokida u majburiy; EuroSCORE'da berilgan bo'lsa, mos kelishi shart.
        lvef = body.aki.lvef_percent
        if "lvef_percent" in raw_es and abs(float(raw_es["lvef_percent"]) - lvef) > 1e-9:
            raise HTTPException(422, f"LVEF ikki blokda har xil: EuroSCORE {raw_es['lvef_percent']}%, AKI {lvef}% — "
                                     "bitta bemorda bitta qiymat bo'lishi kerak")
        body.euroscore.lvef_percent = lvef

        added = [euroscore2(body.euroscore), thakar(body.aki)]       # tartib: mavjud mijozlar evidence[0] = EuroSCORE'ga tayanadi
        if aki_model is not None:
            added.append(aki_model.analyze(body.aki))
        added.append(lvef_evidence(lvef))
        missing = [k for k in SILENT_DEFAULTS if k not in raw_es]
        if missing:
            added.append(Evidence(kind="risk.assumptions", value=missing, source=Source.RULE,
                                  provenance=Provenance(name="euroscore2_defaults", reference="EuroSCORE II"),
                                  risk=RiskLevel.UNKNOWN,
                                  explanation=[f"{FIELD_NAMES[k]}: kiritilmadi → {SILENT_DEFAULTS[k]} deb olindi" for k in missing]))
        for ev in added:
            ep.add(ev)
        conc, ef_conc = aki_concordance(ep), ef_concordance(ep)
        euro = next(e for e in added if e.kind == "risk.euroscore2")
        th = next(e for e in added if e.kind == "risk.aki.rule")
        store.save(ep, body.actor, "risk.assess",
                   {"euroscore2": euro.value, "thakar": th.value,
                    "aki_concordance": conc.status.value if conc else None,
                    "ef_concordance": ef_conc.status.value if ef_conc else None,
                    "assumed_defaults": missing})
        return {"evidence": [e.to_dict() for e in added],
                "aki_concordance": conc.to_dict() if conc else None,
                "ef_concordance": ef_conc.to_dict() if ef_conc else None,
                "assumed_defaults": missing,
                "evidence_ids": [e.id for e in added]}

    @app.get("/rachs1/procedures")
    def rachs1_procedures() -> dict:
        return {"items": [{"code": c, "name": n, "category_le30d": a, "category_gt30d": b}
                          for c, (n, a, b) in PROCEDURES.items()]}

    @app.post("/episodes/{eid}/rachs1")
    def assess_rachs1(eid: str, body: Rachs1In) -> dict:
        ep = get(eid)
        if ep.stage not in (Stage.HEART_TEAM, Stage.ICU):
            raise HTTPException(409, f"xavf baholash HEART_TEAM yoki ICU bosqichida (hozir: {ep.stage.value})")
        ev = rachs1(Rachs1Input(procedures=body.procedures, age_days=body.age_days, premature=body.premature))
        ep.add(ev)
        store.save(ep, body.actor, "risk.rachs1", {"category": ev.value, "procedures": body.procedures, "abstained": ev.abstained})
        return {"evidence": ev.to_dict()}

    @app.get("/episodes/{eid}/heart-team-protocol", response_class=PlainTextResponse)
    def protocol(eid: str) -> str:
        return heart_team_protocol(get(eid))
