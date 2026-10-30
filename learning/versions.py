"""Model versiyalari: nomzod → (INSON TASDIG'I bilan) joriy → kerak bo'lsa orqaga qaytarish.

Qoida: hech qaysi model jimgina almashtirilmaydi. Nomzod faqat (1) barcha avtomatik darvozalardan o'tgan bo'lsa va
(2) ismi aniq ko'rsatilgan shifokor tasdiqlasa joriy bo'ladi. Har bir hodisa `history.jsonl` ga faqat qo'shiladi.

Papka tuzilishi (<root> = models/pcg):
    versions/<id>/{pcg.onnx, pcg.pt, model_card.json, report.json}     — har bir nomzod
    state.json                                                          — joriy versiya va tasdiqlanganlar stegi
    history.jsonl                                                       — yaratildi / tasdiqlandi / qaytarildi
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from core.evidence import utcnow

MIN_APPROVER_LEN = 3


class PromotionError(ValueError):
    pass


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class ModelVersions:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        (self.root / "versions").mkdir(parents=True, exist_ok=True)

    # ---- holat va jurnal
    @property
    def _state_path(self) -> Path:
        return self.root / "state.json"

    def _state(self) -> dict:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        return {"current": None, "promoted": []}

    def _log(self, event: str, version: Optional[str], by: str = "system", note: str = "", **extra) -> None:
        line = json.dumps({"at": utcnow(), "event": event, "version": version, "by": by, "note": note, **extra},
                          ensure_ascii=False)
        with open(self.root / "history.jsonl", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def history(self, limit: int = 50) -> list[dict]:
        p = self.root / "history.jsonl"
        if not p.exists():
            return []
        lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        return lines[-limit:]

    # ---- versiyalar
    def weights_dir(self, version: str) -> Path:
        return self.root / "versions" / version

    def report(self, version: str) -> dict:
        p = self.weights_dir(version) / "report.json"
        if not p.exists():
            raise PromotionError(f"versiya topilmadi: {version}")
        return json.loads(p.read_text(encoding="utf-8"))

    def current(self) -> Optional[str]:
        return self._state()["current"]

    def _new_id(self) -> str:
        base = time.strftime("v%Y%m%d-%H%M%S")
        vid, n = base, 1
        while (self.root / "versions" / vid).exists():
            n += 1
            vid = f"{base}-{n}"
        return vid

    def add_candidate(self, files: dict[str, Path], report: dict) -> str:
        """files: {nomi: manba yo'l}. Nomzod yaratiladi, lekin JORIY BO'LMAYDI."""
        vid = self._new_id()
        d = self.weights_dir(vid)
        d.mkdir(parents=True)
        for name, src in files.items():
            shutil.copyfile(src, d / name)
        report = {**report, "version": vid, "created_at": utcnow()}
        _atomic_write(d / "report.json", json.dumps(report, indent=2, ensure_ascii=False, default=float))
        self._log("candidate_created", vid, passed=bool(report.get("gates", {}).get("passed")))
        return vid

    def list(self) -> list[dict]:
        cur, promoted = self.current(), set(self._state()["promoted"])
        out = []
        for d in sorted((self.root / "versions").iterdir()):
            if (d / "report.json").exists():
                r = json.loads((d / "report.json").read_text(encoding="utf-8"))
                out.append({"version": d.name, "created_at": r.get("created_at"), "passed": bool(r.get("gates", {}).get("passed")),
                            "ever_promoted": d.name in promoted, "current": d.name == cur})
        return out

    def latest_candidate(self) -> Optional[str]:
        """Eng yangi, hali hech qachon tasdiqlanmagan nomzod."""
        pending = [v for v in self.list() if not v["ever_promoted"]]
        return pending[-1]["version"] if pending else None

    # ---- tasdiqlash / qaytarish
    def promote(self, version: str, approved_by: str, note: str = "") -> None:
        approver = (approved_by or "").strip()
        if len(approver) < MIN_APPROVER_LEN:
            raise PromotionError("tasdiqlovchi shifokorning ismi kerak (kamida 3 belgi)")
        report = self.report(version)
        gates = report.get("gates") or {}
        if not gates.get("passed"):
            failed = [g["name"] for g in gates.get("items", []) if not g.get("passed")]
            raise PromotionError("nomzod darvozalardan o'tmagan, tasdiqlab bo'lmaydi: " + (", ".join(failed) or "darvoza natijasi yo'q"))
        st = self._state()
        if st["current"] == version:
            raise PromotionError("bu versiya allaqachon joriy")
        st["promoted"].append(version)
        st["current"] = version
        _atomic_write(self._state_path, json.dumps(st, indent=2))
        self._log("promoted", version, by=approver, note=note)

    def rollback(self, approved_by: str, note: str = "") -> Optional[str]:
        """Oxirgi tasdiqlangan versiyani bekor qiladi: oldingisiga (yoki bazaviy modelga) qaytadi. Yangi joriy versiyani qaytaradi."""
        approver = (approved_by or "").strip()
        if len(approver) < MIN_APPROVER_LEN:
            raise PromotionError("qaytarishni tasdiqlovchi shifokorning ismi kerak (kamida 3 belgi)")
        st = self._state()
        if not st["promoted"]:
            raise PromotionError("qaytariladigan tasdiqlangan versiya yo'q (hozir bazaviy model)")
        undone = st["promoted"].pop()
        st["current"] = st["promoted"][-1] if st["promoted"] else None
        _atomic_write(self._state_path, json.dumps(st, indent=2))
        self._log("rolled_back", undone, by=approver, note=note, restored=st["current"])
        return st["current"]


def resolve_weights_dir(default: str | Path, versions_root: Optional[str | Path], explicit: Optional[str] = None) -> tuple[Path, str]:
    """Ilova qaysi PCG og'irliklarini yuklashi kerak: aniq ko'rsatilgan > tasdiqlangan joriy versiya > bazaviy."""
    if explicit:
        return Path(explicit), "explicit"
    if versions_root and Path(versions_root).exists():
        mv = ModelVersions(versions_root)
        cur = mv.current()
        if cur and (mv.weights_dir(cur) / "model_card.json").exists():
            return mv.weights_dir(cur), cur
    return Path(default), "baseline"
