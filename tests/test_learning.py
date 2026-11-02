"""O'z-o'zini o'rgatish: versiyalar, inson tasdig'i, darvozalar, sikl va holat API'si.

Haqiqiy o'qitish bu yerda emas (u sekin): sikl tartibi soxta dvigatel bilan, darvozalar aniq raqamlar bilan sinaladi.
"""
import json
import hashlib
import random
import uuid
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.registry import ModelCard
from core.store import SqliteEpisodeStore
from learning.cycle import run_cycle
from learning.dataset import CHD_POSITIVE, bucket, label_of, split_children, to_patients, usable
from learning.gates import CFG, dataset_gate, model_gate, paired_bootstrap_delta
from learning.versions import ModelVersions, PromotionError, resolve_weights_dir
from research.export_local import _auroc, collect_children
from screening.model import PCGModel


# ---------------------------------------------------------------- ma'lumot bo'linishi
def test_bucket_is_stable_and_roughly_proportional():
    ids = [f"ep{i:05d}" for i in range(4000)]
    assert [bucket(i) for i in ids[:50]] == [bucket(i) for i in ids[:50]]
    c = Counter(bucket(i) for i in ids)
    assert 0.22 < c["test"] / 4000 < 0.28 and 0.12 < c["val"] / 4000 < 0.18 and 0.55 < c["train"] / 4000 < 0.65


def kid(i, dx, age=900, device="S1", t=None):
    return {"eid": f"e{i:04d}", "patient_key": f"e{i:04d}", "created_at": t or f"2026-11-{1 + i // 40:02d}T{i % 24:02d}:{i % 60:02d}:00", "dx": dx,
            "device": device, "age_days": age, "files": [{"location": "MV", "file": "MV.wav", "path": "x.wav"}]}


def test_usable_excludes_ambiguous_and_neonates_and_labels_are_binary():
    ch = [kid(0, "VSD"), kid(1, "NORMAL"), kid(2, "PFO"), kid(3, "OTHER"), kid(4, "ASD", age=10), kid(5, "NORMAL", age=None)]
    assert [c["eid"] for c in usable(ch)] == ["e0000", "e0001"]
    assert label_of("VSD") == 1 and label_of("NORMAL") == 0 and label_of("PFO") is None
    assert all(label_of(d) == 1 for d in CHD_POSITIVE)
    pts = to_patients([kid(0, "VSD"), kid(1, "NORMAL")])
    assert [p["murmur"] for p in pts] == ["Present", "Absent"] and pts[0]["recordings"][0]["murmur"] == 1
    split = split_children([kid(i, "VSD" if i % 2 else "NORMAL") for i in range(200)])
    assert sum(len(v) for v in split.values()) == 200 and not (
        {c["eid"] for c in split["train"]} & {c["eid"] for c in split["test"]})


# ---------------------------------------------------------------- ma'lumot darvozasi
def balanced(n=120, **kw):
    return [kid(i, "VSD" if i % 2 else "NORMAL", **kw) for i in range(n)]


def failed(gate):
    return {g["name"] for g in gate["items"] if not g["passed"]}


def test_dataset_gate_passes_for_clean_interleaved_collection():
    g = dataset_gate(balanced())
    assert g["passed"], failed(g)


def test_dataset_gate_blocks_sequential_collection_the_zchsound_mistake():
    seq = [kid(i, "NORMAL" if i < 60 else "VSD") for i in range(120)]                  # avval hamma sog'lar, keyin kasallar
    assert "yig'ish tartibi aralash (tashxis bilan ketma-ket emas)" in failed(dataset_gate(seq))


def test_dataset_gate_blocks_device_that_recorded_one_class_only():
    ch = [kid(i, "VSD" if i % 2 else "NORMAL", device="B" if i % 2 else "A") for i in range(120)]
    assert "qurilmalar ikkala sinfni yozgan" in failed(dataset_gate(ch))


def test_dataset_gate_blocks_too_little_data_and_single_class():
    assert "yetarli bola" in failed(dataset_gate(balanced(20)))
    assert "har sinfdan yetarli" in failed(dataset_gate([kid(i, "NORMAL") for i in range(100)] + [kid(900 + i, "VSD") for i in range(3)]))


# ---------------------------------------------------------------- model darvozasi
def metric(auroc, sens=0.9, abstain=0.05):
    return {"auroc": auroc, "sensitivity": sens, "abstain_rate": abstain}


