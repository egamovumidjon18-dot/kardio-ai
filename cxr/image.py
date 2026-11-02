"""Ko'krak qafasi rentgenogrammasi (CXR) tasvirini qayta ishlash va sifat tekshiruvi.

Xususiyatlari:
  * Frontal (PA/AP) rentgenogrammani 224x224 o'lchamga keltirish;
  * Sifat tekshiruvi: kontrast yetishmasligi, haddan tashqari qorong'i/yorug' kadrlarni aniqlash;
  * Buzuq tasvirlarni modelga kiritmasdan oldin to'xtatish (abstain-first).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

import numpy as np
from PIL import Image

TARGET_SIZE = 224


def load_cxr_gray(source: Union[bytes, str, Path, np.ndarray, Image.Image]) -> np.ndarray:
    """Ixtiyoriy manbadan rentgenogrammani o'qiydi va [224, 224] float32 [0.0, 1.0] massiviga keltiradi."""
    if isinstance(source, np.ndarray):
        arr = source.astype(np.float32)
        if arr.ndim == 3:
            # RGB -> Gray
            arr = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
        if arr.max() > 1.0:
            arr /= 255.0
        im = Image.fromarray((arr * 255).astype(np.uint8), mode="L")
    elif isinstance(source, Image.Image):
        im = source.convert("L")
    elif isinstance(source, bytes):
        im = Image.open(io.BytesIO(source)).convert("L")
    else:
        im = Image.open(str(source)).convert("L")

    # 224x224 ga o'lchamini o'zgartirish (Bilinear)
    im = im.resize((TARGET_SIZE, TARGET_SIZE), Image.Resampling.BILINEAR)
    arr = np.array(im, dtype=np.float32) / 255.0
    return arr


def assess_cxr_quality(img: np.ndarray) -> tuple[bool, Optional[str]]:
    """Rentgenogramma tahlil uchun yaroqliligini tekshiradi."""
    if img.shape != (TARGET_SIZE, TARGET_SIZE):
        return False, f"Noto'g'ri o'lcham: {img.shape}, {TARGET_SIZE}x{TARGET_SIZE} kutilgan"

    # Kontrast tekshiruvi (standart og'ish)
    std = float(np.std(img))
    if std < 0.05:
        return False, f"Tasvir kontrasti juda past (std={std:.3f} < 0.05): rentgenogramma qorong'i yoki noaniq"

    # Haddan tashqari to'yinganlik (clipping / saturation)
    zeros = float(np.mean(img <= 0.01))
    ones = float(np.mean(img >= 0.99))
    if zeros > 0.85:
        return False, "Tasvir haddan tashqari qorong'i (under-exposed)"
    if ones > 0.85:
        return False, "Tasvir haddan tashqari yorug' (over-exposed / yuvilib ketgan)"

    return True, None


def to_model_input(img: np.ndarray) -> np.ndarray:
    """[224, 224] -> [1, 1, 224, 224] float32 tensor."""
    return img[np.newaxis, np.newaxis, :, :].astype(np.float32)
