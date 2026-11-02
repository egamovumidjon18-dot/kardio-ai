"""Tibbiy ma'lumotlar arxivi va saqlash (Retention) siyosati (ISO 27799 / Qonuniy arxiv).

Yopilgan (Stage.CLOSED) epizodlarni arxivlash va belgilangan muddatdan keyin
audit zanjirini buzmagan holda ma'lumotlarni xavfsiz boshqarish.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.episode import Stage
from core.store import EpisodeStore


def archive_closed_episodes(store: EpisodeStore, actor: str, older_than_days: int = 30) -> list[str]:
    """30 kundan ortiq muddat oldin CLOSED bo'lgan epizodlarni arxivga belgilaydi."""
    archived_ids = []
    now = datetime.now(timezone.utc)

    # store summaries orqali yopilgan epizodlarni topish
    _, closed_summaries = store.summaries(stage=Stage.CLOSED.value, limit=1000)
    for s in closed_summaries:
        eid = s["id"]
        ep = store.get(eid)
        if ep is None or ep.stage != Stage.CLOSED:
            continue

        closed_at = None
        for h in reversed(ep.handoffs):
            if h.to_stage == Stage.CLOSED.value:
                try:
                    closed_at = datetime.fromisoformat(h.created_at)
                    if closed_at.tzinfo is None:
                        closed_at = closed_at.replace(tzinfo=timezone.utc)
                    break
                except Exception:
                    pass

        if closed_at is None:
            try:
                closed_at = datetime.fromisoformat(ep.created_at)
                if closed_at.tzinfo is None:
                    closed_at = closed_at.replace(tzinfo=timezone.utc)
            except Exception:
                closed_at = now

        days_closed = (now - closed_at).total_seconds() / 86400.0
        if days_closed >= older_than_days:
            store.log_event(actor, "episode.archive", {"episode_id": ep.id, "days_closed": round(days_closed, 1)})
            archived_ids.append(ep.id)

    return archived_ids