CHAMP = {"local": metric(0.70), "circor": metric(0.95)}


def test_paired_bootstrap_detects_real_improvement_and_no_difference():
    rng = random.Random(1)
    y = [i % 2 for i in range(80)]
    old = [yy * 0.3 + rng.random() for yy in y]
    better = [yy * 1.2 + rng.random() * 0.5 for yy in y]
    d, lo, hi = paired_bootstrap_delta(y, better, old, n=400)
    assert d > 0.1 and lo > 0
    d0, lo0, hi0 = paired_bootstrap_delta(y, old, old, n=200)
    assert d0 == 0 and lo0 == 0 and hi0 == 0
    assert _auroc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)


def test_model_gate_passes_only_when_everything_holds():
    chall = {"local": metric(0.85), "circor": metric(0.94)}
    g = model_gate(CHAMP, chall, (0.15, 0.05, 0.25), control_auroc=0.70)
    assert g["passed"], failed(g)


@pytest.mark.parametrize("what,chall,delta,control,gate_name", [
    ("kichik yaxshilanish", {"local": metric(0.71), "circor": metric(0.95)}, (0.01, -0.05, 0.07), 0.70, "mahalliy testda sifat ishonchli oshdi"),
    ("ishonch oralig'i nolni kesadi", {"local": metric(0.80), "circor": metric(0.95)}, (0.10, -0.02, 0.2), 0.70, "mahalliy testda sifat ishonchli oshdi"),
    ("CirCor'da yomonlashdi", {"local": metric(0.85), "circor": metric(0.90)}, (0.15, 0.05, 0.25), 0.70, "CirCor testida yomonlashmadi"),
    ("abstain oshdi", {"local": metric(0.85, abstain=0.20), "circor": metric(0.95)}, (0.15, 0.05, 0.25), 0.70, "«javob bermadi» ulushi oshmadi (mahalliy)"),
    ("sezgirlik tushdi", {"local": metric(0.85, sens=0.70), "circor": metric(0.95)}, (0.15, 0.05, 0.25), 0.70, "sezgirlik pasaymadi (mahalliy)"),
    ("nazorat ham yaxshilandi (sizib chiqish)", {"local": metric(0.90), "circor": metric(0.95)}, (0.20, 0.10, 0.3), 0.82, "aralashtirilgan belgilar nomzodni «yaxshilamaydi» (sizib chiqish yo'q)"),
    ("belgilar foyda bermadi", {"local": metric(0.85), "circor": metric(0.95)}, (0.15, 0.05, 0.25), 0.84, "haqiqiy belgilar aralashtirilganidan yaxshiroq (mahalliy belgilar foyda berdi)"),
    ("nazorat o'tkazilmadi", {"local": metric(0.85), "circor": metric(0.95)}, (0.15, 0.05, 0.25), None, "salbiy nazorat o'tkazildi"),
])
def test_model_gate_blocks_each_failure(what, chall, delta, control, gate_name):
    g = model_gate(CHAMP, chall, delta, control)
    assert not g["passed"] and gate_name in failed(g), (what, failed(g))


def test_model_gate_is_safe_against_nan():
    nan = float("nan")
    g = model_gate(CHAMP, {"local": metric(0.85, sens=nan, abstain=nan), "circor": metric(nan)}, (0.15, 0.05, 0.25), 0.70)
    assert not g["passed"]


# ---------------------------------------------------------------- versiyalar va inson tasdig'i
def make_files(tmp_path, name="a"):
    d = tmp_path / f"src_{name}"
    d.mkdir()
    (d / "pcg.onnx").write_bytes(b"onnx")
    (d / "pcg.pt").write_bytes(b"pt")
    (d / "model_card.json").write_text(json.dumps({"name": "pcg_murmur_cnn", "version": name, "task": "t",
                                                   "dataset": "CirCor DigiScope + mahalliy ma'lumot", "weights": "pcg.onnx"}), encoding="utf-8")
    return {n: d / n for n in ("pcg.onnx", "pcg.pt", "model_card.json")}


def report(passed=True):
    return {"children_ids": ["a"], "gates": {"passed": passed, "items": [{"name": "g1", "passed": passed, "detail": "d"}]}}


