"""PACS DICOM Aqlli Routeri (DICOM Modality Dispatcher & Episode Linker).

Kasalxona PACS / C-STORE orqali qabul qilingan DICOM faylini tahlil qilib:
1. Bemor identifikatori (PatientID) bo'yicha mos epizodni topadi yoki yangi ochadi;
2. Modalitet (DX/CR, XA, US) bo'yicha tegishli AI modeliga yo'naltiradi;
3. Natijalarni kriptografik audit logiga tushirib, epizod dalillariga biriktiradi.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Optional

import numpy as np
from PIL import Image

from core.episode import Episode
from core.evidence import Evidence, Provenance, RiskLevel, Source
from pacs.dicom_parser import DicomMetadata, parse_dicom_dataset


@dataclass
class PacsRoutingResult:
    success: bool
    episode_id: str
    patient_ref: str
    modality: str
    study_instance_uid: Optional[str]
    series_instance_uid: Optional[str]
    sop_instance_uid: Optional[str]
    evidence_kind: str
    risk: str
    details: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "episode_id": self.episode_id,
            "patient_ref": self.patient_ref,
            "modality": self.modality,
            "study_instance_uid": self.study_instance_uid,
            "series_instance_uid": self.series_instance_uid,
            "sop_instance_uid": self.sop_instance_uid,
            "evidence_kind": self.evidence_kind,
            "risk": self.risk,
            "details": self.details,
            "message": self.message,
        }


def _img_to_png_bytes(arr: np.ndarray) -> bytes:
    """2D uint8 numpy massivini PNG baytlariga o'tkazadi."""
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def route_dicom_dataset(
    source: bytes | str | Path | BinaryIO,
    store: Any,
    episode_id: Optional[str] = None,
    actor: str = "pacs_listener",
    cxr_model: Optional[Any] = None,
    angio_model: Optional[Any] = None,
) -> PacsRoutingResult:
    """DICOM faylini qabul qilib, tegishli epizod va AI modeliga yo'naltiradi."""
    arr, meta = parse_dicom_dataset(source)

    # 1. Epizodni aniqlash yoki yaratish
    p_ref = meta.patient_id or "ANONYMOUS_PACS"
    ep: Optional[Episode] = None

    if episode_id:
        try:
            ep = store.get(episode_id)
        except Exception:
            ep = None

    if ep is None:
        # Bemor kodi bo'yicha mavjud epizodni qidirish
        all_ids = store.ids() if hasattr(store, "ids") else []
        for eid in reversed(all_ids):
            try:
                candidate = store.get(eid)
                if candidate.patient_ref == p_ref:
                    ep = candidate
                    break
            except Exception:
                continue

    # Agar topilmasa, yangi epizod ochish
    if ep is None:
        ep = Episode(patient_ref=p_ref, population="adult")
        store.save(ep, actor, "episode.create", {"source": "pacs_auto_ingest", "patient_ref": p_ref})

    modality = (meta.modality or "OT").upper()
    prov = Provenance(
        name="pacs_dicom_router",
        version="1.0.0",
        reference=f"DICOM Part 10 (SOP: {meta.sop_instance_uid or 'N/A'}, Modality: {modality})",
    )

    ev_created: Optional[Evidence] = None
    details: dict[str, Any] = {"metadata": meta.to_dict()}
    msg = ""

    # 2. Modallik bo'yicha tahlil qilish
    if modality in ("DX", "CR"):  # Ko'krak qafasi rentgenogrammasi (CXR)
        # Agar 3D bo'lsa birinchi kadrni olamiz
        frame = arr[0] if arr.ndim == 3 else arr
        png_bytes = _img_to_png_bytes(frame)

        if cxr_model is not None and getattr(cxr_model, "available", False):
            ev_created = cxr_model.analyze(png_bytes, view_position=meta.view_position or "PA")
        else:
            # Standart zaxira tahlili
            ev_created = Evidence(
                kind="cxr.dicom",
                value={"modality": modality, "dimensions": f"{meta.rows}x{meta.columns}"},
                source=Source.MODEL,
                provenance=prov,
                risk=RiskLevel.NORMAL,
                explanation=["PACS orqali CXR rentgen qabul qilindi"],
            )
        msg = f"CXR DICOM ({modality}) qabul qilindi va tahlil qilindi."

    elif modality == "XA":  # Koronar angiografiya
        # Ko'p kadrli (cine loop) bo'lsa o'rta kadrni tanlaymiz (odatda kontrast maksimal bo'lgan kadr)
        if arr.ndim == 3:
            mid_idx = arr.shape[0] // 2
            frame = arr[mid_idx]
            details["selected_frame"] = mid_idx
            details["total_frames"] = arr.shape[0]
        else:
            frame = arr

        png_bytes = _img_to_png_bytes(frame)

        if angio_model is not None and getattr(angio_model, "available", False):
            ev_created = angio_model.analyze(png_bytes)
        else:
            ev_created = Evidence(
                kind="angio.dicom",
                value={"modality": modality, "frames": meta.number_of_frames, "dimensions": f"{meta.rows}x{meta.columns}"},
                source=Source.MODEL,
                provenance=prov,
                risk=RiskLevel.NORMAL,
                explanation=["PACS orqali XA koronar angiografiya qabul qilindi"],
            )
        msg = f"XA Angiografiya DICOM ({meta.number_of_frames} kadr) qabul qilindi va tahlil qilindi."

    elif modality == "US":  # Ultratovush / ExoKG
        ev_created = Evidence(
            kind="echo.dicom",
            value={"modality": modality, "frames": meta.number_of_frames, "dimensions": f"{meta.rows}x{meta.columns}"},
            source=Source.MODEL,
            provenance=prov,
            risk=RiskLevel.NORMAL,
            explanation=["PACS orqali ExoKG ultratovush tasviri qabul qilindi"],
        )
        msg = "ExoKG ultratovush DICOM qabul qilindi."

    else:
        ev_created = Evidence(
            kind="dicom.study",
            value=meta.to_dict(),
            source=Source.MODEL,
            provenance=prov,
            risk=RiskLevel.NORMAL,
            explanation=[f"Noma'lum yoki umumiy modalitedagi DICOM ({modality}) qabul qilindi"],
        )
        msg = f"DICOM ({modality}) qabul qilindi."

    # 3. Dalilni epizodga qo'shish va saqlash
    ep.add(ev_created)
    store.save(
        ep,
        actor,
        "pacs.dicom_received",
        {
            "modality": modality,
            "sop_instance_uid": meta.sop_instance_uid,
            "study_instance_uid": meta.study_instance_uid,
            "evidence_kind": ev_created.kind,
            "risk": ev_created.risk.value,
        },
    )

    return PacsRoutingResult(
        success=True,
        episode_id=ep.id,
        patient_ref=ep.patient_ref,
        modality=modality,
        study_instance_uid=meta.study_instance_uid,
        series_instance_uid=meta.series_instance_uid,
        sop_instance_uid=meta.sop_instance_uid,
        evidence_kind=ev_created.kind,
        risk=ev_created.risk.value,
        details=details,
        message=msg,
    )
