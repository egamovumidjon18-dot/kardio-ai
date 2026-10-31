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


def test_parse_common_lab_formats():
    from guardian.inr import parse_inr_text
    assert parse_inr_text("MNO (INR): 3.8") == 3.8            # e2e tekshiruvida topilgan xato: ilgari None edi
    assert parse_inr_text("INR(МНО) = 3,1") == 3.1
    assert parse_inr_text("МНО [INR] - 4,2") == 4.2
    assert parse_inr_text("MNO 2.5 (norma 2.0-3.0)") == 2.5
    assert parse_inr_text("INR: 1.2\nmaqsad INR 2.5") is None   # ikki xil qiymat — taxmin qilinmaydi


def test_inr_read_preview_saves_nothing(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app
    from core.store import SqliteEpisodeStore
    from tests.test_ai_api import to_guardian
    engine = lambda data: [("LABORATORIYA", 0.97), ("MNO (INR): 3.8", 0.98)]
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "o.db")), None, ocr_engine=engine))
    eid = c.post("/episodes", json={"patient_ref": "O-1", "actor": "dr"}).json()["id"]
    assert c.post(f"/episodes/{eid}/guardian/inr-read", files={"file": ("i.png", b"x", "image/png")}).status_code == 409   # uy kuzatuvi emas
    to_guardian(c, eid)
    n_before = len(c.get(f"/episodes/{eid}").json()["evidence"])
    r = c.post(f"/episodes/{eid}/guardian/inr-read", files={"file": ("i.png", b"x", "image/png")})
    assert r.status_code == 200 and r.json()["value"] == 3.8
    assert len(c.get(f"/episodes/{eid}").json()["evidence"]) == n_before          # hech narsa saqlanmadi
    low = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "p.db")), None, ocr_engine=lambda d: [("MNO 3.8", 0.4)]))
    eid2 = low.post("/episodes", json={"patient_ref": "O-2", "actor": "dr"}).json()["id"]
    to_guardian(low, eid2)
    assert low.post(f"/episodes/{eid2}/guardian/inr-read", files={"file": ("i.png", b"x", "image/png")}).json() == {"value": None, "reason": "low_confidence"}
