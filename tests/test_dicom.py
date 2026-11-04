"""DICOM Part 10 CXR parser va sifat nazorati testlari."""
from __future__ import annotations

import struct
import numpy as np
import pytest

from cxr.dicom import is_dicom, parse_dicom, DicomParseError
from cxr.model import CXRModel
from core.registry import ModelCard


def create_mock_dicom_bytes(
    rows: int = 224,
    cols: int = 224,
    bits_allocated: int = 16,
    view_position: str = "PA",
    photo_interp: str = "MONOCHROME2",
    wc: float = 1500.0,
    ww: float = 1000.0,
    fill_val: int = 1500,
) -> bytes:
    """Sintetik Part 10 DICOM baytlari yaratadi."""
    preamble = b"\x00" * 128
    magic = b"DICM"

    elements = bytearray()

    # (0x0002, 0x0010) Transfer Syntax UID: Explicit Little Endian
    ts_uid = b"1.2.840.10008.1.2.1\x00"
    elements.extend(struct.pack("<HH2sH", 0x0002, 0x0010, b"UI", len(ts_uid)) + ts_uid)

    # (0x0018, 0x5101) View Position
    vp_bytes = view_position.encode("ascii")
    if len(vp_bytes) % 2 == 1:
        vp_bytes += b" "
    elements.extend(struct.pack("<HH2sH", 0x0018, 0x5101, b"CS", len(vp_bytes)) + vp_bytes)

    # (0x0028, 0x0004) Photometric Interpretation
    pi_bytes = photo_interp.encode("ascii")
    if len(pi_bytes) % 2 == 1:
        pi_bytes += b" "
    elements.extend(struct.pack("<HH2sH", 0x0028, 0x0004, b"CS", len(pi_bytes)) + pi_bytes)

    # (0x0028, 0x0010) Rows
    elements.extend(struct.pack("<HH2sHH", 0x0028, 0x0010, b"US", 2, rows))

    # (0x0028, 0x0011) Columns
    elements.extend(struct.pack("<HH2sHH", 0x0028, 0x0011, b"US", 2, cols))

    # (0x0028, 0x0100) Bits Allocated
    elements.extend(struct.pack("<HH2sHH", 0x0028, 0x0100, b"US", 2, bits_allocated))

    # (0x0028, 0x1050) Window Center
    wc_bytes = str(wc).encode("ascii")
    if len(wc_bytes) % 2 == 1:
        wc_bytes += b" "
    elements.extend(struct.pack("<HH2sH", 0x0028, 0x1050, b"DS", len(wc_bytes)) + wc_bytes)

    # (0x0028, 0x1051) Window Width
    ww_bytes = str(ww).encode("ascii")
    if len(ww_bytes) % 2 == 1:
        ww_bytes += b" "
    elements.extend(struct.pack("<HH2sH", 0x0028, 0x1051, b"DS", len(ww_bytes)) + ww_bytes)

    # Gradientli / anatomik o'xshash piksel massivi
    y, x = np.ogrid[:rows, :cols]
    base = np.sin(x / 30.0) * np.cos(y / 30.0)
    arr = (base * 400 + fill_val).astype(np.uint16 if bits_allocated == 16 else np.uint8)
    raw_pixels = arr.tobytes()

    # (0x7FE0, 0x0010) Pixel Data
    elements.extend(struct.pack("<HH2s2sI", 0x7FE0, 0x0010, b"OW", b"\x00\x00", len(raw_pixels)))
    elements.extend(raw_pixels)

    return preamble + magic + bytes(elements)


def test_is_dicom():
    assert not is_dicom(b"hello world")
    assert not is_dicom(b"\x00" * 140)
    dcm = create_mock_dicom_bytes()
    assert is_dicom(dcm)


def test_parse_dicom_success():
    dcm = create_mock_dicom_bytes(rows=224, cols=224, view_position="PA", photo_interp="MONOCHROME2")
    img, meta = parse_dicom(dcm)
    assert img.shape == (224, 224)
    assert img.dtype == np.uint8
    assert meta["view_position"] == "PA"
    assert meta["photometric_interpretation"] == "MONOCHROME2"
    assert meta["rows"] == 224
    assert meta["columns"] == 224


def test_parse_dicom_monochrome1_inversion():
    dcm1 = create_mock_dicom_bytes(photo_interp="MONOCHROME1", fill_val=2000)
    dcm2 = create_mock_dicom_bytes(photo_interp="MONOCHROME2", fill_val=2000)
    img1, _ = parse_dicom(dcm1)
    img2, _ = parse_dicom(dcm2)
    # MONOCHROME1 teskari bo'lishi kerak
    assert np.allclose(img1.astype(int) + img2.astype(int), 255, atol=2)


def test_cxr_model_with_dicom():
    model = CXRModel.from_dir("weights/cxr", allow_synthetic=True)
    assert model is not None

    # Frontal PA DICOM -> muvaffaqiyatli xulosa
    dcm_pa = create_mock_dicom_bytes(view_position="PA")
    ev = model.predict(dcm_pa)
    assert not ev.abstained
    assert "ctr_ratio" in ev.value
    assert 0.35 <= ev.value["ctr_ratio"] <= 0.75

    # LATERAL DICOM -> avtomatik rad etish (abstain-first)
    dcm_lat = create_mock_dicom_bytes(view_position="LATERAL")
    ev_lat = model.predict(dcm_lat)
    assert ev_lat.abstained
    assert "Faqat frontal (PA/AP) proyeksiyalar qabul qilinadi" in "; ".join(ev_lat.explanation)
