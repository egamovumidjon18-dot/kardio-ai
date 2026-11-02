"""Shared measurement-time validation, independent of the upload timestamp."""
from datetime import datetime, timezone


def measurement_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("o'lchov sanasida vaqt mintaqasi kerak")
    value = value.astimezone(timezone.utc)
    if value > datetime.now(timezone.utc):
        raise ValueError("o'lchov sanasi kelajakda bo'lishi mumkin emas")
    return value.isoformat()
