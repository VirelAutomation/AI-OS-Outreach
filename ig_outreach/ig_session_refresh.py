"""
Instagram session refresh — two strategies, tried in order:

  1. Web login  (requests only, no Chrome, works everywhere)
     POST instagram.com/accounts/login/ajax/ → extract sessionid cookie
     Lightest option, zero extra dependencies.

  2. Headless Chrome fallback (same uc setup as FB outreach, Linux/Railway)
     Used if web login is challenged or returns an empty sessionid.

Run standalone to refresh a dead session:
    python ig_outreach/ig_session_refresh.py
"""

import os, sys, time, random, logging, shutil
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

log = logging.getLogger("virel.ig.session")

_ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
_ON_GITHUB = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
_USE_SYSTEM_CHROME = _ON_RAILWAY or _ON_GITHUB or bool(os.getenv("CHROME_BIN"))
_DATA_DIR = Path(os.getenv("DATA_DIR", "")).expanduser() if os.getenv("DATA_DIR") else None
_RUNTIME_DIR = (_DATA_DIR / "ig_outreach") if _DATA_DIR else Path(__file__).parent
_SHOTS_DIR  = _RUNTIME_DIR / "screenshots"

_WEB_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _jitter(lo: float = 1.0, hi: float = 3.0):
    time.sleep(random.uniform(lo, hi))


# ── Strategy 1: Web login via requests (no Chrome, no phone) ─────────────────

def web_login(username: str, password: str) -> str | None:
    """
    Logs into instagram.com using plain HTTP requests.
    No Chrome, no browser, no phone — works on any cloud server.
    Returns the sessionid cookie string, or None if challenged/failed.
    """
    import requests

    log.info("[IG-SESSION] Trying web login (requests)...")
    s = requests.Session()
    s.headers.update({
        "User-Agent":      _WEB_UA,
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
    })

    try:
        # Step 1: load the login page to get CSRF token + cookies
        r = s.get("https://www.instagram.com/accounts/login/", timeout=20)
        if r.status_code != 200:
            log.warning(f"[IG-WEB] Login page returned {r.status_code}")
            return None

        csrf = s.cookies.get("csrftoken", "")
        if not csrf:
            # Try extracting from page source
            import re
            m = re.search(r'"csrf_token":"([^"]+)"', r.text)
            csrf = m.group(1) if m else ""
        if not csrf:
            log.warning("[IG-WEB] Could not get CSRF token")
            return None

        _jitter(1.5, 3.0)

        # Step 2: POST login
        s.headers.update({
            "X-CSRFToken":     csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer":         "https://www.instagram.com/accounts/login/",
            "Content-Type":    "application/x-www-form-urlencoded",
            "Origin":          "https://www.instagram.com",
        })

        ts = int(time.time())
        resp = s.post(
            "https://www.instagram.com/accounts/login/ajax/",
            data={
                "username":            username,
                "enc_password":        f"#PWD_INSTAGRAM_BROWSER:0:{ts}:{password}",
                "queryParams":         "{}",
                "optIntoOneTap":       "false",
                "stopDeletionNonce":   "",
                "trustedDeviceRecords": "{}",
            },
            timeout=20,
        )

        try:
            data = resp.json()
        except Exception:
            log.warning(f"[IG-WEB] Non-JSON response ({resp.status_code}): {resp.text[:200]}")
            return None

        if data.get("authenticated"):
            sid = s.cookies.get("sessionid", "")
            if sid:
                log.info(f"[IG-SESSION] Web login OK — sessionid {len(sid)} chars")
                return sid
            log.warning("[IG-WEB] Authenticated but sessionid cookie missing")
            return None

        if data.get("checkpoint_url") or data.get("lock"):
            log.warning(f"[IG-WEB] Checkpoint challenge: {data.get('checkpoint_url','')}")
            return None

        if data.get("two_factor_required"):
            log.warning("[IG-WEB] 2FA required on web login")
            return None

        log.warning(f"[IG-WEB] Unexpected response: {data}")
        return None

    except Exception as e:
        log.warning(f"[IG-WEB] Web login error: {e}")
        return None