def test_candidate_is_never_current_and_promotion_needs_named_clinician(tmp_path):
    mv = ModelVersions(tmp_path / "m")
    v = mv.add_candidate(make_files(tmp_path), report())
    assert mv.current() is None and mv.latest_candidate() == v
    for bad in ("", "  ", "ab"):
        with pytest.raises(PromotionError, match="ismi"):
            mv.promote(v, bad)
    assert mv.current() is None                                   # tasdiqsiz hech narsa o'zgarmadi
    mv.promote(v, "Dr. Karimova", "mahalliy test yaxshilandi")
    assert mv.current() == v and mv.latest_candidate() is None
    assert [h["event"] for h in mv.history()] == ["candidate_created", "promoted"]
    assert mv.history()[-1]["by"] == "Dr. Karimova"
    with pytest.raises(PromotionError, match="allaqachon joriy"):
        mv.promote(v, "Dr. Karimova")


def test_failed_candidate_cannot_be_promoted(tmp_path):
    mv = ModelVersions(tmp_path / "m")
    v = mv.add_candidate(make_files(tmp_path), report(passed=False))
    with pytest.raises(PromotionError, match="darvozalardan o'tmagan.*g1"):
        mv.promote(v, "Dr. Karimova")
    assert mv.current() is None
    with pytest.raises(PromotionError, match="topilmadi"):
        mv.promote("v-yoq", "Dr. Karimova")


def test_rollback_restores_previous_or_baseline_and_is_logged(tmp_path):
    mv = ModelVersions(tmp_path / "m")
    v1 = mv.add_candidate(make_files(tmp_path, "a"), report())
    v2 = mv.add_candidate(make_files(tmp_path, "b"), report())
    mv.promote(v1, "Dr. Karimova"); mv.promote(v2, "Dr. Karimova")
    assert mv.rollback("Dr. Aliyev", "sezgirlik pasaydi") == v1 and mv.current() == v1
    assert mv.rollback("Dr. Aliyev") is None and mv.current() is None           # bazaviy modelga
    with pytest.raises(PromotionError, match="yo'q"):
        mv.rollback("Dr. Aliyev")
    with pytest.raises(PromotionError, match="ismi"):
        mv.rollback("")
    ev = [(h["event"], h["by"]) for h in mv.history()]
    assert ev.count(("rolled_back", "Dr. Aliyev")) == 2 and ("promoted", "Dr. Karimova") in ev


def test_resolve_weights_prefers_explicit_then_approved_then_baseline(tmp_path):
    mv = ModelVersions(tmp_path / "m")
    assert resolve_weights_dir("weights/pcg", tmp_path / "m") == (Path("weights/pcg"), "baseline")
    v = mv.add_candidate(make_files(tmp_path), report())
    assert resolve_weights_dir("weights/pcg", tmp_path / "m")[1] == "baseline"       # nomzod tasdiqlanmaguncha ishlatilmaydi
    mv.promote(v, "Dr. Karimova")
    d, label = resolve_weights_dir("weights/pcg", tmp_path / "m")
    assert label == v and d == mv.weights_dir(v)
    assert resolve_weights_dir("weights/pcg", tmp_path / "m", explicit="custom") == (Path("custom"), "explicit")


# ---------------------------------------------------------------- sikl (soxta dvigatel)
CARD = ModelCard(name="pcg_test", version="0", task="t", dataset="CirCor DigiScope", weights="none")


@pytest.fixture(scope="module")
def clinic(tmp_path_factory):
    """120 ta tasdiqlangan bola (sog'/kasal navbatma-navbat) — haqiqiy API orqali, rozilik va ExoKG tashxisi bilan."""
    from tests.conftest import make_wav
    root = tmp_path_factory.mktemp("clinic")
    store, rec = SqliteEpisodeStore(str(root / "c.db")), root / "rec"
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.1, np.float32), np.zeros(len(x), np.float32)))
    client = TestClient(create_app(store, model, recordings_dir=rec))
    # Explicit balanced patient partitions; episode UUIDs do not determine the split.
    refs = []
    for i in range(120):
        target = "test" if i % 10 < 3 else "val" if i % 10 < 5 else "train"
        n = 0
        while True:
            ref = f"K-{i}-{n}"
            if bucket(hashlib.sha256(ref.casefold().encode()).hexdigest()) == target:
                refs.append(ref)
                break
            n += 1
    rnd = random.Random(0)
    with patch("core.episode.uuid.uuid4", lambda: uuid.UUID(int=rnd.getrandbits(128), version=4)):
        eids = [client.post("/episodes", json={"patient_ref": ref}).json()["id"] for ref in refs]
    for i, eid in enumerate(eids):
        client.post(f"/episodes/{eid}/screening", data={"actor": "dr", "age_days": "900", "research_consent": "true", "device": "S1"},
                    files=[("recordings", ("MV.wav", make_wav(seed=i), "audio/wav"))])
        client.post(f"/episodes/{eid}/echo-diagnosis", json={"actor": "dr", "diagnosis": "VSD" if i % 2 else "NORMAL"})
    return store, rec


