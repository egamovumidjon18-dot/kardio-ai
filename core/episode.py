"""CardiacEpisode — bemorning bitta uzluksiz klinik yo'li (holat mashinasi).

5 bo'g'in shu epizodning bosqichlari. Bosqichlar bir-birini bevosita
chaqirmaydi: hammasi umumiy Evidence vaqt chizig'iga yozadi.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from core.evidence import Evidence, utcnow
from core.handoff import Handoff


class Stage(str, Enum):
    SCREENING = "screening"        # [1] birlamchi / pediatrik skrining
    WORKUP = "workup"              # [2,3] ExoKG, angiografiya
    HEART_TEAM = "heart_team"      # [4] operatsiya oldi xavf + konsilium
    PROCEDURE = "procedure"        # operatsiya / intervensiya
    ICU = "icu"                    # [4] reanimatsiya
    DISCHARGE = "discharge"
    GUARDIAN_30D = "guardian_30d"  # [5] uy monitoringi
    CLOSED = "closed"


ALLOWED: dict[Stage, set[Stage]] = {
    Stage.SCREENING: {Stage.WORKUP, Stage.CLOSED},
    Stage.WORKUP: {Stage.HEART_TEAM, Stage.CLOSED},
    Stage.HEART_TEAM: {Stage.PROCEDURE, Stage.WORKUP, Stage.CLOSED},  # CLOSED = medikamentoz
    Stage.PROCEDURE: {Stage.ICU},
    Stage.ICU: {Stage.DISCHARGE},
    Stage.DISCHARGE: {Stage.GUARDIAN_30D},
    Stage.GUARDIAN_30D: {Stage.CLOSED, Stage.WORKUP, Stage.ICU},  # qayta yotqizish
    Stage.CLOSED: set(),
}


class TransitionError(ValueError):
    pass


@dataclass
class Episode:
    patient_ref: str               # psevdonim — real F.I.Sh. emas
    population: str = "pediatric"  # "pediatric" | "adult"
    stage: Stage = Stage.SCREENING
    evidence: list[Evidence] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=utcnow)

    def add(self, ev: Evidence) -> Evidence:
        self.evidence.append(ev)
        return ev

    def latest(self, kind: str) -> Evidence | None:
        for ev in reversed(self.evidence):
            if ev.kind == kind:
                return ev
        return None

    def transition(self, handoff: Handoff) -> None:
        if handoff.from_stage != self.stage.value:
            raise TransitionError(f"epizod {self.stage.value} bosqichida, {handoff.from_stage} emas")
        try:
            target = Stage(handoff.to_stage)
        except ValueError:
            raise TransitionError(f"noma'lum bosqich: {handoff.to_stage}") from None
        if target not in ALLOWED[self.stage]:
            raise TransitionError(f"{self.stage.value} → {target.value} o'tishi ruxsat etilmagan")
        known = {e.id for e in self.evidence}
        missing = [eid for eid in handoff.evidence_ids if eid not in known]
        if missing:
            raise TransitionError(f"yo'llanmada noma'lum evidence: {missing}")
        self.handoffs.append(handoff)
        self.stage = target
