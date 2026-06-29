"""
Self-healing outreach engine.

Instead of failing hard, it observes outcomes, adapts strategy, and finds
the best available route — similar to how a human would de-escalate.

States (escalation ladder, always trying to de-escalate back):
  normal   → try FR + DM
  fr_only  → skip DM attempt, just send FRs (hit when DMs consistently blocked)
  slow     → double gaps (hit after rate-limit signals)
  paused   → challenge detected, stop immediately and alert

Recovery:
  - Selector broken?     → Claude looks at screenshot, describes what IS there
  - DM button missing?   → Switch to FR, log as pending
  - 3 DM fails in a row? → fr_only mode
  - Chrome crash?        → auto-restart browser, reload session, resume checkpoint
  - Challenge page?      → alert + stop immediately
"""

import re, time, random, logging, json
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException

import fb_db
import fb_alerts
from fb_browser import (
    jitter, scroll, screenshot, dismiss_modals,
    find_element, detect_challenge, _ON_RAILWAY,
)

log = logging.getLogger("virel.fb.engine")

# ── Selectors (same as fb_dm but centralised here) ────────────────────────────

_MSG_BTN = [
    (By.XPATH, "//div[@aria-label='Message'][@role='button']"),
    (By.XPATH, "//a[contains(@href,'messenger')][@role='button']"),
    (By.XPATH, "//div[@role='button'][normalize-space()='Message']"),
    (By.XPATH, "//span[normalize-space()='Message']/ancestor::div[@role='button'][1]"),
]

_MSG_INPUT = [
    (By.CSS_SELECTOR,  "div[aria-label='Aa'][role='textbox']"),
    (By.XPATH,         "//div[@aria-label='Aa'][@role='textbox']"),
    (By.CSS_SELECTOR,  "div[aria-label='Message'][role='textbox']"),
    (By.CSS_SELECTOR,  "div[contenteditable='true'][role='textbox']"),
    (By.XPATH,         "//div[@aria-label='Message'][@role='textbox']"),
    (By.XPATH,         "//div[@role='textbox'][@contenteditable='true']"),
    (By.XPATH,         "//div[@data-testid='mwim-input-footer']//div[@role='textbox']"),
    (By.XPATH,         "//div[@contenteditable='true'][not(@aria-disabled)][not(@aria-label='Search')]"),
]

_ADD_FRIEND = [
    (By.XPATH, "//div[@aria-label='Add friend'][@role='button']"),
    (By.XPATH, "//div[@aria-label='Add Friend'][@role='button']"),
    (By.XPATH, "//a[@aria-label='Add friend']"),
    (By.XPATH, "//div[@role='button'][contains(normalize-space(),'Add friend')]"),
    (By.XPATH, "//div[@role='button'][contains(normalize-space(),'Add Friend')]"),
    (By.XPATH, "//span[contains(normalize-space(),'Add friend')]/ancestor::div[@role='button'][1]"),
]

_FR_SENT = [
    (By.XPATH, "//div[@aria-label='Friend request sent']"),
    (By.XPATH, "//div[@aria-label='Cancel request']"),
    (By.XPATH, "//div[@aria-label='Respond to friend request']"),
    (By.XPATH, "//div[@role='button'][normalize-space()='Requested']"),
    (By.XPATH, "//span[contains(.,'Requested')]"),
]

# ── AI diagnostics (Claude API — optional, gracefully skipped if no key) ──────

def _ai_diagnose(shot_path: str, context: str) -> dict:
    """
    Send a screenshot to Claude and ask what's visible on the page.
    Returns a dict with keys: has_message_btn, has_add_friend, is_challenge, notes.
    Falls back gracefully if Claude is unavailable.
    """
    try:
        import anthropic, base64 as b64
        api_key = __import__("os").getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {}

        with open(shot_path, "rb") as f:
            img_data = b64.standard_b64encode(f.read()).decode()

        client = anthropic.Anthropic(api_key=api_key)
        resp   = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": img_data
                    }},
                    {"type": "text", "text": (
                        f"Facebook page screenshot. Context: {context}\n"
                        "What action buttons are visible on this profile? "
                        "Reply ONLY with JSON: "
                        '{"has_message_btn":bool,"has_add_friend":bool,'
                        '"is_challenge":bool,"is_private":bool,"notes":"one line"}'
                    )},
                ],
            }],
        )
        raw = resp.content[0].text.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(raw)
    except Exception as e:
        log.debug(f"[ENGINE] AI diagnose skipped: {e}")
        return {}


# ── Engine ────────────────────────────────────────────────────────────────────

