"""Mahalliy ma'lumot eksportidagi himoya: yig'ish tartibi yoki qurilma tashxis bilan aralashib ketmasin
(ZCHSound'da fayl raqami tashxisni 100% bashorat qilar edi — shu xato bizning ma'lumotda takrorlanmasin)."""
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import ModelCard
from core.store import SqliteEpisodeStore
from research import export_local
from research.export_local import _auroc, collection_confound
from screening.model import PCGModel


def kids(order, devices=None):
    """order: 'N'/'D' ketma-ketligi → epizod: (vaqt, tashxis, qurilma)."""
    return {f"e{i}": (f"2026-11-{1 + i // 24:02d}T{i % 24:02d}:00:00", "NORMAL" if c == "N" else "VSD",
                      (devices[i] if devices else "scopeA")) for i, c in enumerate(order)}


def test_rank_auroc_matches_known_values():
    assert _auroc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert _auroc([0, 1], [0.5, 0.5]) == pytest.approx(0.5)
    assert _auroc([0, 0, 1, 1], [1, 2, 3, 4]) == pytest.approx(1.0)


def test_sequential_collection_is_flagged():
    r = collection_confound(kids("N" * 20 + "D" * 20))             # avval hamma sog'lar, keyin hamma kasallar
    assert r["order_auroc"] == 1.0 and r["order_warn"] is True


def test_reversed_sequential_is_also_flagged():
    assert collection_confound(kids("D" * 20 + "N" * 20))["order_warn"] is True


def test_interleaved_collection_is_clean():
    r = collection_confound(kids("ND" * 20))
    assert r["order_warn"] is False and r["order_auroc"] < 0.6


def test_too_little_data_gives_no_verdict():
    assert collection_confound(kids("N" * 5 + "D" * 5)) is None            # n < 20
    assert collection_confound(kids("N" * 28 + "D" * 2)) is None           # kasallar 5 tadan kam


def test_device_that_only_recorded_one_class_is_flagged():
    order = "ND" * 20
    devs = ["scopeA" if c == "N" else "scopeB" for c in order]               # A faqat sog'lar, B faqat kasallar
    r = collection_confound(kids(order, devs))
    assert r["device_warn"] is True and r["order_warn"] is False


def test_mixed_devices_are_clean():
    order = "ND" * 20
    devs = ["scopeA" if i % 4 < 2 else "scopeB" for i in range(len(order))]  # ikkala qurilma ikkala sinfni yozgan
    assert collection_confound(kids(order, devs))["device_warn"] is False


# ---- eksport buyrug'i oxirigacha
CARD = ModelCard(name="pcg_test", version="0", task="t", dataset="CirCor DigiScope", weights="none")


def build(tmp_path, wav_factory, pattern):
    db, rec = tmp_path / "g.db", tmp_path / "rec"
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.1, np.float32), np.zeros(len(x), np.float32)))
    client = TestClient(create_app(SqliteEpisodeStore(str(db)), model, recordings_dir=rec))
    for i, c in enumerate(pattern):
        eid = client.post("/episodes", json={"patient_ref": f"K-{i}"}).json()["id"]
        client.post(f"/episodes/{eid}/screening", data={"actor": "dr", "age_days": "900", "research_consent": "true", "device": "S1"},
                    files=[("recordings", ("MV.wav", wav_factory(seed=i), "audio/wav"))])
        client.post(f"/episodes/{eid}/echo-diagnosis", json={"actor": "dr", "diagnosis": "NORMAL" if c == "N" else "VSD"})
    return db, rec


def run_export(monkeypatch, capsys, db, rec, out):
    monkeypatch.setattr(sys, "argv", ["x", "--db", str(db), "--recordings", str(rec), "--out", str(out)])
    export_local.main()
    return capsys.readouterr().out


def test_cli_warns_on_sequential_and_stays_quiet_on_interleaved(tmp_path, wav_factory, monkeypatch, capsys):
    (tmp_path / "seq").mkdir()
    db, rec = build(tmp_path / "seq", wav_factory, "N" * 12 + "D" * 12)
    out = run_export(monkeypatch, capsys, db, rec, tmp_path / "seq_out")
    assert "DIQQAT: yozuvlar tashxis bo'yicha deyarli ketma-ket" in out and "AUROC 1.00" in out

    (tmp_path / "mix").mkdir()
    db2, rec2 = build(tmp_path / "mix", wav_factory, "ND" * 12)
    out2 = run_export(monkeypatch, capsys, db2, rec2, tmp_path / "mix_out")
    assert "DIQQAT" not in out2 and "yig'ish tartibi tekshiruvi: tartib bilan tashxis AUROC" in out2
