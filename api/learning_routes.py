"""O'z-o'zini o'rgatish holati (faqat o'qish). Tasdiqlash va qaytarish ATAYLAB bu yerda emas: `python -m learning.promote`."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI

from core.store import EpisodeStore
from learning.dataset import usable
from learning.gates import CFG, dataset_gate
from learning.versions import ModelVersions
from research.export_local import collect_children


def register(app: FastAPI, store: EpisodeStore, models_dir: Path, recordings_dir: Optional[Path], running_version: str) -> None:
    @app.get("/learning/status")
    def learning_status() -> dict:
        """Joriy model, nomzod va uning darvozalari, to'plangan tasdiqlangan holatlar, ma'lumot darvozasi, tarix."""
        mv = ModelVersions(models_dir)
        current = mv.current() or "baseline"
        out: dict = {"running_version": running_version, "current_version": current,
                     "restart_needed": running_version not in ("explicit", current), "versions": mv.list()[-10:],
                     "history": mv.history(20), "thresholds": CFG, "latest_candidate": None, "data": None, "last_cycle": None}
        cand = mv.latest_candidate()
        if cand:
            rep = mv.report(cand)
            ok = bool(rep["gates"]["passed"])
            out["latest_candidate"] = {"version": cand, "created_at": rep.get("created_at"), "passed": ok,
                                       "gates": rep["gates"]["items"], "delta_local": rep.get("delta_local"),
                                       "needs_human_approval": True,
                                       "promote_command": (f'python -m learning.promote --version {cand} --approved-by "Ismingiz"' if ok else None)}
        last = models_dir / "last_cycle.json"
        if last.exists():
            lc = json.loads(last.read_text(encoding="utf-8"))
            out["last_cycle"] = {k: lc.get(k) for k in ("started_at", "finished_at", "status", "message", "n_confirmed", "n_new", "version")}
        if recordings_dir is not None:
            children, _ = collect_children(store, recordings_dir)
            listed = mv.list()
            known = set(mv.report(listed[-1]["version"]).get("children_ids", [])) if listed else set()
            new = [c for c in usable(children) if c["eid"] not in known]
            gate = dataset_gate(children)
            out["data"] = {"confirmed_children": len(usable(children)), "new_since_last_candidate": len(new),
                           "needed_new": CFG["min_new"], "dataset_gate": gate}
        return out
