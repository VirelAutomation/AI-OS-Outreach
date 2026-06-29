"""
Facebook group member scraper + DM sender.
Handles Messenger popup AND messenger.com redirect.
Only marks DM sent after verified delivery.
"""

import re, time, random, logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException, WebDriverException
)

import fb_db
import fb_alerts
from fb_browser import jitter, scroll, screenshot, dismiss_modals, find_element, switch_to_new_tab, detect_challenge
from fb_engine import OutreachEngine

log = logging.getLogger("virel.fb.dm")
FB  = "https://www.facebook.com"

# DMs reference the group — warm outreach (20-30% reply rate)
_DM = {
    "hvac": (
        "hey saw you in the group - we built a human sounding AI employee that answers all your calls "
        "and messages 24/7, books leads directly in your calendar and reaches out to new clients automatically. "
        "want to see it?"
    ),
    "med spa": (
        "hey saw you in the group - we built a human sounding AI employee that answers all your calls "
        "and messages 24/7, books appointments straight in your calendar and reaches out to new clients automatically. "
        "want to see how it works?"
    ),  # stays human sounding for med spa
    "coach": (
        "hey saw you in the group - we built a human sounding AI employee that gets you leads through ads, "
        "reaches out to all of them automatically and books calls directly in your calendar. "
        "works 24/7. want to see it?"
    ),
}
_DM_DEFAULT = _DM["coach"]

FOLLOWUP_1 = (
    "hey just checking in, did you get my message? "
    "still happy to walk you through the AI system real quick"
)
FOLLOWUP_2 = (
    "last one from me, if the timing isnt right no worries. "
    "just reach out whenever you want to see how it works"
)

_MSG_BTN_SELECTORS = [
    (By.XPATH, "//div[@aria-label='Message'][@role='button']"),
    (By.XPATH, "//a[contains(@href,'messenger')][@role='button']"),
    (By.XPATH, "//div[@role='button'][normalize-space()='Message']"),
    (By.XPATH, "//span[normalize-space()='Message']/ancestor::div[@role='button'][1]"),
]

_MSG_INPUT_SELECTORS = [
    # Messenger.com — the "Aa" placeholder textbox
    (By.CSS_SELECTOR,  "div[aria-label='Aa'][role='textbox']"),
    (By.XPATH,         "//div[@aria-label='Aa'][@role='textbox']"),
    (By.XPATH,         "//div[@aria-label='Aa'][@contenteditable='true']"),
    # Generic message/textbox selectors
    (By.CSS_SELECTOR,  "div[aria-label='Message'][role='textbox']"),
    (By.CSS_SELECTOR,  "div[contenteditable='true'][role='textbox']"),
    (By.XPATH,         "//div[@aria-label='Message'][@role='textbox']"),
    (By.XPATH,         "//div[@role='textbox'][@contenteditable='true']"),
    (By.XPATH,         "//div[@role='textbox'][contains(@aria-label,'essage')]"),
    (By.XPATH,         "//div[@data-testid='mwim-input-footer']//div[@role='textbox']"),
    (By.CSS_SELECTOR,  "div[aria-label*='essage'][role='textbox']"),
    (By.XPATH,         "//div[@contenteditable='true'][not(@aria-disabled)][not(@aria-label='Search')]"),
]

# Indian city/region names used to detect nationality from profile page
_INDIAN_CITIES = {
    "india", "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad",
    "chennai", "kolkata", "pune", "ahmedabad", "jaipur", "surat",
    "lucknow", "kanpur", "nagpur", "indore", "bhopal", "visakhapatnam",
    "patna", "vadodara", "coimbatore", "agra", "thane", "kerala",
    "gujarat", "maharashtra", "rajasthan", "karnataka", "tamil",
}

# Phone number patterns to extract from About page (indian-first, then generic)
_PHONE_PATTERNS = [
    r'\+91[\s\-\.]?\d{5}[\s\-\.]?\d{5}',   # +91 XXXXX XXXXX
    r'\+91[\s\-\.]?\d{10}',                  # +91 XXXXXXXXXX
    r'(?<!\d)91[\s\-\.]?\d{10}(?!\d)',       # 91XXXXXXXXXX (no +)
    r'\+\d{1,3}[\s\-\.]?\(?\d{2,4}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{4,6}',  # any intl
]


