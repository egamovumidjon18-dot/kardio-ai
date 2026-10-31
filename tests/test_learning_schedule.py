"""O'z-o'zini o'rgatish jadvali: vaqti kelganda bir marta, ustma-ust emas, torch yo'q bo'lsa xavfsiz o'tkazib yuboriladi."""
import json
import threading
from datetime import datetime, timedelta, timezone

from learning.schedule import is_due, maybe_run_cycle


def test_due_logic(tmp_path):
    assert is_due(tmp_path, 168)                                      # hali sikl bo'lmagan
    now = datetime.now(timezone.utc)
    (tmp_path / "last_cycle.json").write_text(json.dumps({"finished_at": (now - timedelta(hours=10)).isoformat()}))
    assert not is_due(tmp_path, 168, now) and is_due(tmp_path, 8, now)


def test_runs_when_due_and_never_overlaps(tmp_path):
    calls, gate = [], threading.Event()

    def slow():
        calls.append(1); gate.wait(2); return {"status": "candidate_ready"}

    t = threading.Thread(target=maybe_run_cycle, args=(None, tmp_path, tmp_path, 1, slow)); t.start()
    while not calls:
        pass
    assert maybe_run_cycle(None, tmp_path, tmp_path, 1, slow) is None   # birinchisi ishlayapti — ikkinchisi boshlanmaydi
    gate.set(); t.join()
    assert len(calls) == 1


def test_missing_torch_is_recorded_not_crashing(tmp_path):
    def no_torch():
        raise ImportError("No module named 'torch'")
    res = maybe_run_cycle(None, tmp_path, tmp_path, 1, no_torch)
    assert res["status"] == "no_training_env"
    assert json.loads((tmp_path / "last_cycle.json").read_text())["status"] == "no_training_env"
    assert maybe_run_cycle(None, tmp_path, tmp_path, 1, no_torch) is None   # keyingi urinish jadval bo'yicha
