"""Server torch'siz ishga tushishi kerak (Docker obrazida torch yo'q: u faqat o'qitish uchun)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_server_imports_without_torch():
    code = "import sys; sys.modules['torch'] = None; import api.main; api.main.create_app"
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
