"""PACS DICOM Part 10 (NEMA PS 3.10) Kengaytirilgan Tibbiy Tasvirlar Parseri.

Tashqi og'ir kutubxonalarsiz (sof Python / NumPy) turli modalitetdagi
(CXR 'DX'/'CR', Angiografiya 'XA', ExoKG 'US', EKG 'ECG') tibbiy DICOM (.dcm)
fayllarini o'qish, teglarni ajratish, 2D/3D piksellarni dekodlash va
kontrastlash (windowing/leveling) moduli.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Optional, Tuple, Any

import numpy as np


class DicomParseError(ValueError):
    """DICOM faylini o'qish yoki tahlil qilishda yuzaga keladigan xatolik."""
    pass


def is_dicom(source: bytes | str | Path | BinaryIO) -> bool:
    """Fayl yoki baytlar oqimi DICOM Part 10 formatida ekanligini tekshiradi."""
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.is_file():
            return False
        with open(p, "rb") as f:
            header = f.read(132)
    elif isinstance(source, bytes):
        header = source[:132]
    elif hasattr(source, "read") and hasattr(source, "seek"):
        pos = source.tell()
        header = source.read(132)
        source.seek(pos)
    else:
        return False

    return len(header) >= 132 and header[128:132] == b"DICM"


@dataclass
class DicomMetadata:
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    study_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None
    sop_instance_uid: Optional[str] = None
    modality: str = "OT"                   # DX, CR, XA, US, ECG, CT, MR, OT (Other)
    view_position: Optional[str] = None    # PA, AP, LATERAL...
    study_date: Optional[str] = None
    study_description: Optional[str] = None
    series_description: Optional[str] = None
    rows: int = 0
    columns: int = 0
    number_of_frames: int = 1
    bits_allocated: int = 16
    bits_stored: int = 16
    pixel_representation: int = 0          # 0: unsigned, 1: signed
    photometric_interpretation: str = "MONOCHROME2"
    window_center: Optional[float] = None
    window_width: Optional[float] = None
    rescale_intercept: float = 0.0
    rescale_slope: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "study_instance_uid": self.study_instance_uid,
            "series_instance_uid": self.series_instance_uid,
            "sop_instance_uid": self.sop_instance_uid,
            "modality": self.modality,
            "view_position": self.view_position,
            "study_date": self.study_date,
            "study_description": self.study_description,
            "series_description": self.series_description,
            "dimensions": f"{self.rows}x{self.columns}",
            "number_of_frames": self.number_of_frames,
            "bits_allocated": self.bits_allocated,
        }


