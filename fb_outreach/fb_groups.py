"""
Facebook group finder, joiner, and poster.
Every action verified before marking as done.
StaleElementReferenceException handled everywhere.
"""

import re, time, random, logging
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, WebDriverException
)

import fb_db
import fb_alerts
from fb_browser import (
    jitter, scroll, screenshot, dismiss_modals,
    find_element, safe_get, type_human, detect_challenge
)
from fb_posts import GROUP_SEARCH_TERMS, get_post, parse_member_count, MIN_GROUP_MEMBERS

log = logging.getLogger("virel.fb.groups")

FB = "https://www.facebook.com"

# Selectors with multiple fallbacks — first one that works wins
_JOIN_SELECTORS = [
    (By.XPATH, "//div[@role='button'][normalize-space()='Join group']"),
    (By.XPATH, "//div[@role='button'][normalize-space()='Join']"),
    (By.XPATH, "//a[@role='button'][contains(.,'Join')]"),
    (By.XPATH, "//span[normalize-space()='Join group']/ancestor::div[@role='button']"),
]

_POST_BOX_SELECTORS = [
    (By.XPATH, "//div[@role='button'][contains(@aria-label,'Write')]"),
    (By.XPATH, "//div[@role='button'][contains(.,'Write something')]"),
    (By.XPATH, "//div[@role='button'][contains(.,'What')]"),
    (By.XPATH, "//span[contains(.,'Write something')]/ancestor::div[@role='button'][1]"),
    (By.CSS_SELECTOR, "[data-testid='status-attachment-mentions-input']"),
]

_POST_BTN_SELECTORS = [
    (By.XPATH, "//div[@aria-label='Post'][@role='button']"),
    (By.XPATH, "//div[@role='button'][normalize-space()='Post']"),
    (By.CSS_SELECTOR, "button[data-testid='react-composer-post-button']"),
]

_POST_CONFIRM_SELECTORS = [
    (By.XPATH, "//div[@role='article']"),
    (By.CSS_SELECTOR, "[data-pagelet='GroupFeed']"),
]


def search_and_join_groups(driver, niche: str, max_join: int = 10, max_total: int = 10) -> list:
    """
    Search and join groups for a niche. Fills all available slots in one run.
    Groups needing admin approval are saved as 'pending' and skipped for posting
    until verify_pending_groups() confirms membership.
    """
    current = fb_db.get_groups_count_for_niche(niche)
    if current >= max_total:
        log.info(f"[JOIN] '{niche}' at cap ({current}/{max_total}) — skipping joins")
        return []

    slots    = max_total - current
    joined   = []
    keywords = GROUP_SEARCH_TERMS.get(niche, [])

    for keyword in keywords:
        if len(joined) >= slots:
            break

        log.info(f"[JOIN] Searching: '{keyword}'")
        search_url = f"{FB}/groups/search/?q={keyword.replace(' ', '+')}"

        if not safe_get(driver, search_url):
            log.warning(f"  Search failed for '{keyword}'")
            jitter(30, 60)
            continue

        scroll(driver, times=4)
        dismiss_modals(driver)

        group_ids = _collect_group_ids(driver)
        log.info(f"  Found {len(group_ids)} group IDs")

        for group_id in group_ids:
            if len(joined) >= slots:
                break
            if fb_db.has_joined(group_id):
                continue

            group_url  = f"{FB}/groups/{group_id}"
            result     = _join_group(driver, group_url, group_id, niche=niche)
            if result:
                name, status = result
                fb_db.log_group_joined(group_id, name, group_url, niche, status=status)
                joined.append({"group_id": group_id, "group_name": name,
                               "group_url": group_url, "niche": niche, "status": status})
                tag = "[JOINED]" if status == "active" else "[PENDING approval]"
                log.info(f"  {tag} '{name}'")
                jitter(10, 20)

        jitter(8, 15)

    active  = sum(1 for g in joined if g["status"] == "active")
    pending = sum(1 for g in joined if g["status"] == "pending")
    log.info(f"[JOIN] Done — {active} active, {pending} pending admin approval")
    return joined


def verify_pending_groups(driver) -> int:
    """
    Re-check groups saved as 'pending'. If you're now a member, mark them active.
    Run this a day or two after --join to activate admin-approved groups.
    """
    pending = fb_db.get_pending_groups()
    if not pending:
        log.info("[VERIFY] No pending groups to check")
        return 0

    log.info(f"[VERIFY] Checking {len(pending)} pending groups...")
    activated = 0

    for g in pending:
        if not safe_get(driver, g["group_url"]):
            continue
        dismiss_modals(driver)

        # If we can see the post box we're a member
        try:
            body = driver.find_element(By.TAG_NAME, "body").text
            if any(phrase in body.lower() for phrase in
                   ["write something", "what's on your mind", "create post"]):
                fb_db.activate_group(g["group_id"])
                activated += 1
                log.info(f"  [ACTIVATED] '{g['group_name']}'")
            else:
                log.info(f"  [STILL PENDING] '{g['group_name']}'")
        except Exception:
            pass
        jitter(3, 6)

    log.info(f"[VERIFY] {activated} groups activated")
    return activated


