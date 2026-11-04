import io
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import create_app
from core.episode import Episode
from core.evidence import RiskLevel
from core.fhir_export import export_episode_to_fhir
from core.store import SqliteEpisodeStore
from cxr.image import assess_cxr_quality, load_cxr_gray
from cxr.model import CXRModel
from risk.biomarkers import BiomarkersInput, assess_biomarkers


def _make_dummy_cxr(is_cardio: bool = False, is_congest: bool = False) -> bytes:
    arr = np.random.normal(0.2, 0.05, (224, 224)).astype(np.float32)
    y, x = np.ogrid[:224, :224]
    thorax_w = 160
    ctr = 0.65 if is_cardio else 0.42
    heart_w = thorax_w * ctr
    heart_mask = ((x - 112) ** 2 / (heart_w / 2) ** 2 + (y - 125) ** 2 / (70) ** 2) <= 1.0
    arr[heart_mask] += 0.55
    if is_congest:
        congest_mask = (np.abs(x - 112) > heart_w / 2) & (y > 90) & (y < 190)
        arr[congest_mask] += 0.35
    arr = np.clip(arr, 0.0, 1.0)
    im = Image.fromarray((arr * 255).astype(np.uint8), mode="L")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_cxr_image_quality():
    # 1. Normal image
    png_bytes = _make_dummy_cxr()
    arr = load_cxr_gray(png_bytes)
    ok, err = assess_cxr_quality(arr)
    assert ok is True
    assert err is None

    # 2. Blank low contrast image -> abstain
    blank = np.zeros((224, 224), dtype=np.float32) + 0.5
    ok, err = assess_cxr_quality(blank)
    assert ok is False
    assert "kontrast" in err.lower()


def test_cxr_model_inference():
    model = CXRModel.from_dir("weights/cxr", allow_synthetic=True)
    assert model is not None

    # 1. Lateral projection -> abstain
    ev_lat = model.predict(_make_dummy_cxr(), view_position="LATERAL")
    assert ev_lat.abstained is True
    assert "frontal" in ev_lat.explanation[0].lower()

    # 2. Frontal CXR prediction
    ev = model.predict(_make_dummy_cxr(is_cardio=True, is_congest=True), view_position="PA")
    assert ev.abstained is False
    assert ev.kind == "cxr.findings"
    assert "ctr_ratio" in ev.value
    assert ev.value["view"] == "PA"
    assert ev.risk in (RiskLevel.HIGH, RiskLevel.VERY_HIGH)


def test_biomarkers_algorithm():
    # 1. Normal / Rule-out (Troponin past, og'riq > 2 soat)
    inp_norm = BiomarkersInput(troponin_0h_ng_l=3.5, nt_probnp_pg_ml=150.0, age_years=45, symptoms_onset_hours=4.0)
    ev_norm = assess_biomarkers(inp_norm)
    assert ev_norm.risk == RiskLevel.LOW
    assert ev_norm.value["troponin_decision"] == "rule_out"
    assert ev_norm.value["nt_probnp_decision"] == "rule_out"

    # 2. Rule-in Troponin (O'tkir infarkt, 0h >= 52)
    inp_ami = BiomarkersInput(troponin_0h_ng_l=85.0, nt_probnp_pg_ml=400.0, age_years=62)
    ev_ami = assess_biomarkers(inp_ami)
    assert ev_ami.risk == RiskLevel.VERY_HIGH
    assert ev_ami.value["troponin_decision"] == "rule_in"

    # 3. Serial 1h Troponin delta rule-in (Delta >= 5 ng/L)
    inp_delta = BiomarkersInput(troponin_0h_ng_l=15.0, troponin_1h_ng_l=23.0, age_years=55)
    ev_delta = assess_biomarkers(inp_delta)
    assert ev_delta.risk == RiskLevel.VERY_HIGH
    assert ev_delta.value["troponin_decision"] == "rule_in"

    # 4. Severe heart failure decompensation (NT-proBNP >= 5000)
    inp_hf = BiomarkersInput(troponin_0h_ng_l=10.0, nt_probnp_pg_ml=6200.0, age_years=70)
    ev_hf = assess_biomarkers(inp_hf)
    assert ev_hf.risk == RiskLevel.VERY_HIGH
    assert ev_hf.value["nt_probnp_decision"] == "severe_decompensation"

    # 5. Abstain on empty input
    ev_empty = assess_biomarkers(BiomarkersInput())
    assert ev_empty.abstained is True


def test_cxr_and_biomarkers_api(tmp_path):
    store = SqliteEpisodeStore(str(tmp_path / "test_cxr.db"))
    cxr = CXRModel.from_dir("weights/cxr", allow_synthetic=True)
    app = create_app(store=store, pcg=None, cxr_model=cxr, auth=False)
    client = TestClient(app)

    # 1. Epizod ochish
    res = client.post("/episodes", json={"patient_ref": "PAT-CXR-001", "actor": "dr_karim"})
    assert res.status_code == 201
    eid = res.json()["id"]

    # 2. CXR yuklash
    cxr_bytes = _make_dummy_cxr()
    res_cxr = client.post(
        f"/episodes/{eid}/cxr",
        data={"actor": "dr_karim", "view_position": "PA", "lang": "uz"},
        files={"file": ("chest.png", cxr_bytes, "image/png")},
    )
    assert res_cxr.status_code == 200
    cxr_json = res_cxr.json()
    assert "evidence" in cxr_json
    assert cxr_json["evidence"]["kind"] == "cxr.findings"

    # 3. Biomarkers kiritish
    res_bio = client.post(
        f"/episodes/{eid}/biomarkers",
        json={
            "actor": "dr_karim",
            "troponin_0h_ng_l": 65.0,
            "nt_probnp_pg_ml": 2800.0,
            "age_years": 68.0,
        },
    )
    assert res_bio.status_code == 200
    bio_json = res_bio.json()
    assert "evidence" in bio_json
    assert bio_json["evidence"]["risk"] == "very_high"

    # 4. FHIR R4 eksportida CXR va Biomarkers tekshirish
    res_fhir = client.get(f"/episodes/{eid}/fhir")
    assert res_fhir.status_code == 200
    bundle = res_fhir.json()
    codes = [
        coding["code"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Observation"
        for coding in entry["resource"]["code"]["coding"]
    ]
    assert "36572-6" in codes  # CXR LOINC
    assert "49563-0" in codes  # Troponin LOINC
    assert "33762-6" in codes  # NT-proBNP LOINC
