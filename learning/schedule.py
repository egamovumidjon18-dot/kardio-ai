"""O'z-o'zini o'rgatish siklini jadval bo'yicha ishga tushirish (ixtiyoriy).

Sikl faqat NOMZOD tayyorlaydi: joriy model hech qachon avtomatik almashmaydi — kardiolog «Modellar» sahifasida tasdiqlaydi.
Yoqish: CARDIOPATH_LEARNING_EVERY_H=168 (soat) + CARDIOPATH_CIRCOR_DIR + CARDIOPATH_RECORDINGS. torch bo'lmasa (masalan Docker
obrazi), sikl o'tkazib yuboriladi va sababi last_cycle.json ga yoziladi.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from core.evidence import utcnow
from core.store import EpisodeStore

log = logging.getLogger("cardiopath.learning")
_running = threading.Lock()


def last_finished(models_dir: Path) -> Optional[datetime]:
    p = Path(models_dir) / "last_cycle.json"
    if not p.exists():
        return None
    try:
        at = json.loads(p.read_text(encoding="utf-8")).get("finished_at")
        return datetime.fromisoformat(at) if at else None
    except (ValueError, OSError):
        return None


def is_due(models_dir: Path, every_h: float, now: Optional[datetime] = None) -> bool:
    last = last_finished(models_dir)
    now = now or datetime.now(timezone.utc)
    return last is None or now - last >= timedelta(hours=every_h)


def maybe_run_cycle(store: EpisodeStore, recordings_dir: Path, models_dir: Path, every_h: float,
                    run: Callable[[], dict], now: Optional[datetime] = None) -> Optional[dict]:
    """Vaqti kelgan bo'lsa va boshqa sikl ishlamayotgan bo'lsa — `run()` ni bajaradi. Aks holda None."""
    if not is_due(models_dir, every_h, now) or not _running.acquire(blocking=False):
        return None
    try:
        return run()
    except ImportError as exc:                     # torch yo'q (Docker obrazi) — o'qitish muhiti emas
        res = {"status": "no_training_env", "message": f"o'qitish uchun torch kerak: {exc}", "finished_at": utcnow()}
        Path(models_dir).mkdir(parents=True, exist_ok=True)
        (Path(models_dir) / "last_cycle.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        return res
    finally:
        _running.release()


def real_runner(store: EpisodeStore, recordings_dir: Path, models_dir: Path, circor_dir: Path,
                baseline_dir: Path = Path("weights/pcg")) -> Callable[[], dict]:
    def run() -> dict:
        from learning.cycle import run_cycle
        from learning.training import RealEngine              # torch shu yerda import qilinadi
        from learning.versions import ModelVersions, resolve_weights_dir
        versions = ModelVersions(models_dir)
        champion_dir, _ = resolve_weights_dir(baseline_dir, models_dir)
        engine = RealEngine(circor_dir, champion_dir, Path(models_dir) / "work")
        res = run_cycle(store, recordings_dir, versions, champion_dir, engine)
        log.warning("o'z-o'zini o'rgatish sikli: %s", res.get("status"))
        return res
    return run
