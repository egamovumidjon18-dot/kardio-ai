from core.evidence import RiskLevel
from guardian.ocr import assess_inr_image


def engine(lines):
    return lambda data: lines


def test_clean_ocr_gives_inr_evidence():
    ev = assess_inr_image(b"img", "mechanical_aortic", engine([("Bemor: X", 0.97), ("МНО 2,6", 0.95)]))
    assert not ev.abstained and ev.value == 2.6 and ev.risk == RiskLevel.LOW
    assert any("OCR ishonchi" in e for e in ev.explanation)


def test_low_confidence_abstains():
    ev = assess_inr_image(b"img", "af", engine([("INR 2.5", 0.55)]))
    assert ev.abstained and "ishonchi past" in ev.explanation[0]


def test_no_text_or_no_inr_or_ambiguous_abstain():
    assert assess_inr_image(b"img", "af", engine([])).abstained
    assert assess_inr_image(b"img", "af", engine([("Gemoglobin 130", 0.99)])).abstained
    assert assess_inr_image(b"img", "af", engine([("INR 2.5", 0.99), ("INR 3.5", 0.99)])).abstained


def test_implausible_value_abstains():
    assert assess_inr_image(b"img", "af", engine([("INR 25", 0.99)])).abstained     # 2.5 → 25 OCR xatosi


def test_engine_failure_abstains_not_crashes():
    def boom(data):
        raise RuntimeError("x")

    ev = assess_inr_image(b"img", "af", boom)
    assert ev.abstained and "OCR xatosi" in ev.explanation[0]

    def bad(data):
        raise ValueError("rasm o'qib bo'lmadi")

    assert assess_inr_image(b"img", "af", bad).abstained


def test_high_inr_still_escalates_risk():
    assert assess_inr_image(b"img", "af", engine([("INR: 6.1", 0.99)])).risk == RiskLevel.HIGH


def test_real_rapidocr_reads_rendered_text():
    """Haqiqiy OCR dvigateli (o'rnatilgan bo'lsa): rasmga yozilgan 'INR 2.5' o'qiladi."""
    import io

    import pytest
    pytest.importorskip("rapidocr_onnxruntime")
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (500, 140), "white")
    try:
        font = ImageFont.truetype("arial.ttf", 56)
    except OSError:
        pytest.skip("shrift yo'q")
    ImageDraw.Draw(img).text((20, 30), "INR 2.5", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    ev = assess_inr_image(buf.getvalue(), "af")
    assert not ev.abstained and ev.value == 2.5