def parse_dicom_dataset(source: bytes | str | Path | BinaryIO) -> Tuple[np.ndarray, DicomMetadata]:
    """DICOM faylidan piksel massivi (uint8) va metama'lumotlarni ajratadi.

    Returns:
        (image_array_uint8, DicomMetadata)
        - Agar bitta kadr bo'lsa: [H, W] uint8 massiv
        - Agar ko'p kadrli (cine loop) bo'lsa: [N, H, W] uint8 massiv
    """
    if isinstance(source, (str, Path)):
        with open(source, "rb") as f:
            raw = f.read()
    elif isinstance(source, bytes):
        raw = source
    elif hasattr(source, "read"):
        raw = source.read()
    else:
        raise DicomParseError("Noto'g'ri DICOM manba turi")

    if len(raw) < 132 or raw[128:132] != b"DICM":
        raise DicomParseError("Faylda 'DICM' sehrli belgisi topilmadi (Part 10 talabiga zid)")

    stream = io.BytesIO(raw)
    stream.seek(132)

    meta = DicomMetadata()
    pixel_bytes: Optional[bytes] = None
    is_explicit = True
    file_len = len(raw)

    while stream.tell() < file_len:
        tag_bytes = stream.read(4)
        if len(tag_bytes) < 4:
            break
        group, element = struct.unpack("<HH", tag_bytes)
        tag = (group, element)

        # File Meta Information Group (0x0002) is always Explicit VR Little Endian
        if group == 0x0002 and tag == (0x0002, 0x0010):  # Transfer Syntax UID
            vr = stream.read(2)
            length = struct.unpack("<H", stream.read(2))[0]
            val = stream.read(length).decode("ascii", errors="ignore").strip().rstrip("\x00")
            if val == "1.2.840.10008.1.2":  # Implicit VR Little Endian
                is_explicit = False
            continue

        if is_explicit and group != 0x0002:
            vr = stream.read(2)
            if vr in (b"OB", b"OW", b"OF", b"SQ", b"UT", b"UN"):
                stream.read(2)  # reserved
                len_bytes = stream.read(4)
                if len(len_bytes) < 4:
                    break
                length = struct.unpack("<I", len_bytes)[0]
            else:
                len_bytes = stream.read(2)
                if len(len_bytes) < 2:
                    break
                length = struct.unpack("<H", len_bytes)[0]
        else:
            len_bytes = stream.read(4)
            if len(len_bytes) < 4:
                break
            length = struct.unpack("<I", len_bytes)[0]

        # Check for pixel data (0x7FE0, 0x0010)
        if tag == (0x7FE0, 0x0010):
            pixel_bytes = stream.read(length)
            break

        if length == 0xFFFFFFFF or length > (file_len - stream.tell()):
            break

        val_bytes = stream.read(length)

        # Parse tags
        if tag == (0x0008, 0x0060):  # Modality (DX, CR, XA, US...)
            meta.modality = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00").upper()
        elif tag == (0x0010, 0x0020):  # Patient ID
            meta.patient_id = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0010, 0x0010):  # Patient Name
            meta.patient_name = val_bytes.decode("utf-8", errors="ignore").strip().rstrip("\x00").replace("^", " ")
        elif tag == (0x0020, 0x000D):  # Study Instance UID
            meta.study_instance_uid = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0020, 0x000E):  # Series Instance UID
            meta.series_instance_uid = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0008, 0x0018):  # SOP Instance UID
            meta.sop_instance_uid = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0008, 0x0020):  # Study Date
            meta.study_date = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0008, 0x1030):  # Study Description
            meta.study_description = val_bytes.decode("utf-8", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0008, 0x103E):  # Series Description
            meta.series_description = val_bytes.decode("utf-8", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0018, 0x5101):  # View Position
            meta.view_position = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00").upper()
        elif tag == (0x0028, 0x0004):  # Photometric Interpretation
            meta.photometric_interpretation = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0028, 0x0008):  # Number of Frames
            try:
                meta.number_of_frames = int(val_bytes.decode("ascii", errors="ignore").strip())
            except ValueError:
                meta.number_of_frames = 1
        elif tag == (0x0028, 0x0010) and len(val_bytes) >= 2:  # Rows
            meta.rows = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0011) and len(val_bytes) >= 2:  # Columns
            meta.columns = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0100) and len(val_bytes) >= 2:  # Bits Allocated
            meta.bits_allocated = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0101) and len(val_bytes) >= 2:  # Bits Stored
            meta.bits_stored = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0103) and len(val_bytes) >= 2:  # Pixel Representation
            meta.pixel_representation = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x1050):  # Window Center
            try:
                meta.window_center = float(val_bytes.decode("ascii", errors="ignore").split("\\")[0].strip())
            except (ValueError, IndexError):
                pass
        elif tag == (0x0028, 0x1051):  # Window Width
            try:
                meta.window_width = float(val_bytes.decode("ascii", errors="ignore").split("\\")[0].strip())
            except (ValueError, IndexError):
                pass
        elif tag == (0x0028, 0x1052):  # Rescale Intercept
            try:
                meta.rescale_intercept = float(val_bytes.decode("ascii", errors="ignore").strip())
            except ValueError:
                pass
        elif tag == (0x0028, 0x1053):  # Rescale Slope
            try:
                meta.rescale_slope = float(val_bytes.decode("ascii", errors="ignore").strip())
            except ValueError:
                pass

    if pixel_bytes is None:
        raise DicomParseError("DICOM faylida piksel ma'lumotlari (0x7FE0, 0x0010) topilmadi")

    rows, cols = meta.rows, meta.columns
    frames = max(1, meta.number_of_frames)
    bits = meta.bits_allocated
    signed = meta.pixel_representation == 1

    if bits == 8:
        dtype = np.int8 if signed else np.uint8
    elif bits == 16:
        dtype = np.int16 if signed else np.uint16
    elif bits == 32:
        dtype = np.int32 if signed else np.uint32
    else:
        raise DicomParseError(f"Qo'llab-quvvatlanmaydigan bits_allocated: {bits}")

    expected_pixels = rows * cols * frames
    arr = np.frombuffer(pixel_bytes, dtype=dtype)
    if arr.size < expected_pixels:
        raise DicomParseError(f"Piksel soni ({arr.size}) kutilgan o'lchamga ({frames}x{rows}x{cols}={expected_pixels}) yetarli emas")

    arr = arr[:expected_pixels].astype(np.float32)

    # Rescale slope va intercept
    if meta.rescale_slope != 1.0 or meta.rescale_intercept != 0.0:
        arr = arr * meta.rescale_slope + meta.rescale_intercept

    # Windowing / Kontrastlash
    wc, ww = meta.window_center, meta.window_width
    if wc is not None and ww is not None and ww > 0:
        low = wc - ww / 2.0
        high = wc + ww / 2.0
        arr = np.clip((arr - low) / (high - low), 0.0, 1.0) * 255.0
    else:
        p1, p99 = np.percentile(arr, [1, 99])
        if p99 > p1:
            arr = np.clip((arr - p1) / (p99 - p1), 0.0, 1.0) * 255.0
        else:
            arr = np.zeros_like(arr)

    arr = arr.astype(np.uint8)

    # MONOCHROME1 teskari o'girish (0 = oq, 255 = qora -> standart MONOCHROME2 ga)
    if meta.photometric_interpretation.upper() == "MONOCHROME1":
        arr = 255 - arr

    if frames > 1:
        arr = arr.reshape((frames, rows, cols))
    else:
        arr = arr.reshape((rows, cols))

    return arr, meta
