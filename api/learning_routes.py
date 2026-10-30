"""O'z-o'zini o'rgatish: holat (hamma kirgan shifokor) va nomzodni TASDIQLASH / QAYTARISH (faqat kardiolog yoki kardioxirurg).

Tasdiqlash faqat kirish tizimi yoqilganda ishlaydi: tasdiqlovchi — so'rovda yozilgan nom emas, haqiqiy kirgan foydalanuvchi.
Darvozalardan o'tmagan nomzodni tasdiqlab bo'lmaydi (`ModelVersions.promote`). Yangi model dastur qayta ishga tushgach yuklanadi."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.store import EpisodeStore
from learning.dataset import usable
from learning.gates import CFG, dataset_gate
from core.identity import current_user
from learning.versions import ModelVersions, PromotionError
from research.export_local import collect_children


class PromoteIn(BaseModel):
    version: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_-]+$")        # yo'l o'zgartirish (../) mumkin emas
    note: str = Field("", max_length=300)


class RollbackIn(BaseModel):
    note: str = Field(max_length=300)


def register(app: FastAPI, store: EpisodeStore, models_dir: Path, recordings_dir: Optional[Path], running_version: str,
             auth_enabled: bool = False) -> None:
    def approver() -> str:
        user = current_user.get()
        if not auth_enabled or not user:
            raise HTTPException(403, "modelni tasdiqlash uchun kirish tizimi yoqilgan bo'lishi kerak (CARDIOPATH_AUTH=on); "
                                     "hozircha: python -m learning.promote")
        return user

    @app.post("/learning/promote")
    def promote(body: PromoteIn) -> dict:
        """Darvozalardan o'tgan nomzodni JORIY qiladi. Tasdiqlovchi = kirgan foydalanuvchi."""
        who = approver()
        try:
            ModelVersions(models_dir).promote(body.version, who, body.note.strip())
        except PromotionError as exc:
            raise HTTPException(409, str(exc)) from None
        except (FileNotFoundError, KeyError, ValueError):
            raise HTTPException(404, "bunday versiya yo'q") from None
        store.log_event(who, "model.promote", {"version": body.version, "note": body.note.strip()})
        return {"ok": True, "version": body.version, "approved_by": who, "restart_needed": True,
                "note": "yangi model dastur qayta ishga tushirilgach yuklanadi"}

    @app.post("/learning/rollback")
    def rollback(body: RollbackIn) -> dict:
        """Oxirgi tasdiqlangan versiyani bekor qiladi (sabab majburiy)."""
        who = approver()
        if len(body.note.strip()) < 5:
            raise HTTPException(422, "qaytarish sababini yozing (kamida 5 belgi)")
        try:
            restored = ModelVersions(models_dir).rollback(who, body.note.strip())
        except PromotionError as exc:
            raise HTTPException(409, str(exc)) from None
        store.log_event(who, "model.rollback", {"restored": restored, "note": body.note.strip()})
        return {"ok": True, "restored": restored or "baseline", "approved_by": who, "restart_needed": True}

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
                                       "promote_command": (f'python -m learning.promote --version {cand} --approved-by "Ismingiz"' if ok else None),
                                       "can_promote_via_ui": ok and auth_enabled}
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