class FakeEngine:
    """Soxta dvigatel: yaxshi nomzod (good=True) yoki yaxshilanmagan (good=False). train chaqirilganini hisoblaydi."""

    def __init__(self, tmp_path, good=True, control=0.50):
        self.tmp, self.good, self.control_auroc, self.trained = tmp_path, good, control, 0

    def train(self, split):
        self.trained += 1
        return make_files(self.tmp, f"cand{self.trained}")

    def evaluate(self, model_dir, split):
        challenger = Path(model_dir).name.startswith("src_cand")           # papka NOMI bo'yicha (pytest tmp yo'lida «cand» uchrashi mumkin)
        rng = random.Random(7)
        rows = []
        for c in split["test"]:
            y = label_of(c["dx"])
            strength = (1.4 if self.good else 0.3) if challenger else 0.3
            rows.append({"id": c["eid"], "murmur": "Present" if y else "Absent", "p": y * strength + rng.random()})
        ys = [int(r["murmur"] == "Present") for r in rows]
        auc = _auroc(ys, [r["p"] for r in rows])
        circor = metric(0.95 if not challenger else (0.945 if self.good else 0.945))
        return {"local": {**metric(auc), "n": len(rows)}, "circor": circor, "rows_local": rows}

    def control(self, split):
        return self.control_auroc


def test_cycle_waits_for_enough_new_children_and_does_not_train(clinic, tmp_path):
    store, rec = clinic
    eng = FakeEngine(tmp_path)
    mv = ModelVersions(tmp_path / "m")
    res = run_cycle(store, rec, mv, tmp_path, eng, cfg={**CFG, "min_new": 500})
    assert res["status"] == "not_enough_new" and eng.trained == 0 and mv.list() == []
    assert (tmp_path / "m" / "last_cycle.json").exists()


def test_cycle_rejects_bad_dataset_before_training(tmp_path):
    from tests.conftest import make_wav
    store, rec = SqliteEpisodeStore(str(tmp_path / "bad.db")), tmp_path / "rec"
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.1, np.float32), np.zeros(len(x), np.float32)))
    client = TestClient(create_app(store, model, recordings_dir=rec))
    for i in range(80):                                            # avval 40 sog', keyin 40 kasal — ZCHSound xatosi
        eid = client.post("/episodes", json={"patient_ref": f"B-{i}"}).json()["id"]
        client.post(f"/episodes/{eid}/screening", data={"actor": "dr", "age_days": "900", "research_consent": "true", "device": "S1"},
                    files=[("recordings", ("MV.wav", make_wav(seed=i), "audio/wav"))])
        client.post(f"/episodes/{eid}/echo-diagnosis", json={"actor": "dr", "diagnosis": "NORMAL" if i < 40 else "VSD"})
    eng, mv = FakeEngine(tmp_path), ModelVersions(tmp_path / "m")
    res = run_cycle(store, rec, mv, tmp_path, eng, cfg={**CFG, "min_new": 10})
    assert res["status"] == "dataset_rejected" and eng.trained == 0 and mv.list() == []
    assert "yig'ish tartibi aralash (tashxis bilan ketma-ket emas)" in res["failed"]


