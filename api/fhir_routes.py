"""HL7 FHIR R4 API Marshrutlari (FHIR Ingestion Service).

Kasalxona axborot tizimlari (HIS/LIS) dan FHIR Observation va Bundle
resurslarini qabul qilib, epizodga biomarkerlar va laboratoriya tahlillari
sifatida biriktirish endpointlari.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel

from core.episode import Episode
from core.fhir_ingest import FhirIngestResult, ingest_fhir_data
from core.store import EpisodeStore


def register(app: FastAPI, store: EpisodeStore, get: Callable[[str], Episode]) -> None:
    @app.post("/episodes/{eid}/fhir/ingest")
    def ingest_fhir_to_episode(
        eid: str,
        payload: dict[str, Any] = Body(...),
        actor: str = "fhir_lis_service",
    ) -> dict:
        """Berilgan epizodga HL7 FHIR R4 Observation yoki Bundle resurslarini kiritadi."""
        ep = get(eid)
        try:
            res: FhirIngestResult = ingest_fhir_data(payload=payload, episode=ep, actor=actor)
            if res.success:
                store.save(
                    ep,
                    actor,
                    "fhir.ingest",
                    {
                        "resources_processed": res.resources_processed,
                        "evidence_count": len(res.evidence_created),
                    },
                )
            return res.to_dict()
        except Exception as exc:
            raise HTTPException(422, f"FHIR ma'lumotlarini qabul qilishda xatolik: {exc}") from exc