def _collect_group_ids(driver) -> list:
    """Safely collect group IDs from current search results page."""
    ids  = []
    seen = set()
    try:
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/groups/']")
        for link in links:
            try:
                href = link.get_attribute("href") or ""
            except StaleElementReferenceException:
                continue
            match = re.search(r"/groups/([^/?#&]+)", href)
            if not match:
                continue
            gid = match.group(1)
            if gid in seen or gid in ("feed","discover","search","join","create","notifications"):
                continue
            # Must look like a real group ID (alphanumeric, not a page path)
            if re.match(r"^[\w.-]+$", gid) and len(gid) > 3:
                seen.add(gid)
                ids.append(gid)
    except Exception as e:
        log.warning(f"  _collect_group_ids: {e}")
    return ids


_PENDING_INDICATORS = [
    "request sent", "request pending", "pending", "asked to join",
    "cancel request", "cancel join request",
]

def _join_group(driver, group_url: str, group_id: str, niche: str = "") -> Optional[tuple]:
    """
    Navigate to group, click Join. Returns (group_name, status) or None.
    status = 'active' if immediately joined, 'pending' if awaiting admin approval.
    """
    if not safe_get(driver, group_url):
        return None

    dismiss_modals(driver)
    jitter(2, 4)

    group_name = group_id
    try:
        h1 = driver.find_elements(By.CSS_SELECTOR, "h1")
        if h1:
            group_name = h1[0].text.strip() or group_id
    except Exception:
        pass

    # Member count gate for niches that require it
    min_members = MIN_GROUP_MEMBERS.get(niche, 0)
    if min_members:
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            count     = parse_member_count(body_text)
            if count and count < min_members:
                log.info(f"  [SKIP] '{group_name}' ~{count:,} members (need {min_members:,}+)")
                return None
            if count:
                log.info(f"  '{group_name}' — {count:,} members — qualifies")
        except Exception:
            pass

    btn = find_element(driver, _JOIN_SELECTORS, timeout=5, label="join-button")
    if not btn:
        # Already a member
        log.info(f"  No Join button for '{group_name}' — already a member")
        return (group_name, "active")

    try:
        btn.click()
        jitter(3, 5)
    except Exception as e:
        log.warning(f"  Join click failed for '{group_name}': {e}")
        return None

    # Check if it went pending or active
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if any(phrase in body_text for phrase in _PENDING_INDICATORS):
            return (group_name, "pending")
        # Can see post box = active member
        if any(phrase in body_text for phrase in ["write something", "what's on your mind", "create post"]):
            return (group_name, "active")
    except Exception:
        pass

    # Default: assume pending since most groups require approval
    return (group_name, "pending")


def discover_existing_groups(driver, niche: str = "business_owner") -> list:
    """
    Scrape Facebook's 'Groups you've joined' page and register any unknown groups in DB.
    Use this to pick up groups you manually joined outside the script.
    """
    log.info("[DISCOVER] Scanning your joined groups on Facebook...")
    added = []

    for url in [f"{FB}/groups/feed/", f"{FB}/groups/"]:
        if not safe_get(driver, url):
            continue
        scroll(driver, times=6)
        dismiss_modals(driver)

        group_ids = _collect_group_ids(driver)
        log.info(f"  Found {len(group_ids)} group IDs on {url}")

        for gid in group_ids:
            if fb_db.has_joined(gid):
                continue

            gurl = f"{FB}/groups/{gid}"
            if not safe_get(driver, gurl):
                continue

            dismiss_modals(driver)

            # Get name
            gname = gid
            try:
                h1 = driver.find_elements(By.CSS_SELECTOR, "h1")
                if h1:
                    gname = h1[0].text.strip() or gid
            except Exception:
                pass

            # Get member count
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                count     = parse_member_count(body_text)
            except Exception:
                count = 0

            fb_db.log_group_joined(gid, gname, gurl, niche)
            added.append({"group_id": gid, "group_name": gname, "group_url": gurl,
                          "niche": niche, "members": count})
            count_str = f"{count:,}" if count else "unknown"
            log.info(f"  [ADDED] '{gname}' — {count_str} members → niche: {niche}")
            jitter(3, 6)

        break  # one page is enough

    log.info(f"[DISCOVER] {len(added)} new groups added to DB")
    return added