def test_cycle_creates_candidate_but_never_promotes_automatically(clinic, tmp_path):
    store, rec = clinic
    eng, mv = FakeEngine(tmp_path, good=True, control=0.50), ModelVersions(tmp_path / "m")
    res = run_cycle(store, rec, mv, tmp_path, eng, cfg={**CFG, "min_new": 10})
    assert res["status"] == "candidate_ready", [g for g in res["gates"]["items"] if not g["passed"]]
    assert mv.current() is None and eng.trained == 1              # TASDIQSIZ joriy bo'lmadi
    rep = mv.report(res["version"])
    assert len(rep["children_ids"]) == 120 and rep["delta_local"]["n_paired"] == rep["split_counts"]["test"] and rep["note"]
    # xuddi shu bolalar bilan qayta ishga tushirsa — yangi bola yo'q
    again = run_cycle(store, rec, mv, tmp_path, eng, cfg={**CFG, "min_new": 10})
    assert again["status"] == "not_enough_new" and again["n_new"] == 0 and eng.trained == 1
    forced = run_cycle(store, rec, mv, tmp_path, eng, force=True, cfg={**CFG, "min_new": 10})
    assert forced["status"] in ("candidate_ready", "candidate_failed") and eng.trained == 2
    # inson tasdig'idan keyingina joriy bo'ladi
    mv.promote(res["version"], "Dr. Karimova", "test")
    assert resolve_weights_dir("weights/pcg", tmp_path / "m")[1] == res["version"]


def test_cycle_flags_candidate_that_did_not_improve_and_blocks_promotion(clinic, tmp_path):
    store, rec = clinic
    eng, mv = FakeEngine(tmp_path, good=False), ModelVersions(tmp_path / "m")
    res = run_cycle(store, rec, mv, tmp_path, eng, cfg={**CFG, "min_new": 10})
    assert res["status"] == "candidate_failed"
    assert "mahalliy testda sifat ishonchli oshdi" in failed(res["gates"])
    with pytest.raises(PromotionError, match="darvozalardan o'tmagan"):
        mv.promote(res["version"], "Dr. Karimova")
    assert mv.current() is None


def test_cycle_blocks_candidate_when_control_shows_leakage(clinic, tmp_path):
    store, rec = clinic
    eng, mv = FakeEngine(tmp_path, good=True, control=0.95), ModelVersions(tmp_path / "m")      # aralashtirilgan belgilar ham «yaxshiladi»
    res = run_cycle(store, rec, mv, tmp_path, eng, cfg={**CFG, "min_new": 10})
    assert res["status"] == "candidate_failed"
    assert "aralashtirilgan belgilar nomzodni «yaxshilamaydi» (sizib chiqish yo'q)" in failed(res["gates"])


# ---------------------------------------------------------------- holat API'si
def test_learning_status_api(clinic, tmp_path):
    store, rec = clinic
    mdir = tmp_path / "models"
    mv = ModelVersions(mdir)
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.1, np.float32), np.zeros(len(x), np.float32)))
    client = TestClient(create_app(store, model, recordings_dir=rec, models_dir=mdir, running_version="baseline"))
    s = client.get("/learning/status").json()
    assert s["current_version"] == "baseline" and s["latest_candidate"] is None and s["restart_needed"] is False
    assert s["data"]["confirmed_children"] == 120 and s["data"]["new_since_last_candidate"] == 120
    assert s["data"]["dataset_gate"]["passed"] is True and s["thresholds"]["min_new"] == CFG["min_new"]

    eng = FakeEngine(tmp_path, good=True)
    res = run_cycle(store, rec, mv, tmp_path, eng, cfg={**CFG, "min_new": 10})
    s = client.get("/learning/status").json()
    cand = s["latest_candidate"]
    assert cand["version"] == res["version"] and cand["passed"] is True and cand["needs_human_approval"] is True
    assert "--approved-by" in cand["promote_command"] and s["data"]["new_since_last_candidate"] == 0
    assert s["last_cycle"]["status"] == "candidate_ready" and s["restart_needed"] is False

    mv.promote(res["version"], "Dr. Karimova")                       # tasdiqlandi, lekin ilova hali eski modelda
    s = client.get("/learning/status").json()
    assert s["current_version"] == res["version"] and s["restart_needed"] is True and s["running_version"] == "baseline"
    assert any(h["event"] == "promoted" and h["by"] == "Dr. Karimova" for h in s["history"])
    # kirish tizimisiz tasdiqlash API'si HECH QACHON ishlamaydi (kirish bilan: tests/test_auth.py)
    assert client.post("/learning/promote", json={"version": res["version"]}).status_code == 403
    assert client.post("/learning/rollback", json={"note": "sabab yo'q emas"}).status_code == 403


def test_health_reports_running_model_version(tmp_path):
    client = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "h.db")), None, running_version="v20261101-1"))
    assert client.get("/health").json()["pcg_version"] == "v20261101-1"
    assert client.get("/learning/status").status_code == 404            # models_dir berilmasa, endpoint yo'q
