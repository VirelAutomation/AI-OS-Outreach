"""Facebook login - phone/email + password via Selenium.
Session is exportable as FACEBOOK_SESSION env var (base64 JSON cookies)
so it works on cloud runners without a visible browser.
"""

import os, time, logging, json, base64
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from selenium.webdriver.common.action_chains import ActionChains
from fb_browser import jitter, type_human, dismiss_modals, screenshot

log = logging.getLogger("virel.fb.login")
FB  = "https://www.facebook.com"
_DATA_DIR = Path(os.getenv("DATA_DIR", "")).expanduser() if os.getenv("DATA_DIR") else None
_RUNTIME_DIR = (_DATA_DIR / "fb_outreach") if _DATA_DIR else Path(__file__).parent

# Multiple selectors for the email/phone field — Facebook changes these
_EMAIL_SELECTORS = [
    (By.ID,   "email"),
    (By.NAME, "email"),
    (By.CSS_SELECTOR, "input[type='text'][name='email']"),
    (By.CSS_SELECTOR, "input[placeholder*='mobile']"),
    (By.CSS_SELECTOR, "input[placeholder*='Email']"),
    (By.XPATH, "//input[@id='email' or @name='email']"),
    (By.XPATH, "//input[contains(@placeholder,'mobile') or contains(@placeholder,'Email')]"),
]

_PASS_SELECTORS = [
    (By.ID,   "pass"),
    (By.NAME, "pass"),
    (By.CSS_SELECTOR, "input[type='password']"),
    (By.XPATH, "//input[@type='password']"),
]

_HOME_SELECTORS = [
    (By.CSS_SELECTOR, "[aria-label='Home']"),
    (By.CSS_SELECTOR, "[data-pagelet='LeftRail']"),
    (By.CSS_SELECTOR, "div[role='navigation']"),
    (By.XPATH, "//div[@role='navigation']"),
    (By.CSS_SELECTOR, "a[href='/'][aria-label]"),
]


def _find(driver, selectors, timeout=15, label="element"):
    for by, sel in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, sel))
            )
            log.debug(f"  Found {label}: {sel[:50]}")
            return el
        except TimeoutException:
            continue
        except Exception:
            continue
    return None


def is_logged_in(driver) -> bool:
    try:
        driver.get(FB)
        jitter(4, 6)
        dismiss_modals(driver)
        for by, sel in _HOME_SELECTORS:
            try:
                els = driver.find_elements(by, sel)
                if els:
                    log.info("[FB] Already logged in")
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def _save_session(driver):
    """Save Facebook cookies as base64 for FACEBOOK_SESSION env var."""
    try:
        _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        cookies = driver.get_cookies()
        encoded = base64.b64encode(json.dumps(cookies).encode()).decode()
        SESSION_FILE.write_text(encoded)
        # Write full value to file for easy copy-paste to Railway
        SESSION_EXPORT_FILE.write_text(
            f"FACEBOOK_SESSION={encoded}\n"
        )
        log.info(f"[FB] Session saved -> {SESSION_FILE.name} + {SESSION_EXPORT_FILE.name} (copy to cloud env)")
        return encoded
    except Exception as e:
        log.warning(f"[FB] Session save failed: {e}")
        return None


SESSION_FILE = _RUNTIME_DIR / "session_fb.txt"
SESSION_EXPORT_FILE = _RUNTIME_DIR / "FACEBOOK_SESSION.txt"


