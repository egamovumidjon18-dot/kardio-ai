"""Markaziy logging sozlamalari.

Ishlab chiqarish muhitida (CARDIOPATH_LOG_FORMAT=json) har bir jurnal satr
JSON formatida chiqadi — Docker log driver va Loki/ELK orqali yig'ish oson.
Standart holatda odatiy matnli format (developer-friendly).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class _JSONFormatter(logging.Formatter):
    """JSON log formatter: bitta satr, bitta JSON obyekti."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        obj = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            obj["exc"] = self.formatException(record.exc_info)
        rid = getattr(record, "request_id", None)
        if rid:
            obj["request_id"] = rid
        return json.dumps(obj, ensure_ascii=False)


def setup_logging() -> None:
    """Bir marta chaqiriladi (default_app yoki test fixture)."""
    fmt = os.environ.get("CARDIOPATH_LOG_FORMAT", "text").strip().lower()
    root = logging.getLogger()
    if root.handlers:          # allaqachon sozlangan — ikki marta chaqirilmasin
        return
    handler = logging.StreamHandler(sys.stderr)
    if fmt == "json":
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(handler)
    root.setLevel(os.environ.get("CARDIOPATH_LOG_LEVEL", "INFO").upper())
