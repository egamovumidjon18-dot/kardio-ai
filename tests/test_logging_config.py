"""core/logging_config.py testlari."""
import json
import logging
import os


def test_json_formatter():
    from core.logging_config import _JSONFormatter
    fmt = _JSONFormatter()
    record = logging.LogRecord("test", logging.INFO, "file.py", 1, "salom", (), None)
    line = fmt.format(record)
    obj = json.loads(line)
    assert obj["level"] == "INFO"
    assert obj["msg"] == "salom"
    assert "ts" in obj


def test_setup_logging_idempotent():
    """Ikki marta chaqirilsa, handler ikkilanmasligi kerak."""
    from core.logging_config import setup_logging
    root = logging.getLogger()
    before = len(root.handlers)
    setup_logging()
    setup_logging()
    # At most one new handler added (may already have been set up)
    assert len(root.handlers) <= before + 1
