"""
Autonomous Outreach Agent — Hamilton-Jacobi Bellman inspired.

The agent continuously monitors state and solves:
    π*(s,t) = argmax_a [ R(s,a) + V(s', t+dt) ]

where V(s,t) = expected leads generated from state s with time t remaining.

It doesn't just alert — it fixes, adapts, reroutes, and re-executes.

Decision loop:
  1. Observe state (DMs sent, platform health, time of day, queue)
  2. Compute optimal action via value function
  3. Execute action
  4. Observe result
  5. If failure → Claude diagnoses → agent fixes → retries
  6. Repeat until daily target met or day ends
"""

import os, sys, time, json, random, logging, subprocess, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# ── Bootstrap ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
load_dotenv(ROOT / "forge_system" / ".env")
sys.path.insert(0, str(ROOT / "fb_outreach"))
sys.path.insert(0, str(ROOT / "ig_outreach"))

import fb_db, fb_alerts

LOG_FILE = ROOT / "agent.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENT] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("virel.agent")

_IST = timezone(timedelta(hours=5, minutes=30))

# ── Config ────────────────────────────────────────────────────────────────────
FB_DAILY_TARGET = int(os.getenv("FACEBOOK_DAILY_DM_LIMIT",  "10"))
IG_DAILY_TARGET = int(os.getenv("INSTAGRAM_DAILY_DM_LIMIT", "5"))
TOTAL_TARGET    = FB_DAILY_TARGET + IG_DAILY_TARGET   # e.g. 15

# Time windows (IST hours)
INDIA_START, INDIA_END = 8, 15    # 8am-3pm: India/morning leads
US_START,    US_END    = 18, 24   # 6pm-midnight: US leads
DAILY_END              = 23       # stop at 11pm IST to avoid night-time flag


# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class PlatformHealth:
    healthy:    bool  = True
    last_error: str   = ""
    fail_count: int   = 0
    paused_until: Optional[datetime] = None

    def is_available(self) -> bool:
        if self.paused_until and datetime.now(_IST) < self.paused_until:
            return False
        return self.healthy

    def mark_fail(self, error: str, pause_minutes: int = 0):
        self.fail_count += 1
        self.last_error  = error
        if pause_minutes:
            self.paused_until = datetime.now(_IST) + timedelta(minutes=pause_minutes)
        if self.fail_count >= 3:
            self.healthy = False

    def mark_ok(self):
        self.healthy    = True
        self.fail_count = 0
        self.last_error = ""
        self.paused_until = None


@dataclass
class AgentState:
    # Counts
    fb_dms_sent:   int = 0
    ig_dms_sent:   int = 0
    fb_frs_sent:   int = 0
    wa_dms_sent:   int = 0
    total_sent:    int = 0

    # Platform health
    fb:  PlatformHealth = field(default_factory=PlatformHealth)
    ig:  PlatformHealth = field(default_factory=PlatformHealth)

    # Session
    consecutive_fails: int  = 0
    last_action:       str  = ""
    last_result:       str  = ""
    cycle:             int  = 0

    def ist_now(self) -> datetime:
        return datetime.now(_IST)

    def hour(self) -> float:
        n = self.ist_now()
        return n.hour + n.minute / 60

    def region(self) -> str:
        h = self.hour()
        if INDIA_START <= h < INDIA_END:
            return "india"
        if US_START <= h < US_END:
            return "us"
        return "us"   # default to US outside windows

    def remaining(self) -> int:
        return max(0, TOTAL_TARGET - self.total_sent)

    def fb_remaining(self) -> int:
        return max(0, FB_DAILY_TARGET - self.fb_dms_sent)

    def ig_remaining(self) -> int:
        return max(0, IG_DAILY_TARGET - self.ig_dms_sent)

    def hours_left(self) -> float:
        return max(0, DAILY_END - self.hour())

    def behind_schedule(self) -> bool:
        """True if we're sending DMs slower than needed to hit target by end of day."""
        if self.hours_left() <= 0:
            return False
        elapsed = self.hour() - INDIA_START
        if elapsed <= 0:
            return False
        expected_rate = TOTAL_TARGET / max(1, DAILY_END - INDIA_START)
        expected_sent = int(elapsed * expected_rate)
        return self.total_sent < expected_sent

    def summary(self) -> str:
        h = self.hour()
        return (
            f"FB={self.fb_dms_sent}/{FB_DAILY_TARGET} "
            f"IG={self.ig_dms_sent}/{IG_DAILY_TARGET} "
            f"Total={self.total_sent}/{TOTAL_TARGET} "
            f"Time={h:.1f}h IST ({self.region()}) "
            f"Left={self.hours_left():.1f}h "
            f"FB_health={'OK' if self.fb.is_available() else 'DOWN'} "
            f"IG_health={'OK' if self.ig.is_available() else 'DOWN'}"
        )