def _load_session(driver) -> bool:
    """Try loading session from FACEBOOK_SESSION env var or local file."""
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    encoded = os.getenv("FACEBOOK_SESSION", "")
    if not encoded and SESSION_FILE.exists():
        encoded = SESSION_FILE.read_text().strip()

    if not encoded:
        return False

    try:
        cookies = json.loads(base64.b64decode(encoded).decode())
        driver.get(FB)
        time.sleep(3)
        for cookie in cookies:
            # Strip unsupported fields
            cookie.pop("sameSite", None)
            cookie.pop("expiry",   None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        driver.refresh()
        time.sleep(4)
        log.info("[FB] Session cookies loaded")
        return True
    except Exception as e:
        log.warning(f"[FB] Session load failed: {e}")
        return False


def login(driver) -> bool:
    phone = os.getenv("FACEBOOK_EMAIL", "")
    pwd   = os.getenv("FACEBOOK_PASSWORD", "")
    if not phone or not pwd:
        raise ValueError("FACEBOOK_EMAIL / FACEBOOK_PASSWORD not set in forge_system/.env")

    # 1. Try cookie session first (works on Railway — no browser login needed)
    if _load_session(driver) and is_logged_in(driver):
        log.info(f"[FB] Session restored from cookies — {phone}")
        return True

    if is_logged_in(driver):
        log.info(f"[FB] Session active — {phone}")
        _save_session(driver)
        return True

    log.info(f"[FB] Logging in with {phone}...")
    driver.get(f"{FB}/login")
    jitter(4, 7)
    dismiss_modals(driver)

    # Find and fill email/phone field
    email_f = _find(driver, _EMAIL_SELECTORS, timeout=15, label="email-field")
    if not email_f:
        screenshot(driver, "no_email_field")
        log.error("[FB] Could not find login email/phone field")
        log.error("  Try running the script and logging in manually in the Chrome window")
        return _wait_for_manual_login(driver)

    try:
        _fill_react_input(driver, email_f, phone)
        jitter(0.8, 1.5)
    except Exception as e:
        log.error(f"[FB] Could not type phone/email: {e}")
        return _wait_for_manual_login(driver)

    # Find and fill password field
    pass_f = _find(driver, _PASS_SELECTORS, timeout=8, label="password-field")
    if not pass_f:
        screenshot(driver, "no_pass_field")
        log.error("[FB] Could not find password field")
        return _wait_for_manual_login(driver)

    try:
        _fill_react_input(driver, pass_f, pwd)
        jitter(0.5, 1.0)

        # Click Login button explicitly (more reliable than .submit())
        login_btn = None
        for sel in ["button[type='submit']", "button[name='login']",
                    "[data-testid='royal_login_button']"]:
            try:
                login_btn = driver.find_element(By.CSS_SELECTOR, sel)
                break
            except Exception:
                pass
        if login_btn:
            login_btn.click()
        else:
            pass_f.submit()

        log.info("[FB] Credentials submitted — waiting for redirect...")
        jitter(8, 14)
        dismiss_modals(driver)
    except Exception as e:
        log.error(f"[FB] Submit failed: {e}")
        return _wait_for_manual_login(driver)

    # Check if logged in
    if is_logged_in(driver):
        log.info("[FB] Login successful")
        _save_session(driver)
        return True

    # OTP / 2FA — give user time to complete in browser
    screenshot(driver, "after_submit")
    log.warning("[FB] Not on home page after login — may need OTP/2FA")
    return _wait_for_manual_login(driver, seconds=60)


def _fill_react_input(driver, element, text: str):
    """
    Fill a React-controlled input field reliably.
    1. Click to focus
    2. Select all + delete existing content
    3. Type via ActionChains (triggers React events properly)
    4. Fallback to JS setValue if ActionChains fails
    """
    import time, random
    from selenium.webdriver.common.keys import Keys

    # Click to focus
    ActionChains(driver).move_to_element(element).click().perform()
    time.sleep(0.3)

    # Clear existing content
    element.send_keys(Keys.CONTROL + "a")
    time.sleep(0.1)
    element.send_keys(Keys.DELETE)
    time.sleep(0.2)

    # Type via ActionChains — triggers React onChange properly
    ac = ActionChains(driver)
    for char in text:
        ac.send_keys(char)
    ac.perform()
    time.sleep(0.5)

    # Verify text was entered, fallback to JS if not
    current = element.get_attribute("value") or ""
    if len(current) < len(text) * 0.5:
        log.debug(f"  ActionChains typing partial ({len(current)}/{len(text)}), using JS fallback")
        driver.execute_script("""
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(arguments[0], arguments[1]);
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, element, text)
        time.sleep(0.3)

    log.debug(f"  Typed {len(text)} chars into field")


def _wait_for_manual_login(driver, seconds=180) -> bool:
    """
    Wait for user to complete login manually in the browser.
    Polls every 5 seconds. Session is saved to Chrome profile after success
    so this manual step only happens ONCE ever.
    """
    import os
    phone = os.getenv("FACEBOOK_EMAIL", "")
    log.warning("=" * 55)
    log.warning("  ACTION REQUIRED — Log into Facebook in the browser")
    log.warning(f"  Account: {phone}")
    log.warning("  Complete any OTP sent to your phone")
    log.warning(f"  You have {seconds} seconds ({seconds//60} min)")
    log.warning("=" * 55)

    for i in range(0, seconds, 5):
        time.sleep(5)
        if is_logged_in(driver):
            log.info("[FB] Manual login confirmed! Session saved — won't need this again.")
            return True
        remaining = seconds - i - 5
        if remaining > 0 and remaining % 30 == 0:
            log.info(f"[FB] Waiting for manual login... {remaining}s left")

    screenshot(driver, "login_final_fail")
    log.error("[FB] Timed out waiting for login. Run again and log in faster.")
    return False
