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

    # ── 1. Browser session ID (web cookie — bypasses phone challenge) ──────────
    # Get this from instagram.com → DevTools → Application → Cookies → sessionid
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

    # ── 2. Railway / env var full session blob ────────────────────────────────
    encoded = os.getenv("INSTAGRAM_SESSION", "")
    if encoded:
        try:
            cl.set_settings(json.loads(base64.b64decode(encoded).decode()))
            cl.login(username, password)
            if _verify_v1(cl):
                log.info(f"[IG] Railway session OK — @{username}")
                return cl
        except Exception as e:
            log.warning(f"[IG] Railway session invalid: {e}")

    # ── 3. Local session file ─────────────────────────────────────────────────
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

    # ── 4. Fresh login (API) ──────────────────────────────────────────────────
    log.info(f"[IG] Fresh login as @{username}...")
    cl = build_client()
    _need_browser_refresh = False
    try:
        cl.login(username, password)
    except ChallengeRequired:
        log.warning("[IG] ChallengeRequired on API login — falling back to headless Chrome")
        _need_browser_refresh = True
    except TwoFactorRequired:
        log.warning("[IG] 2FA required on API login — falling back to headless Chrome")
        _need_browser_refresh = True
    except BadPassword:
        raise ValueError("[IG] Wrong password — check INSTAGRAM_PASSWORD env var")
    except (JSONDecodeError, Exception) as e:
        if "Expecting value" in str(e) or isinstance(e, JSONDecodeError):
            log.warning("[IG] Challenge returned empty page (JSON crash) — falling back to headless Chrome")
            _need_browser_refresh = True
        else:
            raise

    if not _need_browser_refresh and not _verify_v1(cl):
        log.warning("[IG] API login verify failed — falling back to headless Chrome")
        _need_browser_refresh = True

    # ── 5. Web login + headless Chrome fallback ───────────────────────────────
    if _need_browser_refresh:
        log.info("[IG] API login blocked — trying web login then headless Chrome...")
        try:
            from ig_session_refresh import refresh_and_save
            sid = refresh_and_save(
                username, password,
                session_file=SESSION_FILE,
                sessionid_file=SESSION_ID_FILE,
            )
            if sid and SESSION_FILE.exists():
                # refresh_and_save already verified the session internally.
                # Load the saved settings directly — avoids device fingerprint conflict
                # that happens if we call login_by_sessionid() again with a different UA.
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
    # Write full session to separate file so it can be copied to Railway / Render env vars
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
        return False           # never block — caller handles
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
            time.sleep(60)      # brief back-off, not 5 min
        else:
            log.debug(f"[IG] user_info_v1 {uid}: {e}")
        return None


def get_user_info(cl: Client, username: str):
    try:
        info = cl.user_info_by_username_v1(username)
        _jitter(1, 3)
        return info
    except Exception:
        try:
            return cl.user_info_by_username(username)
        except Exception as e:
            log.warning(f"[IG] get_user_info @{username}: {e}")
            return None


# Maps search keywords → hashtags for fallback when user search is blocked
_HASHTAG_MAP = {
    "business coach":       ["businesscoach", "businesscoaching", "businesscoachtips"],
    "life coach":           ["lifecoach", "lifecoaching", "lifecoachtips"],
    "executive coach":      ["executivecoach", "executivecoaching", "leadershipcoach"],
    "online coach":         ["onlinecoach", "onlinecoaching", "onlinebusinesscoach"],
    "mindset coach":        ["mindsetcoach", "mindsetcoaching", "mindsetmentor"],
    "success coach":        ["successcoach", "successcoaching", "successmindset"],
    "health coach":         ["healthcoach", "healthcoaching", "wellnesscoach"],
    "fitness coach":        ["fitnesscoach", "fitnessmotivation", "personaltrainer"],
    "coaching business":    ["coachingbusiness", "coachlife", "coachpreneur"],
    "business consultant":  ["businessconsultant", "businessconsulting", "businessadvisor"],
    "marketing consultant": ["marketingconsultant", "marketingcoach", "marketingstrategy"],
    "strategy consultant":  ["strategyconsultant", "businessstrategy", "growthadvisor"],
    "consultant usa":       ["consultant", "consultantlife", "smallbusinessowner"],
    "online consultant":    ["onlineconsultant", "virtualconsultant", "remotecoach"],
    "coaches and consultants": ["coachesofinstagram", "consultantsofinstagram", "coachlife"],
    "coach entrepreneur":   ["coachpreneur", "entrepreneurcoach", "coachingtips"],
    "consulting business":  ["consultingbusiness", "consultinglife", "businessgrowth"],
    "certified coach":      ["certifiedcoach", "icfcoach", "professionalcoach"],
}


