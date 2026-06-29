"""
Shared browser utilities - modal handling, screenshots, safe element finding.
All Selenium interactions go through helpers here to avoid silent failures.
"""

import os, re, time, random, logging, shutil
from pathlib import Path
from typing import Optional

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, WebDriverException
)

log         = logging.getLogger("virel.fb.browser")
_DATA_DIR   = Path(os.getenv("DATA_DIR", "")).expanduser() if os.getenv("DATA_DIR") else None
_RUNTIME_DIR = (_DATA_DIR / "fb_outreach") if _DATA_DIR else Path(__file__).parent.absolute()
PROFILE_DIR = _RUNTIME_DIR / "chrome_profile"
SHOTS_DIR   = _RUNTIME_DIR / "screenshots"


def jitter(lo=1.5, hi=4.5):
    time.sleep(random.uniform(lo, hi))


def scroll(driver, times=3):
    for _ in range(times):
        driver.execute_script("window.scrollBy(0, window.innerHeight * 0.7)")
        jitter(0.8, 1.5)


_ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
_ON_GITHUB = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
_USE_SYSTEM_CHROME = _ON_RAILWAY or _ON_GITHUB or bool(os.getenv("CHROME_BIN"))

_CHALLENGE_PHRASES = [
    "confirm your identity", "security check", "unusual activity",
    "suspicious activity", "verify your account", "confirm it's you",
    "we've noticed unusual", "confirm your account", "account suspended",
    "your account has been", "temporarily blocked", "we limit how often",
    "we've temporarily restricted", "checkpoint",
]


def detect_challenge(driver) -> bool:
    """Return True if Facebook is showing a security/rate-limit challenge."""
    try:
        text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(phrase in text for phrase in _CHALLENGE_PHRASES)
    except Exception:
        return False


def build_driver(headless: bool = False):
    PROFILE_DIR.mkdir(exist_ok=True)
    SHOTS_DIR.mkdir(exist_ok=True)

    opts = webdriver.ChromeOptions() if _USE_SYSTEM_CHROME else uc.ChromeOptions()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--lang=en-US")

    force_headless = headless or _USE_SYSTEM_CHROME
    if force_headless:
        if _USE_SYSTEM_CHROME:
            log.info("[BROWSER] Cloud system Chrome detected - forcing headless")
        else:
            log.warning("[BROWSER] Headless mode increases bot-detection risk on Facebook")
        opts.add_argument("--headless=new")

    # System Chrome path for CI/cloud
    if _USE_SYSTEM_CHROME:
        for path in [os.getenv("CHROME_BIN", ""), "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser", "/usr/bin/chromium"]:
            if Path(path).exists():
                opts.binary_location = path
                break

        driver_path = os.getenv("CHROMEDRIVER_PATH", "") or shutil.which("chromedriver") or "/usr/bin/chromedriver"
        log.info(f"[BROWSER] System Chrome driver: {driver_path}")
        driver = (
            webdriver.Chrome(service=Service(driver_path), options=opts)
            if driver_path and Path(driver_path).exists()
            else webdriver.Chrome(options=opts)
        )
        driver.implicitly_wait(0)
        return driver

    chrome_version = _get_chrome_major_version()
    log.info(f"[BROWSER] Chrome {chrome_version} — fetching matching ChromeDriver...")

    driver_path = _get_driver_path(chrome_version)
    log.info(f"[BROWSER] Driver: {driver_path or 'auto'}")

    try:
        if driver_path:
            driver = uc.Chrome(
                options=opts,
                driver_executable_path=driver_path,
                use_subprocess=True,
            )
        else:
            driver = uc.Chrome(options=opts, version_main=chrome_version, use_subprocess=True)
    except Exception as e:
        log.warning(f"[BROWSER] Primary init failed ({e}), fallback...")
        time.sleep(5)   # let any lingering Chrome process release the profile lock
        opts2 = uc.ChromeOptions()
        opts2.add_argument(f"--user-data-dir={PROFILE_DIR}")
        opts2.add_argument("--profile-directory=Default")
        opts2.add_argument("--no-sandbox")
        opts2.add_argument("--disable-dev-shm-usage")
        if force_headless:
            opts2.add_argument("--headless=new")
        driver = uc.Chrome(options=opts2, use_subprocess=True)

    driver.implicitly_wait(0)
    return driver


