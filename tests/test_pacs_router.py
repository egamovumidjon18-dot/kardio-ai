"""PACS DICOM Parser va Router testlari."""
from __future__ import annotations

import struct
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.episode import Episode
from core.store import SqliteEpisodeStore
from pacs.dicom_parser import is_dicom, parse_dicom_dataset, DicomMetadata
from pacs.router import route_dicom_dataset


def make_mock_pacs_dicom(
    modality: str = "DX",
    patient_id: str = "PAT-PACS-100",
    patient_name: str = "Toshmatov Ali",
    rows: int = 64,
    cols: int = 64,
    view_position: str = "PA",
    sop_uid: str = "1.2.840.10008.5.1.4.1.1.1.12345",
) -> bytes:
    """Sintetik PACS DICOM fayli baytlarini yaratadi."""
    preamble = b"\x00" * 128
    magic = b"DICM"
    elements = bytearray()

    def add_elem(group: int, elem: int, vr: str, data: bytes):
        if len(data) % 2 == 1:
            data += b" "
        elements.extend(struct.pack("<HH2sH", group, elem, vr.encode("ascii"), len(data)) + data)

    # Transfer Syntax: Explicit Little Endian
    add_elem(0x0002, 0x0010, "UI", b"1.2.840.10008.1.2.1\x00")
    # Modality
    add_elem(0x0008, 0x0060, "CS", modality.encode("ascii"))
    # SOP Instance UID
    add_elem(0x0008, 0x0018, "UI", sop_uid.encode("ascii"))
    # Study Date
    add_elem(0x0008, 0x0020, "DA", b"20261103")
    # Patient ID
    add_elem(0x0010, 0x0020, "LO", patient_id.encode("ascii"))
    # Patient Name
    add_elem(0x0010, 0x0010, "PN", patient_name.encode("utf-8"))
    # View Position
    add_elem(0x0018, 0x5101, "CS", view_position.encode("ascii"))

    # Rows, Columns, Bits
    elements.extend(struct.pack("<HH2sHH", 0x0028, 0x0010, b"US", 2, rows))
    elements.extend(struct.pack("<HH2sHH", 0x0028, 0x0011, b"US", 2, cols))
    elements.extend(struct.pack("<HH2sHH", 0x0028, 0x0100, b"US", 2, 16))

    # Pixel data
    pixels = np.ones((rows, cols), dtype=np.uint16) * 1200
    p_bytes = pixels.tobytes()
    elements.extend(struct.pack("<HH2s2sI", 0x7FE0, 0x0010, b"OW", b"\x00\x00", len(p_bytes)))
    elements.extend(p_bytes)

    return preamble + magic + bytes(elements)


def test_pacs_dicom_parser():
    dcm = make_mock_pacs_dicom(modality="DX", patient_id="PAT-999", patient_name="Bemor Ali")
    assert is_dicom(dcm)

    arr, meta = parse_dicom_dataset(dcm)
    assert arr.shape == (64, 64)
    assert meta.modality == "DX"
    assert meta.patient_id == "PAT-999"
    assert "Ali" in (meta.patient_name or "")
    assert meta.view_position == "PA"


def test_pacs_dicom_router_auto_creates_episode(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "pacs.db"))
    dcm = make_mock_pacs_dicom(modality="DX", patient_id="BEMOR-PACS-001")

    res = route_dicom_dataset(dcm, store=store, actor="test_pacs")
    assert res.success is True
    assert res.patient_ref == "BEMOR-PACS-001"
    assert res.modality == "DX"

    # Epizod bazada saqlanganligini tekshirish
    ep = store.get(res.episode_id)
    assert ep.patient_ref == "BEMOR-PACS-001"
    assert any("cxr" in ev.kind for ev in ep.evidence)

    # Kriptografik audit logini tekshirish
    audit_events = store.audit(ep.id)
    assert any(a["action"] == "pacs.dicom_received" for a in audit_events)


def test_pacs_dicom_router_links_to_existing_episode(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "pacs.db"))
    existing_ep = Episode(patient_ref="BEMOR-EXISTING-77", population="adult")
    store.save(existing_ep, "doctor", "episode.create")

    # Angiografiya XA DICOM
    dcm_angio = make_mock_pacs_dicom(modality="XA", patient_id="BEMOR-EXISTING-77")
    res = route_dicom_dataset(dcm_angio, store=store, actor="cath_lab_listener")

    assert res.success is True
    assert res.episode_id == existing_ep.id
    assert res.modality == "XA"

    updated_ep = store.get(existing_ep.id)
    assert any("angio" in ev.kind for ev in updated_ep.evidence)


def test_pacs_api_endpoints(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "pacs_api.db"))
    app = create_app(store, None)
    client = TestClient(app)

    # 1. Standart bo'lmagan fayl yuklanganda 400
    res_bad = client.post("/pacs/dicom", files={"file": ("corrupt.dcm", b"NOT_A_DICOM_FILE", "application/octet-stream")})
    assert res_bad.status_code == 400

    # 2. To'g'ri DICOM yuklash
    dcm = make_mock_pacs_dicom(modality="DX", patient_id="PAT-API-42")
    res_ok = client.post("/pacs/dicom", files={"file": ("chest.dcm", dcm, "application/dicom")})
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["success"] is True
    assert data["modality"] == "DX"
    eid = data["episode_id"]

    # 3. GET /episodes/{eid}/pacs/studies
    res_studies = client.get(f"/episodes/{eid}/pacs/studies")
    assert res_studies.status_code == 200
    studies = res_studies.json()
    assert len(studies) >= 1
    assert any("cxr" in s["kind"] for s in studies)
