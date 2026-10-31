"""Shadow mode: dasturga ulanmagan (yoki yangi) model haqiqiy klinik EKG'da JIMGINA ishlaydi.

Qoidalar:
  * shadow model javobi shifokorga, bemorga, xulosaga va eskalatsiyaga HECH QACHON chiqmaydi — faqat shu jadvalga yoziladi;
  * shadow xatosi asosiy (ulangan) yo'lni hech qachon buzmaydi;
  * shifokor EKG'ni o'zi o'qib ritmni kiritadi (yorliq). Yorliq kiritish ro'yxatida model javoblari KO'RSATILMAYDI (ko'r baholash);
  * hisobotda faqat umumlashgan ko'rsatkichlar bor; ko'rsatkichlar yetarli holat to'planmaguncha «hali erta» deb belgilanadi.
Bu ochiq to'plamlar tugagandan keyin modelni yangi, mustaqil, mahalliy ma'lumotda halol tekshirishning yagona yo'li.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.identity import effective_actor
from core.registry import ModelCard, check_license
from core.evidence import utcnow
from ecg.signal import LEADS_12, assess_quality, preprocess, select_leads

RHYTHM_LABELS = ("SR", "SBRAD", "STACH", "AFIB", "AFL", "SVT", "OTHER")
FAST = ("AFL", "SVT", "STACH")
# Ko'rsatkichlarni talqin qilishdan oldin kerak bo'lgan eng kam holat soni (oldindan belgilangan, keyin o'zgartirilmaydi)
MIN_AFIB, MIN_NON_AFIB = 30, 100

# backend: [N, 12, 1000] → [N, n_classes] logit
Backend = Callable[[np.ndarray], np.ndarray]


def onnx_logits(path: str | Path) -> Backend:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    return lambda x: sess.run(None, {name: x})[0]


@dataclass
class ShadowRhythmModel:
    """Softmax ritm modeli (train_rhythm / train_afib_multi*): SR, SBRAD, STACH, AFIB, AFL, SVT."""
    card: ModelCard
    backend: Backend

    def __post_init__(self) -> None:
        check_license(self.card)
        th = self.card.thresholds
        self.classes = list(th["classes"])
        self.afib_threshold = float(th["afib_threshold"])

    @property
    def key(self) -> str:
        return f"{self.card.name}@{self.card.version}"

    @classmethod
    def from_dir(cls, d: str | Path) -> Optional["ShadowRhythmModel"]:
        """Qabul mezonidan o'tmagan model ham yuklanadi — shadow aynan shular uchun. Fayl bo'lmasa None."""
        d = Path(d)
        if not (d / "model_card.json").exists():
            return None
        card = ModelCard.load(d / "model_card.json")
        if not (d / card.weights).exists():
            return None
        return cls(card, onnx_logits(d / card.weights))

    def run(self, signal: np.ndarray, fs: float, leads: tuple[str, ...]) -> dict:
        try:
            x12 = select_leads(np.asarray(signal, dtype=np.float32), tuple(leads), LEADS_12)
        except ValueError as exc:
            return {"abstained": str(exc)}
        q = assess_quality(x12, fs, LEADS_12)
        if not q.ok:
            return {"abstained": "sifatsiz EKG: " + "; ".join(q.reasons)}
        lg = np.asarray(self.backend(preprocess(x12, fs)[None].astype(np.float32))[0], dtype=np.float64)
        p = np.exp(lg - lg.max()); p /= p.sum()
        probs = {c: round(float(p[i]), 4) for i, c in enumerate(self.classes)}
        return {"probabilities": probs, "top": self.classes[int(p.argmax())], "afib_call": probs["AFIB"] >= self.afib_threshold}


def input_hash(signal: np.ndarray, fs: float) -> str:
    h = hashlib.sha256(np.ascontiguousarray(signal, dtype=np.float32).tobytes())
    h.update(str(float(fs)).encode())
    return h.hexdigest()


def _rates(calls: list[bool], truth: list[str]) -> dict:
    c, t = np.array(calls, dtype=bool), np.array(truth)
    af, fast = t == "AFIB", np.isin(t, FAST)
    out = {"n": int(len(t)), "n_afib": int(af.sum())}
    out["sensitivity"] = round(float(c[af].mean()), 4) if af.any() else None
    out["specificity"] = round(float((~c[~af]).mean()), 4) if (~af).any() else None
    out["fast_called_afib"] = round(float(c[fast].mean()), 4) if fast.any() else None
    return out


class ShadowStore:
    def __init__(self, path: str = "cardiopath.db") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS shadow_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id TEXT NOT NULL, "
                "kind TEXT NOT NULL, input_sha256 TEXT, age_years REAL, live TEXT, shadow TEXT, created_at TEXT)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS shadow_labels (run_id INTEGER PRIMARY KEY, rhythm TEXT NOT NULL, "
                "actor TEXT, note TEXT, at TEXT)")

    def add_run(self, episode_id: str, kind: str, input_sha256: str, age_years: Optional[float],
                live: dict, shadow: dict) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO shadow_runs (episode_id, kind, input_sha256, age_years, live, shadow, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (episode_id, kind, input_sha256, age_years, json.dumps(live, ensure_ascii=False),
                 json.dumps(shadow, ensure_ascii=False), utcnow()))
            return int(cur.lastrowid)

    def pending(self, limit: int = 50) -> list[dict]:
        """Yorliq kutayotgan EKG'lar. Model javoblari ATAYLAB qaytarilmaydi."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT r.id, r.episode_id, r.created_at FROM shadow_runs r LEFT JOIN shadow_labels l ON l.run_id = r.id "
                "WHERE l.run_id IS NULL ORDER BY r.id LIMIT ?", (limit,)).fetchall()
        return [{"run_id": a, "episode_id": b, "created_at": c} for a, b, c in rows]

    def label(self, run_id: int, rhythm: str, actor: str, note: str = "") -> bool:
        if rhythm not in RHYTHM_LABELS:
            raise ValueError(f"ritm {RHYTHM_LABELS} dan biri bo'lishi kerak")
        with self._lock, self._conn:
            if self._conn.execute("SELECT 1 FROM shadow_runs WHERE id = ?", (run_id,)).fetchone() is None:
                return False
            self._conn.execute(
                "INSERT INTO shadow_labels (run_id, rhythm, actor, note, at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET rhythm = excluded.rhythm, actor = excluded.actor, "
                "note = excluded.note, at = excluded.at",
                (run_id, rhythm, effective_actor(actor), note, utcnow()))
        return True

    def report(self) -> dict:
        """Shifokor yorlig'i bilan solishtirish: ulangan model va har bir shadow model, faqat ikkalasi ham javob bergan holatlarda."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT r.live, r.shadow, l.rhythm FROM shadow_runs r JOIN shadow_labels l ON l.run_id = r.id").fetchall()
            total = self._conn.execute("SELECT COUNT(*) FROM shadow_runs").fetchone()[0]
        per: dict[str, dict[str, list]] = {}
        for live_s, shadow_s, rhythm in rows:
            if rhythm == "OTHER":
                continue
            live = json.loads(live_s)
            if live.get("abstained") or "afib_call" not in live:
                continue
            for key, out in json.loads(shadow_s).items():
                if "afib_call" not in out:
                    continue
                d = per.setdefault(key, {"live": [], "shadow": [], "truth": [], "agree": []})
                d["live"].append(bool(live["afib_call"])); d["shadow"].append(bool(out["afib_call"]))
                d["truth"].append(rhythm); d["agree"].append(out.get("top") == rhythm)
        models = {}
        for key, d in per.items():
            n_af = sum(t == "AFIB" for t in d["truth"])
            models[key] = {"live_model": _rates(d["live"], d["truth"]), "shadow_model": _rates(d["shadow"], d["truth"]),
                           "rhythm_agreement": round(float(np.mean(d["agree"])), 4),
                           "ready": n_af >= MIN_AFIB and len(d["truth"]) - n_af >= MIN_NON_AFIB}
        return {"runs": int(total), "labeled": len(rows), "min_required": {"afib": MIN_AFIB, "non_afib": MIN_NON_AFIB},
                "models": models}