def search_users_by_keyword(cl: Client, keyword: str, limit: int = 40) -> list:
    """Try user search first, fall back to hashtag search if blocked."""
    try:
        results = cl.search_users(keyword)
        _jitter(2, 4)
        uids = [str(u.pk) for u in results[:limit] if u]
        if uids:
            return uids
    except Exception as e:
        log.warning(f"[IG] search_users blocked ('{keyword}'): {e} — trying hashtags")

    # Hashtag fallback — get recent media users for matching hashtags
    hashtags = _HASHTAG_MAP.get(keyword.lower(), [keyword.replace(" ", "")])
    uids = []
    seen = set()
    for tag in hashtags:
        if len(uids) >= limit:
            break
        try:
            medias = cl.hashtag_medias_recent(tag, amount=20)
            _jitter(2, 4)
            for m in medias:
                uid = str(m.user.pk)
                if uid not in seen:
                    seen.add(uid)
                    uids.append(uid)
        except Exception as e:
            log.warning(f"[IG] hashtag '{tag}': {e}")
            _jitter(3, 6)

    log.info(f"  [HASHTAG] '{keyword}' → {len(uids)} users via hashtags")
    return uids[:limit]


def is_account_blocked(cl: Client) -> bool:
    """
    Detect a full account checkpoint/ban or expired session.
    Returns True if ALL endpoints fail — including login_required (session dead).
    """
    try:
        results = cl.hashtag_info("businesscoach")
        if results:
            return False
    except Exception as e:
        if "login_required" in str(e).lower():
            return True   # session is dead — treat as blocked

    try:
        cl.search_users("coach", 1)
        return False
    except Exception as e:
        err = str(e).lower()
        if "challenge" in err or "checkpoint" in err or "login_required" in err:
            return True
        return False


def check_inbox_for_replies(cl: Client, known_user_ids: set) -> list:
    """
    Scan DM inbox and return user_ids of known leads who replied.
    Uses v1 inbox API — no GraphQL.
    """
    replied = []
    try:
        threads = cl.direct_threads(amount=30) or []
        for thread in threads:
            users = getattr(thread, "users", None) or []
            for user in users:
                uid = str(user.pk)
                if uid not in known_user_ids:
                    continue
                try:
                    msgs = cl.direct_messages(thread.id, amount=5) or []
                except Exception:
                    continue
                for msg in msgs:
                    if str(getattr(msg, "user_id", "")) == uid:
                        replied.append(uid)
                        break
    except Exception as e:
        log.warning(f"[IG] Inbox scan failed: {e}")
    return replied


def post_comment(cl: Client, media_id: str, text: str) -> bool:
    """Post a comment on a media. Returns True on success."""
    try:
        cl.media_comment(media_id, text)
        _jitter(3, 6)
        return True
    except RateLimitError:
        log.warning("[IG] Rate limited on comment — backing off 60s")
        time.sleep(60)
        return False
    except Exception as e:
        log.warning(f"[IG] Comment failed on {media_id}: {e}")
        return False


def like_media(cl: Client, media_id: str) -> bool:
    """Like a post. Returns True on success."""
    try:
        cl.media_like(media_id)
        _jitter(1, 3)
        return True
    except Exception as e:
        log.debug(f"[IG] Like failed {media_id}: {e}")
        return False


def get_hashtag_posts(cl: Client, hashtag: str, amount: int = 20) -> list:
    """Get recent posts from a hashtag. Returns list of media objects."""
    try:
        medias = cl.hashtag_medias_recent(hashtag, amount=amount)
        _jitter(2, 4)
        return medias or []
    except Exception as e:
        log.warning(f"[IG] hashtag_medias '{hashtag}': {e}")
        _jitter(3, 6)
        return []


def get_user_recent_posts(cl: Client, user_id: str, amount: int = 5) -> list:
    """Get a user's recent posts."""
    try:
        medias = cl.user_medias(int(user_id), amount=amount)
        _jitter(2, 3)
        return medias or []
    except Exception as e:
        log.debug(f"[IG] user_medias {user_id}: {e}")
        return []


def _jitter(lo: float, hi: float):
    time.sleep(random.uniform(lo, hi))
