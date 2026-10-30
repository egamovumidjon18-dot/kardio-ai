"""Evidence — platformadagi har qanday natijaning yagona shakli.

EF 38%, MNO 1.8, EuroSCORE II 4.2%, PCG "patologik shovqin" — barchasi bitta
`Evidence` bo'lib epizod vaqt chizig'iga yoziladi. NeuroSon `Finding`ning
modallikdan mustaqil umumlashmasi.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# Har bir chiqishga qo'shiladi — yakuniy tashxis EMAS.
DISCLAIMER = (
    "Bu natija sun'iy intellekt va klinik qoidalar yordamchisi tomonidan "
    "tayyorlangan va YAKUNIY TASHXIS EMAS. Qaror faqat shifokor tomonidan "
    "qabul qilinadi. Tadqiqot rejimi (research use only)."
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Source(str, Enum):
    RULE = "rule"            # deterministik shkala / guideline
    MODEL = "model"          # o'qitilgan AI model
    CLINICIAN = "clinician"  # shifokor kiritgan
    PATIENT = "patient"      # bemor o'zi kiritgan (Guardian)


class RiskLevel(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    UNKNOWN = "unknown"


# Concordance uchun tartib (UNKNOWN taqqoslanmaydi).
RISK_ORDER = [RiskLevel.NORMAL, RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.VERY_HIGH]


def risk_rank(level: RiskLevel) -> Optional[int]:
    return RISK_ORDER.index(level) if level in RISK_ORDER else None


@dataclass
class Provenance:
    """Natija qayerdan keldi — maqola va audit uchun majburiy."""

    name: str                      # "cchd_spo2", "pcg_cnn", ...
    version: str = "0.1.0"
    reference: str = ""            # nashr / guideline
    dataset_license: str = ""      # model bo'lsa: o'qitilgan dataset litsenziyasi


@dataclass
class Evidence:
    kind: str                      # "screening.cchd", "screening.pcg" ...
    value: Any
    source: Source
    provenance: Provenance
    unit: str = ""
    risk: RiskLevel = RiskLevel.UNKNOWN
    uncertainty: Optional[float] = None
    abstained: bool = False        # ishonchsiz → qaror chiqarmaydi
    explanation: list[str] = field(default_factory=list)  # qoida izi / abstain sababi
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        d = dict(d)
        d["source"] = Source(d["source"])
        d["risk"] = RiskLevel(d["risk"])
        d["provenance"] = Provenance(**d["provenance"])
        return cls(**d)

    @classmethod
    def abstain(cls, kind: str, source: Source, provenance: Provenance, reason: str,
                value: Any = None) -> "Evidence":
        return cls(kind=kind, value=value, source=source, provenance=provenance,
                   abstained=True, explanation=[reason])
