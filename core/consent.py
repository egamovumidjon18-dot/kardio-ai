"""Bemorning yozma klinik roziligi registri (ISO 13485 / SaMD talabi).

O'zbekiston Respublikasi «Fuqarolar sog'lig'ini saqlash to'g'risida»gi Qonuni 24-moddasi
hamda xalqaro tibbiy dasturiy ta'minot (SaMD) standartlari bo'yicha har bir
tibbiy aralashuv va sun'iy intellekt yordamida tahlil o'tkazishdan oldin bemor
(yoki uning qonuniy vakili) tomonidan yozma rozilik olingan bo'lishi shart.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from core.episode import Episode
from core.evidence import Evidence, Provenance, RiskLevel, Source

CONSENT_LAW_REF = (
    "O'zbekiston Respublikasi «Fuqarolar sog'lig'ini saqlash to'g'risida»gi Qonuni 24-moddasi "
    "(Tibbiy aralashuvga rozilik) + SaMD ISO 13485 / IEC 62304 axloqiy talablari"
)


@dataclass
class ConsentInput:
    clinician: str                        # Rozilikni olgan shifokor F.I.Sh. va lavozimi
    paper_ref: str                        # Qog'oz blank/forma raqami (masalan, "ROZ-2026/0412")
    consent_type: str = "treatment_and_ai"# "treatment_and_ai", "research_anonymous", "telemedicine_guardian"
    consented_at: Optional[str] = None    # ISO formatdagi sana, ko'rsatilmasa joriy vaqt
    patient_or_guardian: str = "patient"  # "patient" (bemor o'zi) yoki "guardian" (vasiysi/ota-onasi)
    guardian_relation: Optional[str] = None  # "onasi", "otasi", "turmush o'rtog'i" ...
    notes: Optional[str] = None           # Qo'shimcha klinik qaydlar


def record_clinical_consent(ep: Episode, inp: ConsentInput, actor: str) -> Evidence:
    """Epizodga rasmiy yozma klinik rozilik faktini biriktiradi."""
    if not inp.clinician or not inp.clinician.strip():
        raise ValueError("Rozilikni olgan shifokor F.I.Sh. ko'rsatilishi shart")
    if not inp.paper_ref or not inp.paper_ref.strip():
        raise ValueError("Qog'oz rozilik blanki/registratsiya raqami ko'rsatilishi shart")

    at = inp.consented_at or datetime.now(timezone.utc).isoformat()
    value = {
        "consented": True,
        "clinician": inp.clinician.strip(),
        "paper_ref": inp.paper_ref.strip(),
        "consent_type": inp.consent_type.strip(),
        "consented_at": at,
        "patient_or_guardian": inp.patient_or_guardian,
        "guardian_relation": inp.guardian_relation,
        "notes": inp.notes,
    }

    prov = Provenance(
        name="clinical_consent_registry",
        version="1.0.0",
        reference=CONSENT_LAW_REF,
    )

    expl = [
        f"Yozma rozilik blanki: #{inp.paper_ref.strip()}",
        f"Shifokor: {inp.clinician.strip()}",
        f"Imzolangan sana: {at}",
        f"Rozilik turi: {inp.consent_type}",
        f"Imzolovchi: {inp.patient_or_guardian}" + (f" ({inp.guardian_relation})" if inp.guardian_relation else ""),
    ]

    ev = Evidence(
        kind="consent.clinical",
        value=value,
        source=Source.CLINICIAN,
        provenance=prov,
        risk=RiskLevel.LOW,
        explanation=expl,
    )
    return ev


def get_clinical_consent(ep: Episode) -> Optional[dict[str, Any]]:
    """Epizodda qayd etilgan eng so'nggi yozma rozilik ma'lumotlarini qaytaradi."""
    for ev in reversed(ep.evidence):
        if ev.kind == "consent.clinical" and isinstance(ev.value, dict) and ev.value.get("consented"):
            return ev.value
    return None
