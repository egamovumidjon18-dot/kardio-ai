import numpy as np
import pytest

from adapters import echo_ef
from adapters.echo_ef import EchoEFAdapter, ef_risk
from core.evidence import RiskLevel
from core.registry import DATASET_LICENSES, LicenseError, ModelCard, check_license


class FakeSess:
    def __init__(self, ef):
        self.ef = ef

    def run(self, names, feed):
        assert feed["input"].shape == (1, 16, 3, 112, 112)
        return [np.array([self.ef], np.float32)]


def adapter(ef):
    a = EchoEFAdapter.__new__(EchoEFAdapter)
    a.card = ModelCard(name="echo_ef_r2plus1d", version="t", task="t", dataset="EchoNet-Dynamic", weights="n")
    check_license(a.card)
    a.sess, a.num_frames, a.size = FakeSess(ef), 16, 112
    return a


def video(tmp_path):
    import cv2
    p = tmp_path / "c.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 25, (112, 112))
    rng = np.random.default_rng(0)
    for i in range(40):
        w.write((rng.random((112, 112, 3)) * 80 + 60 + 40 * np.sin(i / 3)).clip(0, 255).astype("uint8"))
    w.release()
    return p


def test_registry_marks_echonet_non_commercial():
    assert DATASET_LICENSES["EchoNet-Dynamic"][1] is False


def test_product_mode_blocks_echonet(monkeypatch):
    monkeypatch.setenv("CARDIOPATH_MODE", "product")
    with pytest.raises(LicenseError):
        adapter(55)


@pytest.mark.parametrize("ef,risk", [(60, RiskLevel.LOW), (45, RiskLevel.MODERATE),
                                     (35, RiskLevel.HIGH), (25, RiskLevel.VERY_HIGH)])
def test_ef_to_risk(tmp_path, ef, risk):
    ev = adapter(ef).analyze(video(tmp_path))
    assert not ev.abstained and ev.value == ef and ev.unit == "%" and ev.risk == risk and ev.uncertainty == echo_ef.MAE
    assert ev.provenance.dataset_license.startswith("Stanford")
    assert ef_risk(ef) == risk


def test_abstain_cases(tmp_path):
    a = adapter(55)
    assert a.analyze(video(tmp_path), age_years=7).abstained
    assert a.analyze(tmp_path / "yoq.avi").abstained
    assert adapter(3).analyze(video(tmp_path)).abstained                 # fiziologik emas
    bad = tmp_path / "bad.avi"
    bad.write_bytes(b"xx")
    assert a.analyze(bad).abstained


def test_from_env_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("CARDIOPATH_EF_WEIGHTS", str(tmp_path / "yoq.onnx"))
    assert EchoEFAdapter.from_env() is None
