"""Angiografiya kadrini tayyorlash va stenoz niqobini tahlil qilish — o'qitish va inference uchun umumiy.

Faqat numpy (+ Pillow rasm o'qish uchun, OpenCV'siz). Kadr 512×512 kulrang, [0,1].
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SIZE = 512
MIN_SIDE = 256


def load_gray(src: bytes | str | Path) -> np.ndarray:
    """Rasm (PNG/JPG) → kulrang uint8 [H, W]. Buzilgan fayl → ValueError."""
    from PIL import Image, UnidentifiedImageError

    try:
        im = Image.open(io.BytesIO(src) if isinstance(src, bytes) else str(src))
        return np.asarray(im.convert("L"), dtype=np.uint8)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"rasm o'qib bo'lmadi: {exc}") from None


def to_model_input(gray: np.ndarray) -> np.ndarray:
    """[H, W] uint8 → [1, 1, 512, 512] float32; kontrast 1–99 persentil bo'yicha cho'ziladi."""
    from PIL import Image

    im = Image.fromarray(gray).resize((SIZE, SIZE), Image.BILINEAR)
    x = np.asarray(im, dtype=np.float32) / 255.0
    lo, hi = np.percentile(x, [1, 99])
    x = np.clip((x - lo) / max(hi - lo, 1e-3), 0, 1)
    return x[None, None].astype(np.float32)


@dataclass
class Quality:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def assess_quality(gray: np.ndarray) -> Quality:
    """Abstain-first: angiografiyaga o'xshamagan / kontrastsiz kadrda model ishlamaydi."""
    reasons = []
    h, w = gray.shape
    if min(h, w) < MIN_SIDE:
        reasons.append(f"rasm juda kichik ({w}×{h} < {MIN_SIDE})")
    if abs(h / w - 1) > 0.25:
        reasons.append(f"kadr kvadratga yaqin emas ({w}×{h}) — kesilgan/boshqa turdagi rasm bo'lishi mumkin")
    if gray.std() < 12:
        reasons.append("kontrast juda past (tomir ko'rinmaydi)")
    if np.mean(gray >= 250) > 0.4 or np.mean(gray <= 5) > 0.6:
        reasons.append("ekspozitsiya noto'g'ri (ortiqcha yorug' yoki qora)")
    return Quality(not reasons, reasons)


def components(mask: np.ndarray, min_area: int = 1) -> list[np.ndarray]:
    """Bog'langan komponentlar (4-qo'shnilik), har biri bool niqob. scipy'siz."""
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    h, w = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack, pts = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            pts.append((cy, cx))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(pts) >= min_area:
            m = np.zeros_like(mask, dtype=bool)
            ys, xs = zip(*pts)
            m[list(ys), list(xs)] = True
            out.append(m)
    return out


def candidates(prob: np.ndarray, thr: float, min_area: int) -> list[dict]:
    """[512, 512] ehtimollik → stenoz nomzodlari (maydon, markaz, bbox, o'rtacha ishonch)."""
    res = []
    for m in components(prob >= thr, min_area):
        ys, xs = np.nonzero(m)
        res.append({"area_px": int(m.sum()), "center_xy": [int(xs.mean()), int(ys.mean())],
                    "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                    "confidence": round(float(prob[m].mean()), 3)})
    return sorted(res, key=lambda c: -c["confidence"])