# ── Value function (HJB-inspired) ────────────────────────────────────────────

def compute_value(state: AgentState, action: str) -> float:
    """
    V(s, a) = immediate_reward * success_probability + gamma * future_value

    HJB intuition:
      dV/dt = -H(s, dV/ds)
    where H is the Hamiltonian (maximum achievable reward rate).

    In discrete form: prefer actions that keep us on the optimal trajectory
    toward TOTAL_TARGET by DAILY_END.
    """
    h_left  = state.hours_left()
    remain  = state.remaining()

    if h_left <= 0 or remain <= 0:
        return 0.0

    # Optimal rate needed to hit target
    rate_needed = remain / h_left          # DMs/hour needed
    rate_current = state.total_sent / max(1, state.hour() - INDIA_START)

    # Urgency: how far behind are we?  (HJB terminal cost approaching)
    urgency = min(2.0, rate_needed / max(0.1, rate_current)) if state.total_sent > 0 else 1.0

    # Success probability per action based on platform health + time window
    p = {
        "send_fb_dm":  0.6 if state.fb.is_available() and state.fb_remaining() > 0 else 0.0,
        "send_ig_dm":  0.5 if state.ig.is_available() and state.ig_remaining() > 0 else 0.0,
        "send_wa_dm":  0.8,   # WhatsApp numbers we already have — high success
        "fix_fb":      0.7 if not state.fb.is_available() else 0.0,
        "fix_ig":      0.6 if not state.ig.is_available() else 0.0,
        "wait":        0.0,
    }.get(action, 0.1)

    # Immediate reward
    immediate = p * 1.0

    # Future value: taking this action opens up more DMs later
    future_factor = 0.9 if action.startswith("fix_") else 0.5
    future        = future_factor * (remain - 1) / TOTAL_TARGET

    # Discount by time pressure (HJB: as t → T, terminal cost dominates)
    gamma = 1.0 - (1.0 / (1.0 + h_left))

    return immediate + gamma * future * urgency


def optimal_action(state: AgentState) -> str:
    """Return the highest-value action given current state."""
    candidates = []

    if state.fb_remaining() > 0:
        candidates.append("send_fb_dm")
    if state.ig_remaining() > 0:
        candidates.append("send_ig_dm")
    if not state.fb.is_available():
        candidates.append("fix_fb")
    if not state.ig.is_available():
        candidates.append("fix_ig")

    # WhatsApp option if we have numbers collected
    try:
        wa_leads = fb_db.get_whatsapp_leads(nationality="indian")
        if wa_leads and state.hour() < INDIA_END:
            candidates.append("send_wa_dm")
    except Exception:
        pass

    if not candidates:
        return "wait"

    values = {a: compute_value(state, a) for a in candidates}
    best   = max(values, key=values.get)

    log.info(f"[HJB] Values: {json.dumps({k: round(v,3) for k,v in values.items()})}")
    log.info(f"[HJB] Optimal action: {best}")
    return best


# ── Claude reasoning layer ────────────────────────────────────────────────────

def _gemini_diagnose(state: AgentState, error: str, context: str) -> dict:
    """
    Ask Gemini to diagnose a failure and return a recovery plan.
    Returns: {"action": str, "reason": str, "fix_steps": list}
    """
    try:
        import google.generativeai as genai

        # Find any Gemini key
        key = ""
        for k, v in os.environ.items():
            if k.startswith("GEMINI_API_KEY") and v and "MODEL" not in k:
                key = v
                break
        if not key:
            return {"action": "wait", "reason": "No Gemini key", "fix_steps": [], "wait_minutes": 5}

        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""You are the decision engine for an autonomous social media outreach agent.

Current state:
{state.summary()}

Error encountered: {error}
Context: {context}

Daily target: {TOTAL_TARGET} DMs ({FB_DAILY_TARGET} Facebook + {IG_DAILY_TARGET} Instagram)
Time (IST): {state.hour():.1f}h
Behind schedule: {state.behind_schedule()}