def _get_chrome_major_version() -> int:
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in chrome_paths:
        if Path(p).exists():
            try:
                from win32api import GetFileVersionInfo, LOWORD, HIWORD
                info = GetFileVersionInfo(p, "\\")
                ms   = info["FileVersionMS"]
                return HIWORD(ms)
            except Exception:
                try:
                    import subprocess
                    vi = subprocess.check_output(
                        ["powershell", f"(Get-Item '{p}').VersionInfo.FileVersion"],
                        text=True, stderr=subprocess.DEVNULL
                    ).strip()
                    return int(vi.split(".")[0])
                except Exception:
                    pass
    return 148   # hardcode known version as fallback


def _get_driver_path(chrome_version: int) -> str | None:
    """Download ChromeDriver matching Chrome version via webdriver-manager."""
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import ChromeType
        path = ChromeDriverManager().install()
        log.info(f"[BROWSER] ChromeDriver from webdriver-manager: {path}")
        return path
    except Exception as e:
        log.warning(f"[BROWSER] webdriver-manager failed: {e}")
        return None


def screenshot(driver, name: str):
    """Save screenshot for debugging failed actions."""
    try:
        safe = re.sub(r'[<>:"/\\|?*]', '_', name)   # strip Windows-illegal chars
        path = SHOTS_DIR / f"{safe}_{int(time.time())}.png"
        driver.save_screenshot(str(path))
        log.info(f"  [SCREENSHOT] {path.name}")
    except Exception:
        pass


def dismiss_modals(driver) -> int:
    """Close any Facebook dialog modals. Returns count dismissed."""
    dismissed = 0
    for selector in [
        "//div[@role='dialog']//div[@aria-label='Close']",
        "//div[@role='dialog']//button[@aria-label='Close']",
        "//div[@aria-label='Close'][@role='button']",
    ]:
        try:
            btns = driver.find_elements(By.XPATH, selector)
            for btn in btns:
                btn.click()
                dismissed += 1
                jitter(0.5, 1.0)
        except Exception:
            pass
    if dismissed:
        log.info(f"  [MODAL] Dismissed {dismissed} dialog(s)")
    return dismissed


def find_element(driver, selectors: list, timeout: int = 8,
                 label: str = "element") -> Optional[object]:
    """
    Try multiple selectors in order. Returns first match or None.
    Logs which selector worked or that all failed.
    """
    for i, (by, sel) in enumerate(selectors):
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, sel))
            )
            log.debug(f"  Found {label} with selector #{i}")
            return el
        except TimeoutException:
            log.debug(f"  {label} selector #{i} timed out: {sel[:60]}")
        except Exception as e:
            log.debug(f"  {label} selector #{i} error: {e}")
    log.warning(f"  [{label.upper()}] All {len(selectors)} selectors failed")
    return None


def switch_to_new_tab(driver) -> bool:
    """If a new tab opened, switch to it. Returns True if switched."""
    handles = driver.window_handles
    if len(handles) > 1:
        driver.switch_to.window(handles[-1])
        jitter(2, 3)
        log.debug("  Switched to new tab")
        return True
    return False


def type_human(element, text: str):
    """Type with random inter-character delays to appear human."""
    element.click()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.04, 0.12))


def safe_get(driver, url: str, wait_for_css: str = None, timeout: int = 12) -> bool:
    """Navigate to URL, optionally wait for an element. Returns True on success."""
    try:
        driver.get(url)
        jitter(2, 4)
        if wait_for_css:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_css))
            )
        return True
    except TimeoutException:
        log.warning(f"  [LOAD] Timed out waiting for {wait_for_css} on {url[:60]}")
        screenshot(driver, "load_timeout")
        return False
    except WebDriverException as e:
        log.warning(f"  [LOAD] {url[:60]}: {e}")
        return False
