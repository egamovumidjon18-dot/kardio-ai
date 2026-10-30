import io

import numpy as np
import pytest

from angio.image import assess_quality, candidates, components, load_gray, to_model_input
from angio.model import LABEL, AngioModel
from core.evidence import RiskLevel
from core.registry import ModelCard

CARD = ModelCard(name="angio_test", version="0", task="t", dataset="ARCADE", weights="none",
                 thresholds={"prob": 0.5, "min_area_px": 20})


def fake_frame(size=512, seed=0):
    rng = np.random.default_rng(seed)
    img = (rng.random((size, size)) * 40 + 120).astype(np.uint8)
    img[size // 3:size // 3 + 10, :] = 40                  # "tomir"
    img[:, size // 2:size // 2 + 6] = 60
    return img


def blob_backend(blobs):
    def run(x):
        p = np.zeros((512, 512), np.float32)
        for y, x0, r in blobs:
            p[y - r:y + r, x0 - r:x0 + r] = 0.9
        return p
    return run


def png(arr):
    from PIL import Image
    b = io.BytesIO()
    Image.fromarray(arr).save(b, format="PNG")
    return b.getvalue()


def test_components_and_candidates():
    m = np.zeros((50, 50), bool)
    m[5:10, 5:10] = True
    m[30:35, 30:40] = True
    assert len(components(m)) == 2
    p = np.zeros((512, 512), np.float32)
    p[100:120, 100:130] = 0.9
    p[300:303, 300:303] = 0.9
    c = candidates(p, 0.5, 20)
    assert len(c) == 1 and c[0]["bbox_xyxy"] == [100, 100, 129, 119]


def test_model_input_shape_and_range():
    x = to_model_input(fake_frame(300))
    assert x.shape == (1, 1, 512, 512) and 0 <= x.min() and x.max() <= 1


def test_candidates_found_is_moderate_and_labelled_assistive():
    ev = AngioModel(CARD, blob_backend([(150, 150, 15)])).analyze(png(fake_frame()))
    assert ev.risk == RiskLevel.MODERATE and not ev.abstained
    assert ev.value["label"] == LABEL and "SYNTAX" in LABEL and "emas" in LABEL
    assert ev.value["n_candidates"] == 1
    assert any("SYNTAX kalkulyatori emas" in e for e in ev.explanation)


def test_no_candidate_never_reassures():
    ev = AngioModel(CARD, blob_backend([])).analyze(fake_frame())
    assert ev.risk == RiskLevel.UNKNOWN and "EMAS" in ev.explanation[0]


def test_bad_frames_abstain():
    m = AngioModel(CARD, blob_backend([(150, 150, 15)]))
    assert m.analyze(np.full((512, 512), 128, np.uint8)).abstained           # kontrastsiz
    assert m.analyze(fake_frame(100)).abstained                              # kichik
    assert m.analyze(fake_frame(512)[:, :300]).abstained                     # kvadrat emas
    assert assess_quality(fake_frame()).ok


def test_too_many_candidates_abstain():
    blobs = [(30 + 35 * (i % 13), 30 + 70 * (i // 13), 10) for i in range(13)]
    ev = AngioModel(CARD, blob_backend(blobs)).analyze(fake_frame())
    assert ev.abstained and "ishonchsiz" in ev.explanation[0]


def test_broken_image_raises_value_error():
    with pytest.raises(ValueError):
        load_gray(b"not an image")


def test_arcade_license():
    assert CARD.commercial_use and CARD.dataset_license == "CC-BY 4.0"
