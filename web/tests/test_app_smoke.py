import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_optional_web_app_smoke_script_passes_when_dependencies_installed():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    pytest.importorskip("uvicorn")

    result = subprocess.run(
        [sys.executable, "-m", "web.check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "[OK] optional web app smoke passed" in result.stdout
