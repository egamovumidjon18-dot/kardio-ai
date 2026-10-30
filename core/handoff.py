"""Handoff — bosqichlar orasidagi tuzilgan yo'llanma paketi.

Kim, qaysi Evidence asosida, qaysi ochiq savollar bilan uzatdi. Bemor
"sarson bo'lmasligi" texnik jihatdan aynan shu.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from core.evidence import utcnow


@dataclass
class Handoff:
    from_stage: str
    to_stage: str
    author: str                                   # shifokor identifikatori
    evidence_ids: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    note: str = ""
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return asdict(self)
