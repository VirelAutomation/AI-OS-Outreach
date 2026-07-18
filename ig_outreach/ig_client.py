"""
Instagram client wrapper.
- Always uses v1 API endpoints (no GraphQL — avoids challenge pages)
- Rate limit returns False immediately (no blocking sleep)
- Session verified with user_info_v1 (not timeline feed)
"""

import os, sys, json, base64, time, random, logging
from json import JSONDecodeError
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, ChallengeRequired, BadPassword, TwoFactorRequired, RateLimitError
)

# Add parent dir so ig_alerts can find fb_alerts pattern
sys.path.insert(0, str(Path(__file__).parent))

log = logging.getLogger("virel.ig")
_DATA_DIR = Path(os.getenv("DATA_DIR", "")).expanduser() if os.getenv("DATA_DIR") else None
_RUNTIME_DIR = (_DATA_DIR / "ig_outreach") if _DATA_DIR else Path(__file__).parent
SESSION_FILE = _RUNTIME_DIR / "session_virel.json"
SESSION_EXPORT_FILE = _RUNTIME_DIR / "INSTAGRAM_SESSION.txt"
SESSION_ID_FILE = _RUNTIME_DIR / "INSTAGRAM_SESSION_ID.txt"


def _ensure_runtime_dir():
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def build_client() -> Client:
    cl = Client()
    cl.delay_range = [2, 5]
    cl.logger = log
    # Use a randomised mobile device fingerprint to avoid session bans
    cl.set_device({
        "app_version": "269.0.0.18.75",
        "android_version": 31,
        "android_release": "12",
        "dpi": "480dpi",
        "resolution": "1080x2400",
        "manufacturer": "samsung",
        "device": "SM-G991B",
        "model": "samsung",
        "cpu": "qcom",
        "version_code": "314665256",
    })
    return cl


def _verify_v1(cl: Client) -> bool:
    """Non-GraphQL session check."""
    try:
        cl.user_info_v1(cl.user_id)
        return True
    except Exception:
        return False


def login(cl: Client) -> Client:
    _ensure_runtime_dir()
    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")
    if not username or not password:
        raise ValueError("INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD missing")

    # 1. Browser session ID (web cookie)
    session_id = os.getenv("INSTAGRAM_SESSION_ID", "")
    if session_id:
        try:
            cl2 = build_client()
            cl2.login_by_sessionid(session_id)
            if _verify_v1(cl2):
                log.info(f"[IG] Web session ID OK — @{username}")
                _save_session(cl2)
                return cl2
            log.warning("[IG] Session ID verify failed — trying other methods")
        except Exception as e:
            log.warning(f"[IG] Session ID login failed: {e}")

    # 2. Railway / env var full session blob
    encoded = os.getenv("INSTAGRAM_SESSION", "")
    if encoded:
        try:
            cl.set_settings(json.loads(base64.b64decode(encoded).decode()))
            if _verify_v1(cl):
                log.info(f"[IG] Railway session OK — @{username}")
                return cl
        except Exception as e:
            log.warning(f"[IG] Railway session invalid: {e}")

    # 3. Local session file
    if SESSION_FILE.exists():
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            if _verify_v1(cl):
                log.info(f"[IG] Session restored — @{username}")
                _save_session(cl)
                return cl
            else:
                log.warning("[IG] Session loaded but v1 verify failed — fresh login")
        except (ChallengeRequired, JSONDecodeError):
            log.warning("[IG] Session file triggered challenge — clearing and trying session ID path")
        except Exception as e:
            log.warning(f"[IG] Session file invalid: {e}")
        SESSION_FILE.unlink(missing_ok=True)

    # 4. Fresh login (API)
    log.info(f"[IG] Fresh login as @{username}...")
    cl = build_client()
    need_browser_refresh = False
    try:
        cl.login(username, password)
    except ChallengeRequired:
        log.warning("[IG] ChallengeRequired on API login — falling back to headless Chrome")
        need_browser_refresh = True
    except TwoFactorRequired:
        log.warning("[IG] 2FA required on API login — falling back to headless Chrome")
        need_browser_refresh = True
    except BadPassword:
        raise ValueError("[IG] Wrong password — check INSTAGRAM_PASSWORD env var")
    except (JSONDecodeError, Exception) as e:
        if "Expecting value" in str(e) or isinstance(e, JSONDecodeError):
            log.warning("[IG] Challenge returned empty page (JSON crash) — falling back to headless Chrome")
            need_browser_refresh = True
        else:
            raise

    if not need_browser_refresh and not _verify_v1(cl):
        log.warning("[IG] API login verify failed — falling back to headless Chrome")
        need_browser_refresh = True

    if need_browser_refresh:
        log.info("[IG] API login blocked — trying web login then headless Chrome...")
        try:
            from ig_session_refresh import refresh_and_save
            sid = refresh_and_save(
                username, password,
                session_file=SESSION_FILE,
                sessionid_file=SESSION_ID_FILE,
            )
            if sid and SESSION_FILE.exists():
                cl2 = build_client()
                cl2.load_settings(SESSION_FILE)
                log.info(f"[IG] Web/Chrome session loaded — @{username}")
                return cl2
            raise RuntimeError(
                "[IG] All login methods failed (API + web + Chrome).\n"
                "Check ig_outreach/screenshots/ig_*.png for what the browser saw.\n"
                "Most likely: wrong password, 2FA enabled, or Instagram hard-blocked the account."
            )
        except ImportError:
            raise RuntimeError(
                "[IG] ig_session_refresh.py not found — and API login is blocked.\n"
                "Run: python ig_outreach/ig_session_refresh.py"
            )

    _save_session(cl)
    log.info(f"[IG] Logged in as @{username}")
    return cl


def _save_session(cl: Client):
    _ensure_runtime_dir()
    settings = cl.get_settings()
    SESSION_FILE.write_text(json.dumps(settings))
    encoded = base64.b64encode(json.dumps(settings).encode()).decode()
    SESSION_EXPORT_FILE.write_text(f"INSTAGRAM_SESSION={encoded}\n")
    SESSION_ID_FILE.write_text(f"INSTAGRAM_SESSION_ID={settings.get('sessionid','')}\n")
    log.info(
        f"[IG] Session saved -> {SESSION_FILE.name}, {SESSION_EXPORT_FILE.name}, {SESSION_ID_FILE.name}"
        " (copy values to cloud env)"
    )


def send_dm(cl: Client, user_id: str, message: str) -> bool:
    try:
        cl.direct_send(message, user_ids=[int(user_id)])
        _jitter(2, 4)
        return True
    except RateLimitError:
        log.warning("[IG] Rate limited — will retry next run")
        return False
    except Exception as e:
        log.warning(f"[IG] DM failed uid={user_id}: {e}")
        return False


def get_user_info_by_id(cl: Client, uid: int):
    """v1 API only — no GraphQL."""
    try:
        info = cl.user_info_v1(uid)
        _jitter(1, 3)
        return info
    except Exception as e:
        err = str(e)
        if "JSONDecodeError" in err or "challenge" in err.lower():
            log.warning("[IG] Challenge on user_info — backing off 60s")
            time.sleep(60)
        else:
            log.warning(f"[IG] user_info error uid={uid}: {e}")
        return None
