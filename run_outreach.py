"""Wrapper that runs outreach and captures all output to run.log"""
import subprocess, sys
from pathlib import Path

log = Path(__file__).parent / "run.log"
with open(log, "w") as f:
    result = subprocess.run(
        [sys.executable, "ig_outreach/main.py", "--limit", "20", "--region", "india"],
        cwd=str(Path(__file__).parent),
        stdout=f, stderr=f, text=True
    )
print(f"Exit code: {result.returncode}")
print(f"Output in: {log}")