def scrape_whatsapp_number(driver, profile_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Visit the profile's About/Contact page, extract phone number and nationality.
    Returns (phone_number, nationality) — either may be None.
    Indians almost always have WhatsApp so +91 numbers are flagged.
    """
    if "profile.php" in profile_url:
        about_url = profile_url + "&sk=about_contact_and_basic_info"
    else:
        about_url = profile_url.rstrip("/") + "/about_contact_and_basic_info"
    try:
        driver.get(about_url)
        jitter(2, 3)
        dismiss_modals(driver)

        page_text = ""
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            return None, None

        # Detect Indian nationality via +91 or city/region mention
        nationality = None
        if "+91" in page_text or any(city in page_text for city in _INDIAN_CITIES):
            nationality = "indian"

        # Extract phone number
        phone = None
        for pattern in _PHONE_PATTERNS:
            m = re.search(pattern, page_text)
            if m:
                phone = re.sub(r'[\s\-\.]', '', m.group(0))
                if re.match(r'^91\d{10}$', phone):
                    phone = '+' + phone
                if phone.startswith('+91'):
                    nationality = "indian"
                break

        if phone:
            log.info(f"  [WHATSAPP] Found: {phone} ({nationality or 'unknown'})")

        return phone, nationality

    except Exception as e:
        log.debug(f"  WhatsApp scrape error ({profile_url.split('/')[-1]}): {e}")
        return None, None


_ADD_FRIEND_SELECTORS = [
    (By.XPATH, "//div[@aria-label='Add friend'][@role='button']"),
    (By.XPATH, "//div[@aria-label='Add Friend'][@role='button']"),
    (By.XPATH, "//a[@aria-label='Add friend']"),
    (By.XPATH, "//div[@role='button'][contains(normalize-space(),'Add friend')]"),
    (By.XPATH, "//div[@role='button'][contains(normalize-space(),'Add Friend')]"),
    (By.XPATH, "//span[contains(normalize-space(),'Add friend')]/ancestor::div[@role='button'][1]"),
]

_FRIEND_SENT_SELECTORS = [
    (By.XPATH, "//div[@aria-label='Friend request sent']"),
    (By.XPATH, "//div[@aria-label='Cancel request']"),
    (By.XPATH, "//div[@aria-label='Respond to friend request']"),
    (By.XPATH, "//div[@role='button'][normalize-space()='Requested']"),
    (By.XPATH, "//span[contains(.,'Requested')]"),
]


def send_friend_request(driver, profile_url: str) -> bool:
    """
    Navigate to profile and click Add Friend if available.
    Returns True if request was sent (or already pending).
    Skips if already friends (no Add Friend button present).
    """
    if not _safe_nav(driver, profile_url):
        return False

    dismiss_modals(driver)
    jitter(1.5, 3)

    # Check if already friends / request already sent
    for by, sel in _FRIEND_SENT_SELECTORS:
        try:
            if driver.find_elements(by, sel):
                log.info("  [FR] Already sent/friends — skip")
                return True
        except Exception:
            pass

    btn = find_element(driver, _ADD_FRIEND_SELECTORS, timeout=5, label="add-friend")
    if not btn:
        log.debug("  [FR] No Add Friend button — may already be friends or messaging allowed")
        return False

    try:
        btn.click()
        jitter(1.5, 2.5)
        log.info("  [FR] Friend request sent")
        return True
    except Exception as e:
        log.warning(f"  [FR] Click failed: {e}")
        return False


_FB_SYSTEM = {
    "help","legal","privacy","policies","about","ads","terms","settings",
    "notifications","bookmarks","gaming","stories","messages","messenger",
    "find-friends","on-this-day","saved","feeds","marketplace","watch",
    "news","places","login","register","recover","checkpoint","directory",
    "friends","profile","home","explore","hashtag","search","reel","reels",
    "video","photo","photos","videos","live","fundraisers","jobs","shops",
    "community","safety","support","business","creators","developers",
    "flicks","memories","weather","sports","today","moment","groups","pages",
    "events","share","sharer","dialog","intent","ajax","api","x","twitter",
}


def _parse_uid_from_href(href: str):
    """
    Extract (uid, profile_url) from a Facebook link (absolute or relative).
    Returns (None, None) if not a valid personal profile link.
    """
    if not href:
        return None, None

    # Group-context user link: /groups/ID/user/NUMERIC_ID/
    m_grp = re.search(r"/groups/\d+/user/(\d{6,})", href)
    if m_grp:
        uid = m_grp.group(1)
        return uid, f"{FB}/profile.php?id={uid}"

    # Numeric ID: profile.php?id=123
    m2 = re.search(r"profile\.php[?&]id=(\d{6,})", href)
    if m2:
        uid = m2.group(1)
        return uid, f"{FB}/profile.php?id={uid}"

    # Any numeric-only UID in a facebook.com path
    m_num = re.search(r"facebook\.com/(\d{8,})", href)
    if m_num:
        uid = m_num.group(1)
        return uid, f"{FB}/profile.php?id={uid}"

    # Username-style: facebook.com/username
    m = re.search(
        r"facebook\.com/(?!groups|pages|events|marketplace|watch|business|profile\.php|sharer)"
        r"([A-Za-z0-9._][A-Za-z0-9._-]{2,49})(?:[/?#]|$)",
        href
    )
    if m:
        uid = m.group(1).lower().rstrip("-.")
        if uid not in _FB_SYSTEM and re.match(r'^[\w.\-]+$', uid):
            return uid, f"{FB}/{uid}"

    return None, None


def _extract_profile_links(driver, seen: set, max_members: int) -> list:
    """Extract valid personal profile links from current page (handles relative + absolute URLs)."""
    results = []
    try:
        # Cast wide net — relative and absolute hrefs
        links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
    except WebDriverException:
        return results

    for link in links:
        if len(results) >= max_members:
            break
        try:
            href = link.get_attribute("href") or ""
        except StaleElementReferenceException:
            continue

        uid, profile_url = _parse_uid_from_href(href)
        if uid and uid not in seen:
            seen.add(uid)
            results.append({"uid": uid, "profile_url": profile_url})
    return results


def scrape_group_members(driver, group_url: str, max_members: int = 60) -> list:
    """
    Scrape members from a group. Tries the members tab first;
    if hidden/empty, falls back to scraping post authors from the group feed.
    """
    members_url = group_url.rstrip("/") + "/members"
    log.info(f"[SCRAPE] {members_url}")

    if not _safe_nav(driver, members_url):
        return []

    members = []
    seen    = set()
    attempt = 0

    while len(members) < max_members and attempt < 20:
        scroll(driver, times=4)
        jitter(1.5, 3)
        attempt += 1

        try:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='facebook.com/']")
        except WebDriverException:
            break

        new = _extract_profile_links(driver, seen, max_members)
        members.extend(new)

    if members:
        log.info(f"  Scraped {len(members)} members from members tab")
        return members[:max_members]

    # Members list hidden — fall back to group feed (post authors + commenters)
    log.info("  Members tab hidden — falling back to group feed scrape")
    return _scrape_group_feed(driver, group_url, max_members)


def _scrape_group_feed(driver, group_url: str, max_members: int) -> list:
    """Scrape post authors and commenters from the group's main feed."""
    if not _safe_nav(driver, group_url):
        return []

    dismiss_modals(driver)
    members = []
    seen    = set()

    for _ in range(15):
        if len(members) >= max_members:
            break
        scroll(driver, times=3)
        jitter(1.5, 2.5)
        new = _extract_profile_links(driver, seen, max_members)
        members.extend(new)

    log.info(f"  Scraped {len(members)} users from group feed")
    return members[:max_members]


def send_dm(driver, profile_url: str, message: str) -> bool:
    """
    Navigate to profile, click Message, handle popup OR messenger.com redirect,
    type and send message. Returns True ONLY if message box confirmed typed and sent.
    """
    original_handles = set(driver.window_handles)

    if not _safe_nav(driver, profile_url):
        return False

    dismiss_modals(driver)
    jitter(2, 4)

    # Click Message button
    msg_btn = find_element(driver, _MSG_BTN_SELECTORS, timeout=8, label="message-button")
    if not msg_btn:
        screenshot(driver, f"no_msg_btn_{profile_url.split('/')[-1]}")
        return False

    try:
        msg_btn.click()
        jitter(2, 4)
    except Exception as e:
        log.warning(f"  Message button click failed: {e}")
        return False

    # Handle new tab (messenger.com redirect) or inline popup
    new_handles = set(driver.window_handles) - original_handles
    if new_handles:
        driver.switch_to.window(new_handles.pop())
        jitter(2, 3)
        log.debug("  Switched to messenger.com tab")

    dismiss_modals(driver)

    # Find message input — give messenger.com extra time to load
    jitter(2, 3)
    msg_input = find_element(driver, _MSG_INPUT_SELECTORS, timeout=15, label="message-input")
    if not msg_input:
        screenshot(driver, f"no_input_{profile_url.split('/')[-1]}")
        # Close new tab if we opened one
        if new_handles:
            driver.close()
            driver.switch_to.window(list(original_handles)[0])
        return False

    # Type message
    try:
        msg_input.click()
        jitter(0.5, 1.0)
        for char in message:
            msg_input.send_keys(char)
            time.sleep(random.uniform(0.04, 0.10))
        jitter(1, 2)
    except Exception as e:
        log.warning(f"  Typing failed: {e}")
        screenshot(driver, "typing_failed")
        return False

    # Send with Enter
    try:
        msg_input.send_keys(Keys.RETURN)
        jitter(2, 3)
    except Exception as e:
        log.warning(f"  Send key failed: {e}")
        return False

    # Close messenger tab if we opened one, return to original
    if new_handles:
        driver.close()
        driver.switch_to.window(list(original_handles)[0])

    log.info(f"  DM sent: {message[:60]}...")
    return True


_MAX_CONSECUTIVE_FAILS = 3   # alert + stop after this many DM failures in a row


def _tomorrow_2pm() -> str:
    """Return IST timestamp for tomorrow at 2pm — default retry window."""
    from datetime import timezone, timedelta
    IST      = timezone(timedelta(hours=5, minutes=30))
    tomorrow = datetime.now(IST).replace(hour=14, minute=0, second=0, microsecond=0)
    tomorrow += timedelta(days=1)
    return tomorrow.isoformat()


def run_pending_queue(driver) -> int:
    """Process DMs that were queued from a previous failed/limited run."""
    due = fb_db.get_pending_dm_queue()
    if not due:
        return 0

    log.info(f"[QUEUE] {len(due)} pending DMs from previous runs...")
    fb_alerts.alert(f"Retrying {len(due)} queued DMs", level="info")
    sent = 0

    for item in due:
        if detect_challenge(driver):
            fb_alerts.alert(
                "Facebook challenge detected mid-queue",
                "Stopping queue processing. Manual verification required.",
                level="error"
            )
            break

        uid         = item["fb_uid"]
        profile_url = item["profile_url"]
        message     = item["message"]

        if fb_db.has_been_dmed(uid):
            fb_db.mark_queue_sent(item["id"])
            continue

        log.info(f"  [QUEUE] Retrying @{uid}...")
        if send_dm(driver, profile_url, message):
            fb_db.log_dm(uid, profile_url, item["group_source"], item["niche"], message)
            fb_db.mark_queue_sent(item["id"])
            sent += 1
            log.info(f"  [QUEUE SENT] @{uid}")
            jitter(300, 600)
        else:
            next_retry = _tomorrow_2pm()
            fb_db.increment_queue_attempt(item["id"], next_retry)
            log.warning(f"  [QUEUE FAIL] @{uid} — rescheduled")

    log.info(f"[QUEUE] {sent} sent from queue")
    return sent


def run_dm_outreach(driver, daily_limit: int = 10) -> int:
    """
    Scrape members from joined groups, send warm DMs.
    Uses OutreachEngine for self-healing adaptive strategy.
    """
    already   = fb_db.dms_today()
    remaining = daily_limit - already
    if remaining <= 0:
        msg = f"Daily DM limit of {daily_limit} already reached."
        log.info(f"[DM] {msg}")
        fb_alerts.alert("FB DMs — daily limit reached", msg, level="info")
        return 0

    groups = fb_db.get_joined_groups()
    if not groups:
        log.info("[DM] No joined groups. Run --join first.")
        fb_alerts.alert("FB DMs — no groups", "No active groups to DM from. Run --join.", level="warn")
        return 0

    engine = OutreachEngine(driver)
    sent   = 0

    for group in groups:
        if sent >= remaining or engine.is_paused():
            break

        gid    = group["group_id"]
        gname  = group["group_name"]
        niche  = group["niche"]
        gurl   = group["group_url"]
        dm_msg = _DM.get(niche.lower(), _DM_DEFAULT)

        log.info(f"[DM] Scraping '{gname}' ({niche})...")
        members = scrape_group_members(driver, gurl, max_members=80)
        if not members:
            log.warning(f"  No members found in '{gname}'")
            continue

        for member in members:
            if sent >= remaining or engine.is_paused():
                break

            uid         = member["uid"]
            profile_url = member["profile_url"]

            if fb_db.has_been_dmed(uid):
                continue

            log.info(f"  [DM] @{uid} | engine: {engine.status()}")
            fb_db.save_checkpoint("dm", group_id=gid, fb_uid=uid)

            # Scrape WhatsApp/nationality from About page
            whatsapp_num, nationality = scrape_whatsapp_number(driver, profile_url)

            # Engine handles all strategy, fallbacks and adaptation
            result = engine.attempt(profile_url, dm_msg, uid)

            if result == OutreachEngine.RESULT_SENT:
                fb_db.log_dm(uid, profile_url, gname, niche, dm_msg,
                             whatsapp_number=whatsapp_num, nationality=nationality,
                             friend_request_sent=True)
                fb_db.clear_checkpoint()
                sent += 1
                wa_tag = f" | WA: {whatsapp_num}" if whatsapp_num else ""
                log.info(f"  [SENT #{sent}/{remaining}] @{uid}{wa_tag}")
                gap = engine.gap()
                log.info(f"  Waiting {gap//60}m {gap%60}s...")
                time.sleep(gap)

            elif result == OutreachEngine.RESULT_FR_ONLY:
                fb_db.log_dm(uid, profile_url, gname, niche,
                             "(pending — friend request sent)",
                             whatsapp_number=whatsapp_num, nationality=nationality,
                             friend_request_sent=True)
                fb_db.clear_checkpoint()
                jitter(10, 20)

            elif result == OutreachEngine.RESULT_BLOCKED:
                # Challenge — queue everything remaining and stop
                idx = members.index(member)
                _queue_remaining(members, idx, gname, niche, dm_msg, gid)
                log.error("[DM] Blocked — remaining DMs queued for tomorrow 2pm")
                return sent

            else:  # SKIPPED
                fb_db.clear_checkpoint()
                jitter(5, 15)

    total_today = fb_db.dms_today()
    queue_size  = fb_db.get_pending_queue_count()
    summary     = f"Sent {sent} DMs today ({total_today}/{daily_limit}). Engine final mode: {engine.mode}."
    if queue_size:
        summary += f" {queue_size} queued for tomorrow 2pm."

    log.info(f"[DM] Done — {summary}")
    if sent > 0:
        fb_alerts.alert("FB DMs complete", summary, level="ok")
    elif sent == 0:
        fb_alerts.alert("FB DMs — 0 sent",
                        f"Engine mode: {engine.mode}. Check screenshots.",
                        level="warn")
    return sent


def _queue_remaining(members: list, start_idx: int, group_source: str,
                     niche: str, message: str, group_id: str):
    """Queue all remaining uncontacted members for tomorrow 2pm."""
    scheduled = _tomorrow_2pm()
    queued    = 0
    for member in members[start_idx:]:
        uid = member["uid"]
        if not fb_db.has_been_dmed(uid):
            fb_db.queue_pending_dm(
                uid, member["profile_url"], group_source,
                niche, message, "auto_queued", scheduled
            )
            queued += 1
    if queued:
        log.info(f"  [QUEUE] {queued} DMs queued for tomorrow 2pm")


def run_followups(driver) -> int:
    """Send due follow-up DMs to non-repliers."""
    due = fb_db.get_due_followups()
    if not due:
        log.info("[FOLLOWUPS] Nothing due.")
        return 0

    log.info(f"[FOLLOWUPS] {len(due)} due.")
    sent = 0

    for fu in due:
        uid  = fu["fb_uid"]
        purl = fu["profile_url"]
        num  = fu["followup_number"]
        msg  = FOLLOWUP_1 if num == 1 else FOLLOWUP_2

        log.info(f"  Followup #{num} to @{uid}...")
        if send_dm(driver, purl, msg):
            fb_db.mark_followup_sent(fu["id"], msg)
            sent += 1
            log.info(f"  [SENT] @{uid}")
            jitter(60, 120)

    log.info(f"[FOLLOWUPS] {sent}/{len(due)} sent")
    return sent


def _safe_nav(driver, url: str) -> bool:
    try:
        driver.get(url)
        jitter(3, 5)
        dismiss_modals(driver)
        return True
    except Exception as e:
        log.warning(f"  Navigation failed {url[:60]}: {e}")
        return False