def _type_human(element, text: str):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.05, 0.14))


def _build_driver():
    import undetected_chromedriver as uc
    _SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    opts = webdriver.ChromeOptions() if _USE_SYSTEM_CHROME else uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--lang=en-US,en")
    # Cloud (Railway/Linux): force headless, same as FB outreach
    if _USE_SYSTEM_CHROME or os.getenv("IG_HEADLESS"):
        log.info("[IG-SESSION] Headless Chrome mode")
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
    chrome_bin = os.getenv("CHROME_BIN", "")
    if chrome_bin and Path(chrome_bin).exists():
        opts.binary_location = chrome_bin

    if _USE_SYSTEM_CHROME:
        if not getattr(opts, "binary_location", None):
            for path in ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser", "/usr/bin/chromium"]:
                if Path(path).exists():
                    opts.binary_location = path
                    break
        driver_path = os.getenv("CHROMEDRIVER_PATH", "") or shutil.which("chromedriver") or "/usr/bin/chromedriver"
        log.info(f"[IG-SESSION] System Chrome driver: {driver_path}")
        driver = (
            webdriver.Chrome(service=Service(driver_path), options=opts)
            if driver_path and Path(driver_path).exists()
            else webdriver.Chrome(options=opts)
        )
        driver.set_page_load_timeout(45)
        driver.implicitly_wait(0)
        return driver

    # use_subprocess=True causes ConnectionResetError on Windows; only needed on Linux
    use_sub = sys.platform != "win32"
    driver = uc.Chrome(options=opts, use_subprocess=use_sub)
    driver.set_page_load_timeout(45)
    driver.implicitly_wait(0)
    return driver


def _dismiss_popups(driver):
    """Dismiss 'Save info', 'Turn on notifications', cookie banners."""
    for label in ["Not Now", "Not now", "Skip", "Decline", "Close"]:
        try:
            btn = driver.find_element("xpath", f"//button[contains(text(),'{label}')]")
            btn.click()
            _jitter(0.5, 1.2)
            return
        except Exception:
            pass


