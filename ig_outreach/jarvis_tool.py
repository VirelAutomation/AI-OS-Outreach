"""
Called by Jarvis when the user asks to run Instagram outreach.
Runs main.py as a subprocess and streams the result back.
"""

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_SCRIPT = Path(__file__).parent / "main.py"


def run_ig_outreach(limit: int = 10) -> str:
    """Run the IG outreach bot and return a summary string for Jarvis to relay."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--limit", str(limit)],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
        timeout=3600,
    )
    output = result.stdout + result.stderr
    lines = [l for l in output.splitlines() if l.strip()]
    return "\n".join(lines) if lines else "No output captured."