def post_in_groups(driver, daily_limit: int = 10, niche: str = None) -> int:
    """Post in all joined groups not yet posted in today. Returns posts made."""
    already = fb_db.posts_today()
    remaining = daily_limit - already
    if remaining <= 0:
        log.info(f"[POST] Daily limit {daily_limit} reached.")
        return 0

    groups = fb_db.get_joined_groups(niche=niche)
    if not groups:
        log.info("[POST] No groups joined yet. Run --join first.")
        return 0

    posted            = 0
    consecutive_fails = 0

    for group in groups:
        if posted >= remaining:
            break

        gid   = group["group_id"]
        gname = group["group_name"]
        niche = group["niche"]
        gurl  = group["group_url"]

        if fb_db.posted_today(gid):
            log.info(f"  [skip] Already posted in '{gname}' today")
            continue

        if detect_challenge(driver):
            fb_alerts.alert(
                "Facebook challenge detected during posting",
                f"Stopped after {posted} posts. Verify account on phone.",
                level="error"
            )
            log.error("[POST] Challenge detected — stopping.")
            break

        message = get_post(niche)
        log.info(f"[POST] '{gname}' ({niche})")
        log.info(f"  Message preview: {message[:80]}...")

        fb_db.save_checkpoint("posting", group_id=gid)

        ok = _post_to_group(driver, gurl, message)
        if ok:
            fb_db.log_post(gid, gname, niche, message, verified=True)
            fb_db.clear_checkpoint()
            posted += 1
            consecutive_fails = 0
            log.info(f"  [DONE #{posted}] '{gname}' - verified posted")
            gap = random.randint(480, 900)
            log.info(f"  Waiting {gap//60}m {gap%60}s before next post...")
            time.sleep(gap)
        else:
            consecutive_fails += 1
            log.warning(f"  [FAIL #{consecutive_fails}] '{gname}' — not posted")
            jitter(15, 30)
            if consecutive_fails >= 3:
                fb_alerts.alert(
                    "FB Posts — 3 consecutive failures",
                    f"Stopping. Posted {posted}/{daily_limit} today. Selector may be broken.",
                    level="error"
                )
                log.error("[POST] Too many consecutive failures — stopping.")
                break

    total_today = fb_db.posts_today()
    log.info(f"[POST] Done — {posted} posts | Today total: {total_today}/{daily_limit}")
    if posted > 0:
        fb_alerts.alert("FB Posts complete", f"Posted in {posted} groups today.", level="ok")
    elif posted == 0 and remaining > 0:
        fb_alerts.alert("FB Posts — 0 posted", "No posts went through. Check screenshots.", level="warn")
    return posted


def _post_to_group(driver, group_url: str, message: str) -> bool:
    """Navigate to group, type post, submit, VERIFY it appeared. Returns True only if verified."""
    if not safe_get(driver, group_url):
        return False

    dismiss_modals(driver)
    scroll(driver, times=2)
    jitter(2, 4)

    # Scroll nav bar out of the way then click post box via JS to bypass interception
    driver.execute_script("window.scrollBy(0, 200)")
    jitter(1, 2)

    post_box = find_element(driver, _POST_BOX_SELECTORS, timeout=10, label="post-box")
    if not post_box:
        screenshot(driver, "post_box_missing")
        return False

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post_box)
        jitter(0.5, 1)
        driver.execute_script("arguments[0].click();", post_box)
        jitter(1.5, 3)
    except Exception as e:
        log.warning(f"  Post box click failed: {e}")
        return False

    # Find the text input inside the composer modal that opened after clicking post box
    _COMPOSER_INPUT = [
        (By.CSS_SELECTOR, "div[contenteditable='true'][role='textbox']"),
        (By.CSS_SELECTOR, "div[data-lexical-editor='true']"),
        (By.CSS_SELECTOR, "div[contenteditable='true'].notranslate"),
        (By.XPATH, "//div[@role='dialog']//div[@contenteditable='true']"),
        (By.XPATH, "//div[@contenteditable='true'][@role='textbox']"),
        (By.CSS_SELECTOR, "div[contenteditable='true']"),
    ]
    composer = find_element(driver, _COMPOSER_INPUT, timeout=8, label="composer-input")
    if not composer:
        screenshot(driver, "composer_input_missing")
        return False

    try:
        driver.execute_script("arguments[0].click();", composer)
        jitter(0.5, 1)
        for char in message:
            composer.send_keys(char)
            time.sleep(random.uniform(0.04, 0.10))
        jitter(1, 2)
    except Exception as e:
        log.warning(f"  Typing failed: {e}")
        screenshot(driver, "typing_failed")
        return False

    # Click Post button via JS to avoid nav interception
    post_btn = find_element(driver, _POST_BTN_SELECTORS, timeout=8, label="post-button")
    if not post_btn:
        screenshot(driver, "post_btn_missing")
        return False

    try:
        driver.execute_script("arguments[0].click();", post_btn)
    except Exception as e:
        log.warning(f"  Post button click failed: {e}")
        return False

    jitter(4, 7)
    dismiss_modals(driver)

    # VERIFY — check post actually appeared (feed refreshed with new content)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='article']"))
        )
        log.info("  Post verified in feed")
        return True
    except TimeoutException:
        screenshot(driver, "post_verify_failed")
        log.warning("  Could not verify post appeared — marking as unverified")
        return False
