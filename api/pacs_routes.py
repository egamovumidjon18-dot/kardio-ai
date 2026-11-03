"""PACS DICOM API Marshrutlari (PACS Ingestion & DICOMweb Service).

Kasalxona PACS arxivi va apparatlaridan (CXR, Angio, ExoKG) DICOM fayllarini
qabul qilish, avtomatik modelga yo'naltirish va epizodga biriktirish endpointlari.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from core.episode import Episode
from core.store import EpisodeStore
from pacs.dicom_parser import is_dicom
from pacs.router import PacsRoutingResult, route_dicom_dataset


def register(
    app: FastAPI,
    store: EpisodeStore,
    get: Callable[[str], Episode],
    cxr_model: Optional[Any] = None,
    angio_model: Optional[Any] = None,
) -> None:
    @app.post("/pacs/dicom")
    async def pacs_dicom_upload(
        file: UploadFile = File(...),
        episode_id: Optional[str] = Form(None),
        actor: str = Form("pacs_operator"),
    ) -> dict:
        """Kasalxona PACS tizimidan DICOM (.dcm) faylini qabul qilib, tegishli modelga yo'naltiradi."""
        content = await file.read()
        if not is_dicom(content):
            raise HTTPException(400, "Yuklangan fayl standart DICOM Part 10 formatida emas ('DICM' belgisi yo'q)")

        try:
            res: PacsRoutingResult = route_dicom_dataset(
                source=content,
                store=store,
                episode_id=episode_id,
                actor=actor,
                cxr_model=cxr_model,
                angio_model=angio_model,
            )
            return res.to_dict()
        except Exception as exc:
            raise HTTPException(422, f"DICOM tahlilida xatolik yuz berdi: {exc}") from exc

    @app.get("/episodes/{eid}/pacs/studies")
    def get_episode_pacs_studies(eid: str) -> list[dict]:
        """Epizodga biriktirilgan barcha DICOM tekshiruvlari va modalitetlar ro'yxati."""
        ep = get(eid)
        studies = []
        for ev in ep.evidence:
            if ev.kind in ("cxr", "cxr.dicom", "angio", "angio.dicom", "echo.dicom", "dicom.study"):
                studies.append({
                    "evidence_id": ev.id,
                    "kind": ev.kind,
                    "risk": ev.risk.value,
                    "created_at": ev.created_at,
                    "provenance": ev.provenance.name,
                    "value": ev.value,
                    "explanation": ev.explanation,
                })
        return studies
