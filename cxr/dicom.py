"""DICOM Part 10 (NEMA PS 3.10) minimal reader for CXR files.

Tashqi og'ir paketlarsiz (pydicom talab etilmaydi) sof Python / NumPy vositasida
standart tibbiy DICOM (.dcm) fayllarini o'qish, piksel massivini ajratish
va windowing/leveling (kontrastlash) qilish moduli.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import BinaryIO, Optional, Tuple

import numpy as np


def is_dicom(source: bytes | str | Path | BinaryIO) -> bool:
    """Fayl yoki baytlar oqimi DICOM Part 10 formatida ekanligini tekshiradi (128-bayt preamble + 'DICM')."""
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


class DicomParseError(ValueError):
    """DICOM faylini o'qishda xatolik yuz berganda ko'tariladi."""
    pass


def parse_dicom(source: bytes | str | Path | BinaryIO) -> Tuple[np.ndarray, dict]:
    """DICOM faylidan 2D kulrang uint8 piksel massivi va asosiy metama'lumotlarni ajratadi.

    Returns:
        (image_2d_uint8, metadata_dict)
    """
    if isinstance(source, (str, Path)):
        with open(source, "rb") as f:
            raw = f.read()
    elif isinstance(source, bytes):
        raw = source
    elif hasattr(source, "read"):
        raw = source.read()
    else:
        raise DicomParseError("Noto'g'ri manba turi")

    if len(raw) < 132 or raw[128:132] != b"DICM":
        raise DicomParseError("Faylda 'DICM' sehrli belgisi topilmadi")

    stream = io.BytesIO(raw)
    stream.seek(132)  # Skip 128 preamble + 4 'DICM'

    meta: dict = {
        "view_position": None,
        "photometric_interpretation": "MONOCHROME2",
        "rows": 0,
        "columns": 0,
        "bits_allocated": 16,
        "bits_stored": 16,
        "pixel_representation": 0,  # 0: unsigned, 1: signed
        "window_center": None,
        "window_width": None,
        "rescale_intercept": 0.0,
        "rescale_slope": 1.0,
        "patient_id": None,
        "study_date": None,
    }

    pixel_bytes = None
    is_explicit = True  # Standard DICOM Part 10 defaults to explicit VR

    # Tag parsing loop
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
                stream.read(2)  # 2 reserved bytes
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

        # Check for pixel data
        if tag == (0x7FE0, 0x0010):
            pixel_bytes = stream.read(length)
            break

        # If length is undefined (0xFFFFFFFF) or corrupt, stop
        if length == 0xFFFFFFFF or length > (file_len - stream.tell()):
            break

        val_bytes = stream.read(length)

        # Parse relevant header tags
        if tag == (0x0018, 0x5101):  # View Position (e.g. PA, AP, LATERAL)
            meta["view_position"] = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0028, 0x0004):  # Photometric Interpretation
            meta["photometric_interpretation"] = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0028, 0x0010):  # Rows
            if len(val_bytes) >= 2:
                meta["rows"] = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0011):  # Columns
            if len(val_bytes) >= 2:
                meta["columns"] = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0100):  # Bits Allocated
            if len(val_bytes) >= 2:
                meta["bits_allocated"] = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0101):  # Bits Stored
            if len(val_bytes) >= 2:
                meta["bits_stored"] = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x0103):  # Pixel Representation
            if len(val_bytes) >= 2:
                meta["pixel_representation"] = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == (0x0028, 0x1050):  # Window Center
            try:
                meta["window_center"] = float(val_bytes.decode("ascii", errors="ignore").split("\\")[0].strip())
            except (ValueError, IndexError):
                pass
        elif tag == (0x0028, 0x1051):  # Window Width
            try:
                meta["window_width"] = float(val_bytes.decode("ascii", errors="ignore").split("\\")[0].strip())
            except (ValueError, IndexError):
                pass
        elif tag == (0x0028, 0x1052):  # Rescale Intercept
            try:
                meta["rescale_intercept"] = float(val_bytes.decode("ascii", errors="ignore").strip())
            except ValueError:
                pass
        elif tag == (0x0028, 0x1053):  # Rescale Slope
            try:
                meta["rescale_slope"] = float(val_bytes.decode("ascii", errors="ignore").strip())
            except ValueError:
                pass
        elif tag == (0x0010, 0x0020):  # Patient ID
            meta["patient_id"] = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")
        elif tag == (0x0008, 0x0020):  # Study Date
            meta["study_date"] = val_bytes.decode("ascii", errors="ignore").strip().rstrip("\x00")

    if pixel_bytes is None:
        raise DicomParseError("Piksel ma'lumotlari (0x7FE0, 0x0010) topilmadi")

    rows, cols = meta["rows"], meta["columns"]
    bits = meta["bits_allocated"]

    # Decode pixels into numpy array
    if bits == 16:
        dtype = np.int16 if meta["pixel_representation"] == 1 else np.uint16
        arr = np.frombuffer(pixel_bytes, dtype=dtype)
    elif bits == 8:
        dtype = np.int8 if meta["pixel_representation"] == 1 else np.uint8
        arr = np.frombuffer(pixel_bytes, dtype=dtype)
    else:
        raise DicomParseError(f"Qo'llab-quvvatlanmaydigan bits_allocated: {bits}")

    expected_len = rows * cols
    if arr.size >= expected_len and expected_len > 0:
        arr = arr[:expected_len].reshape((rows, cols)).astype(np.float32)
    else:
        # If dimensions not explicitly found, try square root fallback
        side = int(np.sqrt(arr.size))
        if side * side == arr.size:
            arr = arr.reshape((side, side)).astype(np.float32)
        else:
            raise DicomParseError(f"Piksel soni ({arr.size}) kutilgan o'lchamga ({rows}x{cols}) mos kelmadi")

    # Rescale slope and intercept
    slope = meta.get("rescale_slope", 1.0) or 1.0
    intercept = meta.get("rescale_intercept", 0.0) or 0.0
    arr = arr * slope + intercept

    # Apply Windowing / Leveling to 0..255 uint8
    wc = meta.get("window_center")
    ww = meta.get("window_width")
    if wc is not None and ww is not None and ww > 0:
        lower = wc - 0.5 - (ww - 1) / 2.0
        upper = wc - 0.5 + (ww - 1) / 2.0
        arr = np.clip(arr, lower, upper)
        norm = ((arr - lower) / (upper - lower) * 255.0).astype(np.uint8)
    else:
        # Autoscale min..max
        min_v, max_v = float(np.min(arr)), float(np.max(arr))
        if max_v > min_v:
            norm = (((arr - min_v) / (max_v - min_v)) * 255.0).astype(np.uint8)
        else:
            norm = np.zeros_like(arr, dtype=np.uint8)

    # Photometric Interpretation: MONOCHROME1 means 0 is bright/white, max is dark/black
    if meta["photometric_interpretation"] == "MONOCHROME1":
        norm = 255 - norm

    return norm, meta