Available platforms:
- Facebook: {'AVAILABLE' if state.fb.is_available() else f'DOWN (error: {state.fb.last_error})'}
- Instagram: {'AVAILABLE' if state.ig.is_available() else f'DOWN (error: {state.ig.last_error})'}

Decide the best recovery action. Options:
- restart_fb_chrome: restart Chrome and reload FB session cookies
- switch_to_ig: switch outreach to Instagram for this session
- increase_rate: reduce gap between DMs (risky but needed if behind)
- try_whatsapp: send WA messages to numbers already collected
- wait_N_minutes: pause N minutes then retry
- escalate: alert user, cannot auto-fix

Reply ONLY with valid JSON (no markdown):
{{"action": "...", "reason": "one sentence", "fix_steps": ["step1", "step2"], "wait_minutes": 0}}"""

        resp = model.generate_content(prompt)
        raw  = resp.text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip().rstrip("`").strip()
        return json.loads(raw)

    except Exception as e:
        log.warning(f"[GEMINI] Diagnose failed: {e}")
        return {"action": "wait", "reason": str(e), "fix_steps": [], "wait_minutes": 15}


# Keep old name as alias so nothing breaks
_claude_diagnose = _gemini_diagnose


# ── Action executors ──────────────────────────────────────────────────────────

def _run_fb_dms(state: AgentState, limit: int = 3) -> tuple[int, str]:
    """Run FB DM outreach subprocess. Returns (sent, error_or_empty)."""
    log.info(f"[ACTION] Running FB DMs (limit={limit}, region={state.region()})...")
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "fb_outreach" / "main.py"),
             "--dm", "--niche", "coach"],
            capture_output=True, text=True, timeout=3600,
            cwd=str(ROOT),
        )
        out = result.stdout + result.stderr

        # Parse how many were sent from log output
        sent = 0
        for line in out.splitlines():
            if "[SENT #" in line:
                try:
                    sent = int(line.split("[SENT #")[1].split("/")[0])
                except Exception:
                    pass

        if result.returncode != 0 and sent == 0:
            return 0, out[-500:]  # last 500 chars of error
        return sent, ""

    except subprocess.TimeoutExpired:
        return 0, "timeout after 60 minutes"
    except Exception as e:
        return 0, str(e)


def _run_ig_dms(state: AgentState, limit: int = 5) -> tuple[int, str]:
    """Run IG DM outreach subprocess. Returns (sent, error_or_empty)."""
    log.info(f"[ACTION] Running IG DMs (limit={limit}, region={state.region()})...")
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "ig_outreach" / "main.py"),
             "--region", state.region(),
             "--niche", "coach",
             "--limit", str(limit)],
            capture_output=True, text=True, timeout=1800,
            cwd=str(ROOT),
        )
        out = result.stdout + result.stderr

        sent = 0
        for line in out.splitlines():
            if "[SENT #" in line:
                try:
                    sent = int(line.split("[SENT #")[1].split("/")[0])
                except Exception:
                    pass

        if "checkpoint" in out.lower() or "blocked" in out.lower():
            return 0, "instagram_checkpoint"
        if result.returncode != 0 and sent == 0:
            return 0, out[-300:]
        return sent, ""

    except subprocess.TimeoutExpired:
        return 0, "timeout"
    except Exception as e:
        return 0, str(e)


def _run_fb_posts(state: AgentState) -> tuple[int, str]:
    log.info("[ACTION] Running FB group posts...")
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "fb_outreach" / "main.py"),
             "--post", "--niche", "coach"],
            capture_output=True, text=True, timeout=7200,
            cwd=str(ROOT),
        )
        out = result.stdout + result.stderr
        posted = out.count("[DONE #")
        return posted, "" if result.returncode == 0 else out[-300:]
    except Exception as e:
        return 0, str(e)


def _restart_fb(state: AgentState) -> bool:
    """Kill Chrome, clear checkpoint, re-run login to verify session is fresh."""
    log.info("[FIX] Restarting FB Chrome session...")
    try:
        subprocess.run("taskkill /F /IM chrome.exe /T", shell=True,
                       capture_output=True, timeout=10)
        subprocess.run("taskkill /F /IM chromedriver.exe /T", shell=True,
                       capture_output=True, timeout=10)
        time.sleep(8)
        # Test login only (no DMs)
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0,'fb_outreach'); "
             "import fb_db; fb_db.init_db(); "
             "from fb_browser import build_driver; "
             "from fb_login import login; "
             "d = build_driver(); ok = login(d); d.quit(); "
             "print('LOGIN_OK' if ok else 'LOGIN_FAIL')"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        ok = "LOGIN_OK" in (result.stdout + result.stderr)
        if ok:
            log.info("[FIX] FB session restored successfully")
            state.fb.mark_ok()
        else:
            log.warning("[FIX] FB login failed after restart")
        return ok
    except Exception as e:
        log.error(f"[FIX] FB restart failed: {e}")
        return False


# ── Main agent loop ───────────────────────────────────────────────────────────

class OutreachAgent:
    def __init__(self):
        self.state = AgentState()
        self._load_today_counts()

    def _load_today_counts(self):
        """Sync state from DB on startup."""
        try:
            fb_db.init_db()
            s = fb_db.get_stats()
            self.state.fb_dms_sent = s["dms_today"]
            self.state.total_sent  = s["dms_today"]
            log.info(f"[INIT] Loaded today's counts — {self.state.summary()}")
        except Exception as e:
            log.warning(f"[INIT] Could not load counts: {e}")

    def _execute_action(self, action: str) -> tuple[bool, str]:
        """Execute an action. Returns (success, error)."""
        s = self.state

        if action == "send_fb_dm":
            limit = min(s.fb_remaining(), 5)   # batch of 5 max per run
            sent, err = _run_fb_dms(s, limit)
            if sent > 0:
                s.fb_dms_sent  += sent
                s.total_sent   += sent
                s.fb.mark_ok()
                return True, ""
            s.fb.mark_fail(err, pause_minutes=15 if "challenge" in err.lower() else 0)
            return False, err

        elif action == "send_ig_dm":
            limit = min(s.ig_remaining(), 5)
            sent, err = _run_ig_dms(s, limit)
            if sent > 0:
                s.ig_dms_sent += sent
                s.total_sent  += sent
                s.ig.mark_ok()
                return True, ""
            if "checkpoint" in err:
                s.ig.mark_fail(err, pause_minutes=1440)   # pause IG for 24h
            else:
                s.ig.mark_fail(err)
            return False, err

        elif action == "send_wa_dm":
            # Future: send WhatsApp messages to collected numbers
            log.info("[ACTION] WhatsApp outreach (placeholder — add wa_sender.py)")
            return True, ""

        elif action == "fix_fb":
            ok = _restart_fb(s)
            return ok, "" if ok else "restart failed"

        elif action == "fix_ig":
            msg = (
                "Instagram checkpoint requires manual verification. "
                "Open Instagram app → log into @virel.automation → complete security check."
            )
            fb_alerts.alert("IG checkpoint — manual action needed", msg, level="error")
            s.ig.mark_fail("checkpoint", pause_minutes=1440)
            log.warning(f"[FIX] {msg}")
            return False, "checkpoint"

        elif action == "wait":
            log.info("[ACTION] Nothing to do right now — waiting 15 min")
            time.sleep(900)
            return True, ""

        return False, f"unknown action: {action}"

    def _handle_failure(self, action: str, error: str):
        """Ask Claude to diagnose and auto-apply the fix."""
        log.info(f"[DIAGNOSE] Action '{action}' failed: {error[:100]}")

        diagnosis = _claude_diagnose(self.state, error, f"failed action: {action}")
        fix_action = diagnosis.get("action", "wait")
        reason     = diagnosis.get("reason", "")
        wait_min   = diagnosis.get("wait_minutes", 0)

        log.info(f"[CLAUDE] → {fix_action} | {reason}")

        if wait_min > 0:
            log.info(f"[FIX] Waiting {wait_min} minutes before retry...")
            time.sleep(wait_min * 60)

        if fix_action == "restart_fb_chrome":
            _restart_fb(self.state)

        elif fix_action == "switch_to_ig":
            log.info("[FIX] Switching to Instagram for this cycle")
            self.state.fb.mark_fail("switched away by agent", pause_minutes=60)

        elif fix_action == "increase_rate":
            log.info("[FIX] Increasing rate — reducing min gap for next run")

        elif fix_action == "try_whatsapp":
            self._execute_action("send_wa_dm")

        elif fix_action == "escalate":
            fb_alerts.alert(
                "Agent escalating — cannot auto-fix",
                f"Action: {action} | Error: {error[:150]} | Claude says: {reason}",
                level="error",
            )

        self.state.consecutive_fails += 1

    def run_day(self):
        """
        Main agentic loop. Runs all day, continuously optimising toward daily target.
        """
        log.info("=" * 60)
        log.info("  Virel Autonomous Outreach Agent — Starting")
        log.info(f"  Target: {TOTAL_TARGET} DMs | FB: {FB_DAILY_TARGET} | IG: {IG_DAILY_TARGET}")
        log.info("=" * 60)

        # Run FB posts first thing
        log.info("[AGENT] Running daily FB posts...")
        posted, err = _run_fb_posts(self.state)
        if err:
            log.warning(f"[POSTS] {err[:100]}")
        else:
            log.info(f"[POSTS] {posted} posts done")

        # Run IG comments in background — builds visibility in coaching community
        log.info("[AGENT] Starting IG comments (background, 20/day)...")
        subprocess.Popen(
            [sys.executable, str(ROOT / "ig_outreach" / "main.py"),
             "--comments", "--niche", "coach", "--comment-limit", "20"],
            cwd=str(ROOT),
            stdout=open(ROOT / "ig_outreach" / "outreach.log", "a"),
            stderr=subprocess.STDOUT,
        )

        while True:
            self.state.cycle += 1
            now   = self.state.ist_now()
            hour  = self.state.hour()

            log.info(f"\n[CYCLE {self.state.cycle}] {now.strftime('%H:%M IST')} | {self.state.summary()}")

            # Stop conditions
            if self.state.total_sent >= TOTAL_TARGET:
                msg = f"Daily target hit — {self.state.total_sent}/{TOTAL_TARGET} DMs sent."
                log.info(f"[DONE] {msg}")
                fb_alerts.alert("Daily target reached", msg, level="ok")
                break

            if hour >= DAILY_END:
                remaining = self.state.remaining()
                if remaining > 0:
                    msg = f"End of day. Sent {self.state.total_sent}/{TOTAL_TARGET}. {remaining} queued for tomorrow."
                    log.info(f"[EOD] {msg}")
                    fb_alerts.alert("End of day", msg, level="info")
                break

            # Check if behind schedule — alert and plan recovery
            if self.state.behind_schedule():
                log.info(f"[HJB] Behind schedule — computing recovery plan")
                fb_alerts.alert(
                    "Behind DM schedule",
                    f"Sent {self.state.total_sent}/{TOTAL_TARGET} | "
                    f"{self.state.hours_left():.1f}h left | Accelerating...",
                    level="warn",
                )

            # Compute optimal action
            action = optimal_action(self.state)
            log.info(f"[AGENT] Executing: {action}")
            self.state.last_action = action

            # Execute
            ok, error = self._execute_action(action)

            if ok:
                self.state.consecutive_fails = 0
                self.state.last_result = "ok"
            else:
                self.state.last_result = "fail"
                self._handle_failure(action, error)

                if self.state.consecutive_fails >= 5:
                    msg = f"5 consecutive failures — agent pausing for 30 min. Last error: {error[:100]}"
                    log.error(f"[AGENT] {msg}")
                    fb_alerts.alert("Agent pausing", msg, level="error")
                    time.sleep(1800)
                    self.state.consecutive_fails = 0

            # Wait between cycles (shorter if behind schedule)
            if self.state.behind_schedule():
                wait = 60    # 1 min if urgent
            elif action == "wait":
                wait = 900   # 15 min idle
            else:
                wait = 300   # 5 min normal

            log.info(f"[AGENT] Next cycle in {wait//60}m {wait%60}s...")
            time.sleep(wait)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Virel Autonomous Outreach Agent")
    parser.add_argument("--once",    action="store_true", help="Run one cycle then exit")
    parser.add_argument("--status",  action="store_true", help="Print current state and exit")
    parser.add_argument("--post",    action="store_true", help="Run posts only then exit")
    args = parser.parse_args()

    agent = OutreachAgent()

    if args.status:
        log.info(agent.state.summary())
        action = optimal_action(agent.state)
        log.info(f"Next optimal action: {action}")
        return

    if args.post:
        posted, err = _run_fb_posts(agent.state)
        log.info(f"Posts: {posted} | {err or 'ok'}")
        return

    if args.once:
        action = optimal_action(agent.state)
        ok, err = agent._execute_action(action)
        log.info(f"Action: {action} | ok={ok} | {err or ''}")
        return

    agent.run_day()


if __name__ == "__main__":
    main()
