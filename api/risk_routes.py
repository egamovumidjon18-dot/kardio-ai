"""Operatsiya oldi xavf (Heart Team) endpointlari."""
from __future__ import annotations

from typing import Callable, Optional
from datetime import datetime
import math
from functools import partial
import anyio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from core.episode import Episode, Stage
from core.measurements import measurement_time
from core.model_safety import guarded_inference
from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.store import EpisodeStore
from integration.concordances import aki_concordance, ef_concordance, lvef_evidence
from risk.aki import AKIInput, AKIModel, thakar
from risk.euroscore2 import EuroScoreInput, euroscore2
from risk.protocol import heart_team_protocol
from risk.rachs1 import PROCEDURES, Rachs1Input, rachs1
from risk.kdigo import KDIGOInput, assess_kdigo

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
    lvef_measured_at: Optional[datetime] = None



class KDIGOIn(BaseModel):
    actor: str
    baseline_creatinine: float = Field(gt=0, le=2000, description="µmol/L")
    current_creatinine: float = Field(gt=0, le=2000, description="µmol/L")
    creatinine_48h_rise: Optional[float] = Field(None, ge=0, le=1000)
    urine_output_ml_kg_h: Optional[float] = Field(None, ge=0, le=20)
    urine_hours: Optional[float] = Field(None, ge=0, le=168)
    rrt: bool = False


class BiomarkersIn(BaseModel):
    actor: str
    troponin_0h_ng_l: Optional[float] = Field(None, ge=0, le=100000, description="hs-cTn 0h (ng/L)")
    troponin_1h_ng_l: Optional[float] = Field(None, ge=0, le=100000, description="hs-cTn 1h (ng/L)")
    troponin_3h_ng_l: Optional[float] = Field(None, ge=0, le=100000, description="hs-cTn 3h (ng/L)")
    nt_probnp_pg_ml: Optional[float] = Field(None, ge=0, le=100000, description="NT-proBNP (pg/mL)")
    bnp_pg_ml: Optional[float] = Field(None, ge=0, le=100000, description="BNP (pg/mL)")
    age_years: float = Field(60.0, ge=0, le=130)
    symptoms_onset_hours: float = Field(3.0, ge=0, le=720)
    creatinine_umol_l: Optional[float] = Field(None, ge=0, le=2000)

def register(app: FastAPI, store: EpisodeStore, get: Callable[[str], Episode], aki_model: Optional[AKIModel]) -> None:
    @app.post("/episodes/{eid}/risk")
    async def assess_risk(eid: str, body: RiskIn, request: Request) -> dict:
        ep = get(eid)
        if ep.stage not in (Stage.HEART_TEAM, Stage.ICU):
            raise HTTPException(409, f"xavf baholash HEART_TEAM yoki ICU bosqichida (hozir: {ep.stage.value})")
        raw_es = ((await request.json()).get("euroscore") or {})
        try:
            measured = measurement_time(body.lvef_measured_at)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

        # Bitta bemor — bitta LVEF. AKI blokida u majburiy; EuroSCORE'da berilgan bo'lsa, mos kelishi shart.
        lvef = body.aki.lvef_percent
        if not math.isfinite(lvef) or not 0 < lvef <= 100:
            raise HTTPException(422, "LVEF 0 dan katta va 100% dan oshmasligi kerak")
        for es_key, aki_key in (("female", "female"), ("creatinine_umol_l", "creatinine_umol_l"),
                                ("chronic_lung_disease", "copd"), ("insulin_diabetes", "insulin_diabetes"),
                                ("previous_cardiac_surgery", "previous_cardiac_surgery")):
            if es_key in raw_es and getattr(body.euroscore, es_key) != getattr(body.aki, aki_key):
                raise HTTPException(422, f"ikki blokda {es_key} har xil — bitta bemor uchun qiymatlarni tekshiring")
        if "lvef_percent" in raw_es and abs(float(raw_es["lvef_percent"]) - lvef) > 1e-9:
            raise HTTPException(422, f"LVEF ikki blokda har xil: EuroSCORE {raw_es['lvef_percent']}%, AKI {lvef}% — "
                                     "bitta bemorda bitta qiymat bo'lishi kerak")
        body.euroscore.lvef_percent = lvef

        added = [euroscore2(body.euroscore), thakar(body.aki)]       # tartib: mavjud mijozlar evidence[0] = EuroSCORE'ga tayanadi
        if any(e.abstained for e in added):
            raise HTTPException(422, "; ".join(s for e in added if e.abstained for s in e.explanation))
        if aki_model is not None:
            added.append(await anyio.to_thread.run_sync(
                partial(guarded_inference, aki_model, "risk.aki.model", partial(aki_model.analyze, body.aki)),
                limiter=app.state.inference_limiter))
        added.append(lvef_evidence(lvef, measured))
        missing = [k for k in SILENT_DEFAULTS if k not in raw_es]
        if missing or ep.latest("risk.assumptions") is not None:
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


    @app.post("/episodes/{eid}/kdigo")
    def assess_kdigo_endpoint(eid: str, body: KDIGOIn) -> dict:
        ep = get(eid)
        if ep.stage not in (Stage.ICU, Stage.DISCHARGE, Stage.GUARDIAN_30D):
            raise HTTPException(409, f"KDIGO AKI baholash ICU, DISCHARGE yoki GUARDIAN_30D bosqichida (hozir: {ep.stage.value})")
        ev = assess_kdigo(KDIGOInput(
            baseline_creatinine=body.baseline_creatinine,
            current_creatinine=body.current_creatinine,
            creatinine_48h_rise=body.creatinine_48h_rise,
            urine_output_ml_kg_h=body.urine_output_ml_kg_h,
            urine_hours=body.urine_hours,
            rrt=body.rrt,
        ))
        if ev.abstained:
            raise HTTPException(422, "; ".join(ev.explanation))
        ep.add(ev)
        store.save(ep, body.actor, "risk.kdigo", {"stage": ev.value["stage"], "risk": ev.risk.value})
        return {"evidence": ev.to_dict()}

    @app.post("/episodes/{eid}/biomarkers")
    def biomarkers_endpoint(eid: str, body: BiomarkersIn) -> dict:
        ep = get(eid)
        from risk.biomarkers import BiomarkersInput, assess_biomarkers
        ev = assess_biomarkers(BiomarkersInput(
            troponin_0h_ng_l=body.troponin_0h_ng_l,
            troponin_1h_ng_l=body.troponin_1h_ng_l,
            troponin_3h_ng_l=body.troponin_3h_ng_l,
            nt_probnp_pg_ml=body.nt_probnp_pg_ml,
            bnp_pg_ml=body.bnp_pg_ml,
            age_years=body.age_years,
            symptoms_onset_hours=body.symptoms_onset_hours,
            creatinine_umol_l=body.creatinine_umol_l,
        ))
        if ev.abstained:
            raise HTTPException(422, "; ".join(ev.explanation))
        ep.add(ev)
        store.save(ep, body.actor, "risk.biomarkers", {
            "risk": ev.risk.value,
            "troponin": ev.value.get("troponin_decision"),
            "nt_probnp": ev.value.get("nt_probnp_decision")
        })
        return {"evidence": ev.to_dict()}

    @app.get("/episodes/{eid}/heart-team-protocol", response_class=PlainTextResponse)
    def protocol(eid: str) -> str:
        return heart_team_protocol(get(eid))