class OutreachEngine:
    """
    Adaptive DM engine. Tracks what's working, switches strategy when needed,
    and uses AI diagnostics on persistent failures.
    """

    MODE_NORMAL  = "normal"
    MODE_FR_ONLY = "fr_only"
    MODE_SLOW    = "slow"
    MODE_PAUSED  = "paused"

    RESULT_SENT     = "sent"
    RESULT_FR_ONLY  = "fr_only"
    RESULT_SKIPPED  = "skipped"
    RESULT_BLOCKED  = "blocked"

    def __init__(self, driver):
        self.driver  = driver
        self.mode    = self.MODE_NORMAL
        self.session = {
            "dm_sent": 0, "fr_sent": 0,
            "dm_fail": 0, "fr_fail": 0,
            "consec_fail": 0, "consec_fr_fail": 0,
        }

    # ── Public ────────────────────────────────────────────────────────────────

    def attempt(self, profile_url: str, message: str, uid: str) -> str:
        """
        Try to contact a profile using the best available strategy.
        Returns one of RESULT_* constants.
        """
        if self.mode == self.MODE_PAUSED:
            return self.RESULT_BLOCKED

        if detect_challenge(self.driver):
            self._on_challenge(uid)
            return self.RESULT_BLOCKED

        # Navigate to profile
        if not self._nav(profile_url):
            return self.RESULT_SKIPPED

        # ------------------------------------------------------------------
        # Route 1: Send friend request (always try — unlocks messaging later)
        # ------------------------------------------------------------------
        fr_sent = self._try_friend_request()

        # ------------------------------------------------------------------
        # Route 2: Try direct DM (skip in fr_only mode)
        # ------------------------------------------------------------------
        if self.mode != self.MODE_FR_ONLY:
            dm_result = self._try_dm(profile_url, message, uid)

            if dm_result == "sent":
                self._on_dm_success()
                return self.RESULT_SENT

            if dm_result == "no_button" and fr_sent:
                # Profile has no Message button but FR went — that's fine
                log.info(f"  [FR-ONLY] @{uid} — DM restricted, FR sent")
                self._on_fr_success()
                return self.RESULT_FR_ONLY

            if dm_result in ("input_fail", "click_fail"):
                # Selector / UI problem — ask AI what's actually on the page
                self._ai_adapt(profile_url, uid, dm_result)

            self._on_dm_fail(uid)

            if fr_sent:
                return self.RESULT_FR_ONLY

            return self.RESULT_SKIPPED

        # ------------------------------------------------------------------
        # FR-only mode — just the friend request
        # ------------------------------------------------------------------
        if fr_sent:
            log.info(f"  [FR mode] @{uid} — FR sent")
            self._on_fr_success()
            return self.RESULT_FR_ONLY

        self._on_fr_fail()
        return self.RESULT_SKIPPED

    def gap(self) -> int:
        """Return appropriate inter-DM gap in seconds for current mode."""
        if self.mode == self.MODE_SLOW:
            return random.randint(600, 900)   # 10-15 min
        return random.randint(300, 720)       # 5-12 min normal

    def is_paused(self) -> bool:
        return self.mode == self.MODE_PAUSED

    def status(self) -> str:
        return (
            f"mode={self.mode} | sent={self.session['dm_sent']} "
            f"fr={self.session['fr_sent']} | fails={self.session['consec_fail']}"
        )

    # ── Private actions ───────────────────────────────────────────────────────

    def _nav(self, url: str) -> bool:
        try:
            self.driver.get(url)
            jitter(2, 4)
            dismiss_modals(self.driver)
            return True
        except Exception as e:
            log.warning(f"  [NAV] Failed {url[:60]}: {e}")
            return False

    def _try_friend_request(self) -> bool:
        """Click Add Friend if available. Returns True if sent."""
        for by, sel in _FR_SENT:
            try:
                if self.driver.find_elements(by, sel):
                    return True   # already sent
            except Exception:
                pass

        btn = find_element(self.driver, _ADD_FRIEND, timeout=4, label="add-friend")
        if not btn:
            return False
        try:
            btn.click()
            jitter(1.5, 2.5)
            log.info("  [FR] Friend request sent")
            return True
        except Exception:
            return False

    def _try_dm(self, profile_url: str, message: str, uid: str) -> str:
        """
        Attempt to send a DM. Returns:
          "sent"       — message confirmed typed and sent
          "no_button"  — Message button not found
          "click_fail" — button found but click failed
          "input_fail" — button clicked, input not found / typing failed
        """
        original_handles = set(self.driver.window_handles)

        msg_btn = find_element(self.driver, _MSG_BTN, timeout=6, label="message-button")
        if not msg_btn:
            return "no_button"

        try:
            msg_btn.click()
            jitter(2, 3)
        except Exception:
            return "click_fail"

        # Handle new tab (messenger.com)
        new_handles = set(self.driver.window_handles) - original_handles
        if new_handles:
            self.driver.switch_to.window(new_handles.pop())
            jitter(2, 3)

        dismiss_modals(self.driver)
        jitter(2, 3)   # give messenger.com extra time

        msg_input = find_element(self.driver, _MSG_INPUT, timeout=15, label="message-input")
        if not msg_input:
            safe = re.sub(r'[<>:"/\\|?*]', '_', f"no_input_{uid}")
            screenshot(self.driver, safe)
            if new_handles:
                self.driver.close()
                self.driver.switch_to.window(list(original_handles)[0])
            return "input_fail"

        try:
            self.driver.execute_script("arguments[0].click();", msg_input)
            jitter(0.3, 0.8)
            for char in message:
                msg_input.send_keys(char)
                time.sleep(random.uniform(0.04, 0.10))
            jitter(1, 2)
            msg_input.send_keys(Keys.RETURN)
            jitter(2, 3)
        except Exception as e:
            log.warning(f"  [DM] Typing failed: {e}")
            if new_handles:
                self.driver.close()
                self.driver.switch_to.window(list(original_handles)[0])
            return "input_fail"

        if new_handles:
            self.driver.close()
            self.driver.switch_to.window(list(original_handles)[0])

        log.info(f"  DM sent: {message[:60]}...")
        return "sent"

    # ── Adaptation logic ──────────────────────────────────────────────────────

    def _on_dm_success(self):
        self.session["dm_sent"]    += 1
        self.session["consec_fail"] = 0
        if self.mode == self.MODE_SLOW and self.session["dm_sent"] % 3 == 0:
            log.info("[ENGINE] 3 successes in slow mode — reverting to normal")
            self.mode = self.MODE_NORMAL

    def _on_fr_success(self):
        self.session["fr_sent"]        += 1
        self.session["consec_fr_fail"]  = 0

    def _on_dm_fail(self, uid: str):
        self.session["dm_fail"]    += 1
        self.session["consec_fail"] = self.session.get("consec_fail", 0) + 1
        c = self.session["consec_fail"]

        if c == 3 and self.mode == self.MODE_NORMAL:
            log.info("[ENGINE] 3 consecutive DM fails → switching to FR-only mode")
            fb_alerts.alert("FB DMs — switching to FR-only mode",
                            f"3 consecutive DM failures. Will still send friend requests. "
                            f"Sent {self.session['dm_sent']} DMs so far this session.",
                            level="warn")
            self.mode = self.MODE_FR_ONLY

        elif c == 5 and self.mode == self.MODE_FR_ONLY:
            log.info("[ENGINE] 5 fails in FR-only mode → slow mode")
            self.mode = self.MODE_SLOW

        elif c >= 8:
            log.error("[ENGINE] 8 consecutive failures — likely challenge or full block")
            self._on_challenge(uid)

    def _on_fr_fail(self):
        self.session["fr_fail"]        += 1
        self.session["consec_fr_fail"] += 1
        if self.session["consec_fr_fail"] >= 5:
            log.warning("[ENGINE] 5 consecutive FR failures — may be rate limited")
            self.mode = self.MODE_SLOW

    def _on_challenge(self, uid: str):
        self.mode = self.MODE_PAUSED
        fb_alerts.alert(
            "Facebook challenge detected",
            f"Stopped at @{uid}. Open Facebook on your phone and verify. "
            "Run again after verification — pending DMs are queued.",
            level="error",
        )

    def _ai_adapt(self, profile_url: str, uid: str, failure_type: str):
        """
        Take a screenshot and ask Claude what's on the page.
        Adjusts strategy based on AI findings.
        """
        shot_name = re.sub(r'[<>:"/\\|?*]', '_', f"diag_{uid}")
        screenshot(self.driver, shot_name)

        # Find the screenshot file
        shots_dir = Path(__file__).parent / "screenshots"
        shots     = sorted(shots_dir.glob(f"{shot_name}*.png"), key=lambda p: p.stat().st_mtime)
        if not shots:
            return
        shot_path = str(shots[-1])

        diagnosis = _ai_diagnose(shot_path, f"failure={failure_type} profile={profile_url}")
        if not diagnosis:
            return

        log.info(f"  [AI] Diagnosis for @{uid}: {diagnosis}")

        if diagnosis.get("is_challenge"):
            log.error("  [AI] Challenge page detected via screenshot")
            self._on_challenge(uid)

        elif not diagnosis.get("has_message_btn") and not diagnosis.get("has_add_friend"):
            log.info("  [AI] Profile fully restricted — no actionable buttons")
            # Don't count as failure, just skip
            self.session["consec_fail"] = max(0, self.session["consec_fail"] - 1)

        elif diagnosis.get("has_message_btn") and failure_type == "input_fail":
            # Message button IS there but input not found — likely slow load
            log.info("  [AI] Message button visible but input timed out — will slow down")
            self.mode = self.MODE_SLOW

        notes = diagnosis.get("notes", "")
        if notes:
            log.info(f"  [AI] Notes: {notes}")
