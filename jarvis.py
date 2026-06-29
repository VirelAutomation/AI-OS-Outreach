"""
Jarvis CLI — talk to Jarvis directly from the terminal.

Usage:
    python jarvis.py
    python jarvis.py "send 30 comments and 10 DMs to coaches on Instagram"
    python jarvis.py --status
"""

import os, sys, argparse
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / "forge_system" / ".env")

sys.path.insert(0, str(ROOT / "forge_system" / "forge_system"))

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║              JARVIS — Virel Autonomous System                ║
║          Type anything. He'll figure it out.                 ║
║          Type 'exit' or Ctrl+C to quit.                      ║
╚══════════════════════════════════════════════════════════════╝
"""

EXAMPLES = """
Try:
  "send 30 comments and 10 DMs to coaches on Instagram"
  "what's my outreach status today"
  "I need 20x more leads, make a plan"
  "post in all my Facebook groups"
  "write a cold email for a life coach named Sarah"
  "show me the last 20 lines of the FB log"
  "remember my monthly target is 10 clients"
  "start the outreach agent"
"""


def run_once(message: str, silent: bool = False) -> str:
    from agents.jarvis_core import run
    if not silent:
        print(f"\nJarvis thinking...\n")
    response = run(message)
    return response


def interactive():
    print(BANNER)

    # Verify at least one Gemini key is present
    gemini_keys = [v for k, v in os.environ.items()
                   if k.startswith("GEMINI_API_KEY") and v and "MODEL" not in k]
    if not gemini_keys:
        print("⚠️  No GEMINI_API_KEY found in forge_system/.env")
        print("   Add GEMINI_API_KEY=AIza... to unlock Jarvis\n")
        return

    # Check IG status
    try:
        import sqlite3
        conn = sqlite3.connect(ROOT / "ig_outreach" / "outreach.db")
        today_ig = conn.execute(
            "SELECT COUNT(*) FROM ig_outreach WHERE dm_sent_at LIKE ?",
            (f"{__import__('datetime').date.today().isoformat()}%",)
        ).fetchone()[0]
        conn.close()
    except Exception:
        today_ig = 0

    try:
        sys.path.insert(0, str(ROOT / "fb_outreach"))
        import fb_db; fb_db.init_db()
        fb_stats = fb_db.get_stats()
        today_fb = fb_stats["dms_today"]
    except Exception:
        today_fb = 0

    print(f"Today: FB={today_fb} DMs | IG={today_ig} DMs")
    print(EXAMPLES)

    history = []

    while True:
        try:
            user_input = input("You → ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nJarvis: Later.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("Jarvis: Done.")
            break

        print()
        try:
            from agents.jarvis_core import run
            response = run(user_input, history=history[-6:])
            print(f"Jarvis → {response}\n")
            history.append({"role": "user",      "content": user_input})
            history.append({"role": "assistant",  "content": response})
        except Exception as e:
            print(f"Jarvis → [Error: {e}]\n")


def main():
    parser = argparse.ArgumentParser(description="Jarvis CLI")
    parser.add_argument("message", nargs="?", help="Single message to Jarvis (non-interactive)")
    parser.add_argument("--status", action="store_true", help="Quick status check")
    args = parser.parse_args()

    if args.status:
        response = run_once("give me a quick status of everything — FB, IG, comments, queue")
        print(f"Jarvis: {response}")
        return

    if args.message:
        response = run_once(args.message)
        print(f"Jarvis: {response}")
        return

    interactive()


if __name__ == "__main__":
    main()
