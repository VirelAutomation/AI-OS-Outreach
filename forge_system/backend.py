"""
Canonical FORGE backend launcher.

This file exists so the project has one obvious backend entrypoint.
The real application lives in forge_system/main.py.

Run:
    python backend.py
or:
    uvicorn backend:app --reload --port 8000
"""

from pathlib import Path
import sys

import uvicorn

PROJECT_DIR = Path(__file__).resolve().parent
APP_DIR = PROJECT_DIR / "forge_system"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import app  # noqa: E402


if __name__ == "__main__":
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)