def refresh_session(username: str, password: str) -> str | None:
    """
    Logs into instagram.com in headless Chrome, returns the sessionid cookie.
    Returns None if login fails — check ig_outreach/screenshots/ig_*.png for what browser saw.
    """
    log.info("[IG-SESSION] Launching headless Chrome → instagram.com")
    driver = None
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        driver = _build_driver()
        wait   = WebDriverWait(driver, 25)

        driver.get("https://www.instagram.com/accounts/login/")
        _jitter(2.5, 4.5)

        # Accept cookie consent if present (EU / some regions)
        try:
            btn = wait.until(EC.element_to_be_clickable(
                ("xpath", "//button[contains(text(),'Allow') or contains(text(),'Accept all')]")
            ))
            btn.click()
            _jitter(1, 2)
        except TimeoutException:
            pass

        # Fill username
        try:
            user_field = wait.until(EC.presence_of_element_located(
                ("css selector", "input[name='username']")
            ))
        except TimeoutException:
            log.error("[IG-SESSION] Login form not found")
            driver.save_screenshot(str(_SHOTS_DIR / "ig_no_form.png"))
            return None

        user_field.click()
        _jitter(0.3, 0.7)
        _type_human(user_field, username)
        _jitter(0.4, 0.9)

        # Fill password
        pass_field = driver.find_element("css selector", "input[name='password']")
        pass_field.click()
        _jitter(0.3, 0.7)
        _type_human(pass_field, password)
        _jitter(0.5, 1.0)

        # Submit
        pass_field.submit()
        log.info("[IG-SESSION] Credentials submitted — waiting for home feed...")
        _jitter(4, 7)

        # Wait up to 20s for redirect away from login page, dismissing popups along the way
        for _ in range(8):
            url = driver.current_url
            if "instagram.com" in url and "/accounts/login" not in url and "/challenge" not in url:
                break
            _dismiss_popups(driver)
            _jitter(2, 3)

        # Still on login/challenge page = failed
        if "/accounts/login" in driver.current_url:
            log.error("[IG-SESSION] Still on login page after submit")
            driver.save_screenshot(str(_SHOTS_DIR / "ig_login_fail.png"))
            return None

        if "/challenge" in driver.current_url:
            log.error("[IG-SESSION] Challenge page hit (likely 2FA or suspicious activity)")
            driver.save_screenshot(str(_SHOTS_DIR / "ig_challenge.png"))
            return None

        # Dismiss any post-login prompts
        _dismiss_popups(driver)
        _jitter(1, 2)
        _dismiss_popups(driver)

        # Extract sessionid
        cookies = driver.get_cookies()
        sessionid = next((c["value"] for c in cookies if c["name"] == "sessionid"), None)

        if not sessionid:
            log.error("[IG-SESSION] sessionid cookie not found after login")
            driver.save_screenshot(str(_SHOTS_DIR / "ig_no_sessionid.png"))
            return None

        log.info(f"[IG-SESSION] sessionid extracted ({len(sessionid)} chars)")
        return sessionid

    except Exception as e:
        log.error(f"[IG-SESSION] Browser error: {e}")
        if driver:
            try:
                driver.save_screenshot(str(_SHOTS_DIR / "ig_session_error.png"))
            except Exception:
                pass
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def refresh_and_save(username: str, password: str,
                     session_file: Path, sessionid_file: Path) -> str | None:
    """
    Full refresh: try web login first (no Chrome), fall back to headless Chrome.
    Returns sessionid on success, None on failure.
    """
    def _verify_and_save(candidate_sessionid: str) -> str | None:
        try:
            from instagrapi import Client
            cl = Client()
            cl.delay_range = [2, 5]
            cl.login_by_sessionid(candidate_sessionid)
            info = cl.user_info_v1(cl.user_id)
            if not info:
                log.error("[IG-SESSION] login_by_sessionid verify failed")
                return None

            import json, base64
            settings = cl.get_settings()
            session_file.parent.mkdir(parents=True, exist_ok=True)
            session_file.write_text(json.dumps(settings))
            encoded = base64.b64encode(json.dumps(settings).encode()).decode()
            sessionid_file.write_text(
                f"# Paste this into Railway env vars or .env\n"
                f"INSTAGRAM_SESSION_ID={candidate_sessionid}\n"
                f"INSTAGRAM_SESSION={encoded}\n"
            )
            log.info(f"[IG-SESSION] Saved -> {session_file.name} + {sessionid_file.name}")
            return candidate_sessionid
        except Exception as e:
            log.error(f"[IG-SESSION] instagrapi verify error: {e}")
            return None

    # Strategy 1: web login (fastest, no browser required)
    sessionid = web_login(username, password)
    if sessionid:
        verified = _verify_and_save(sessionid)
        if verified:
            return verified
        log.info("[IG-SESSION] Web session failed instagrapi verify -> trying headless Chrome fallback...")

    # Strategy 2: headless Chrome (same as FB outreach on Railway)
    sessionid = refresh_session(username, password)
    if not sessionid:
        return None

    return _verify_and_save(sessionid)


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / "forge_system" / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _SHOTS_DIR.mkdir(parents=True, exist_ok=True)

    uname = os.getenv("INSTAGRAM_USERNAME")
    pwd   = os.getenv("INSTAGRAM_PASSWORD")
    if not uname or not pwd:
        print("ERROR: set INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD in forge_system/.env")
        sys.exit(1)

    _session_file   = _RUNTIME_DIR / "session_virel.json"
    _sessionid_file = _RUNTIME_DIR / "INSTAGRAM_SESSION_ID.txt"

    sid = refresh_and_save(uname, pwd, _session_file, _sessionid_file)
    if sid:
        print(f"\nSUCCESS — session saved")
        print(f"To use on Railway: copy INSTAGRAM_SESSION or INSTAGRAM_SESSION_ID from {_sessionid_file}")
    else:
        print("\nFAILED — check ig_outreach/screenshots/ig_*.png for what the browser saw")
        sys.exit(1)
