"""MNO (INR) laboratoriya qog'ozi: rasm → matn (OCR) → `parse_inr_text` → `assess_inr`.

OCR dvigateli: rapidocr-onnxruntime (ONNX, CPU, ixtiyoriy bog'liqlik). Xavfsizlik:
  * dvigatel yo'q / rasm o'qilmadi / OCR ishonchi past / qiymat bir ma'noli emas → ABSTAIN
    (bemor qiymatni qo'lda kiritadi yoki rasmni qayta yuboradi);
  * noto'g'ri o'qilgan raqam xavfli (2.5 ↔ 25) — `assess_inr` fiziologik bo'lmagan qiymatni ham rad etadi;
  * bemorga doza aytilmaydi (inr.py qoidasi o'zgarmaydi).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.evidence import Evidence, Provenance, Source
from guardian.inr import Indication, assess_inr, parse_inr_text

MIN_CONFIDENCE = 0.80
# engine: rasm (bytes) → [(matn, ishonch 0..1), ...] qatorlar
Engine = Callable[[bytes], list[tuple[str, float]]]


@dataclass
class OcrResult:
    text: str
    confidence: float          # qatorlar o'rtacha ishonchi
    n_lines: int


def rapid_engine() -> Optional[Engine]:
    """rapidocr o'rnatilmagan bo'lsa None."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None
    ocr = RapidOCR()

    def run(data: bytes) -> list[tuple[str, float]]:
        import io

        import numpy as np
        from PIL import Image, UnidentifiedImageError

        try:
            img = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"rasm o'qib bo'lmadi: {exc}") from None
        result, _ = ocr(img)
        return [(str(t), float(s)) for _, t, s in (result or [])]

    return run


def read_text(image: bytes | str | Path, engine: Engine) -> OcrResult:
    data = image if isinstance(image, bytes) else Path(image).read_bytes()
    lines = engine(data)
    if not lines:
        return OcrResult("", 0.0, 0)
    return OcrResult("\n".join(t for t, _ in lines), sum(s for _, s in lines) / len(lines), len(lines))


def assess_inr_image(image: bytes | str | Path, indication: Indication,
                     engine: Optional[Engine] = None, min_confidence: float = MIN_CONFIDENCE) -> Evidence:
    """Rasm → Evidence('guardian.inr'). Har qanday ishonchsizlikda abstain."""
    prov = Provenance(name="inr_ocr", version="rapidocr-onnx", reference="rapidocr-onnxruntime + ACC/AHA 2020 maqsadlari")
    engine = engine or rapid_engine()
    if engine is None:
        return Evidence.abstain("guardian.inr", Source.PATIENT, prov,
                                "OCR moduli o'rnatilmagan (pip install rapidocr-onnxruntime) — qiymatni qo'lda kiriting")
    try:
        res = read_text(image, engine)
    except ValueError as exc:
        return Evidence.abstain("guardian.inr", Source.PATIENT, prov, str(exc))
    except Exception as exc:  # OCR dvigateli ichki xatosi — bemorga xavf tug'dirmasligi uchun abstain
        return Evidence.abstain("guardian.inr", Source.PATIENT, prov, f"OCR xatosi: {type(exc).__name__}")
    if res.n_lines == 0:
        return Evidence.abstain("guardian.inr", Source.PATIENT, prov,
                                "rasmda matn topilmadi — yorug'roq joyda, to'g'ri burchakdan qayta suratga oling")
    if res.confidence < min_confidence:
        return Evidence.abstain("guardian.inr", Source.PATIENT, prov,
                                f"OCR ishonchi past ({res.confidence:.0%} < {min_confidence:.0%}) — qayta suratga oling "
                                "yoki qiymatni qo'lda kiriting", value={"ocr_text": res.text})
    ev = assess_inr(parse_inr_text(res.text), indication, res.text)
    ev.explanation.append(f"OCR ishonchi {res.confidence:.0%}, {res.n_lines} qator")
    ev.provenance = prov
    return ev
