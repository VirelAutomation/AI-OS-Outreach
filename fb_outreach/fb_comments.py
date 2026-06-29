"""
Facebook Group Comment Engine.

Comments on posts in joined groups to generate leads via visibility.
Strategy: comment on member posts (not our own) → they see our profile → DM follows.
25 comments per batch per slot (scheduler drives cadence).

Tracks all comments in fb_comments table — no duplicate posts ever.
"""

import os, re, time, random, logging
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, WebDriverException,
)

import fb_db
import fb_alerts
from fb_browser import (
    jitter, scroll, screenshot, dismiss_modals,
    find_element, safe_get, detect_challenge,
)

log = logging.getLogger("virel.fb.comments")

DAILY_LIMIT = int(os.getenv("FACEBOOK_DAILY_COMMENT_LIMIT", "60"))

# ── Niche comment templates ───────────────────────────────────────────────────

_TEMPLATES: dict[str, list[str]] = {
    "hvac": [
        "Really solid work. What software are you using for scheduling?",
        "Love seeing HVAC businesses doing content like this.",
        "This is the kind of post that builds real trust with homeowners.",
        "Great perspective. Are you handling follow-ups manually or automated?",
        "Solid insight — this separates the good contractors from the great ones.",
        "This is spot on. Most HVAC owners underestimate this.",
        "Really appreciate the transparency here. Great post.",
        "Love this. More contractors need to be doing this.",
    ],
    "med_spa": [
        "This is such a great way to build trust with potential clients.",
        "Love seeing aesthetic businesses doing content marketing like this.",
        "Really professional. How are you currently managing client inquiries?",
        "Solid presence — this kind of content really converts.",
        "Great point. Most med spas skip this step entirely.",
        "Really valuable post for anyone in the aesthetics space.",
        "Love the approach here. Results speak for themselves.",
        "This is the content that builds a lasting client base.",
    ],
    "coach": [
        "This hits exactly where most coaches get stuck. Great call.",
        "100%. The ones who get this early are the ones scaling.",
        "Solid advice — way more people need to hear this.",
        "This is the kind of content that builds a real audience.",
        "Love the clarity here. This is what good coaching looks like.",
        "Really valuable post — saving this one.",
        "This is gold. Wish more coaches were saying this.",
        "Spot on. This is what separates good coaches from great ones.",
    ],
    "consultant": [
        "Really solid insight here. Saving this one.",
        "This is exactly where most consultants leave money on the table.",
        "100%. The best consultants I know all do this.",
        "Great framework. How long did it take you to develop this?",
        "Really valuable post — this is what real consulting looks like.",
        "Love the breakdown here. Really practical.",
        "Solid advice that applies across every niche.",
        "This is the kind of content that gets you referrals.",
    ],
    "business_owner": [
        "Really solid insight. Saving this one.",
        "This is the kind of advice that actually moves the needle.",
        "More business owners need to see this. Great post.",
        "Real value right here. Thank you for posting.",
        "This is gold. What's been your biggest win applying this?",
        "Spot on. Most business owners miss this completely.",
        "Love the transparency here. Really refreshing.",
        "Great post — this is what real growth looks like.",
    ],
    "digital_marketing_agency": [
        "This is exactly where most agencies are leaving money on the table.",
        "Solid strategy. What results are you seeing with this approach?",
        "100%. The agencies winning right now all understand this.",
        "Really valuable post — agencies need to hear this more.",
        "Great breakdown. Have you seen this scale across different niches?",
        "Love the clarity here. This is what good agency work looks like.",
        "Spot on — this is the kind of insight that moves clients.",
        "Really solid content. This is what separates good agencies from great ones.",
    ],
}

_DEFAULT = [
    "Really valuable post. Thanks for sharing this.",
    "This is exactly the kind of content that helps businesses grow.",
    "Solid insight here. Saving this.",
    "Love seeing content like this in this group.",
    "Great post — this is what real business growth looks like.",
    "Really appreciate you sharing this. Helpful perspective.",
    "Spot on. More people need to hear this.",
    "This is the kind of post that actually adds value.",
]


def _get_comment(niche: str) -> str:
    pool = _TEMPLATES.get(niche, _DEFAULT)
    return random.choice(pool)


# ── Selectors ─────────────────────────────────────────────────────────────────

_COMMENT_INPUT = [
    (By.XPATH, "//div[@aria-label='Write a comment…'][@contenteditable='true']"),
    (By.XPATH, "//div[@aria-label='Write a comment...'][@contenteditable='true']"),
    (By.XPATH, "//div[@aria-placeholder='Write a comment…'][@contenteditable='true']"),
    (By.XPATH, "//div[@aria-placeholder='Write a comment...'][@contenteditable='true']"),
    (By.CSS_SELECTOR, "div[aria-label*='comment'][contenteditable='true']"),
    (By.CSS_SELECTOR, "div[aria-placeholder*='comment'][contenteditable='true']"),
]

_COMMENT_TRIGGER = [
    (By.XPATH, "//div[@aria-label='Leave a comment']"),
    (By.XPATH, "//span[normalize-space()='Comment']/ancestor::div[@role='button'][1]"),
    (By.XPATH, "//div[@aria-label='Comment'][@role='button']"),
    (By.CSS_SELECTOR, "div[aria-label='Leave a comment']"),
]


# ── Post discovery ────────────────────────────────────────────────────────────

def _collect_post_ids(driver, group_id: str) -> list[str]:
    """
    Find post IDs from the group feed by looking for links that follow the
    /groups/{group_id}/posts/{post_id}/ pattern.
    """
    post_ids = []
    seen = set()
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href") or ""
            except StaleElementReferenceException:
                continue
            m = re.search(r"/groups/[^/]+/posts/([^/?#&]+)", href)
            if m:
                pid = m.group(1)
                if pid not in seen:
                    seen.add(pid)
                    post_ids.append(pid)
    except Exception as e:
        log.debug(f"  _collect_post_ids error: {e}")
    return post_ids


def _comment_on_post(driver, post_url: str, comment_text: str) -> bool:
    """
    Navigate to post URL, find the comment box, type comment, submit.
    Returns True if comment was submitted successfully.
    """
    if not safe_get(driver, post_url):
        return False

    dismiss_modals(driver)
    scroll(driver, times=2)
    jitter(2, 3)

    # Try to find the comment input directly
    comment_input = find_element(driver, _COMMENT_INPUT, timeout=6, label="comment-input")

    if not comment_input:
        # Click the comment trigger to open the input
        trigger = find_element(driver, _COMMENT_TRIGGER, timeout=5, label="comment-trigger")
        if trigger:
            try:
                driver.execute_script("arguments[0].click();", trigger)
                jitter(1, 2)
                comment_input = find_element(driver, _COMMENT_INPUT, timeout=5, label="comment-input-2")
            except Exception as e:
                log.debug(f"  Comment trigger click failed: {e}")

    if not comment_input:
        log.debug(f"  No comment input found at {post_url}")
        screenshot(driver, "comment_input_missing")
        return False

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", comment_input)
        jitter(0.5, 1)
        driver.execute_script("arguments[0].click();", comment_input)
        jitter(0.5, 1)

        for char in comment_text:
            comment_input.send_keys(char)
            time.sleep(random.uniform(0.04, 0.09))

        jitter(1, 1.5)
        comment_input.send_keys(Keys.RETURN)
        jitter(2, 4)
        return True

    except Exception as e:
        log.warning(f"  Comment type/submit error: {e}")
        screenshot(driver, "comment_fail")
        return False


# ── Main engine ───────────────────────────────────────────────────────────────

def run_comments(driver, niche: str = "coach", region: str = "us",
                 daily_limit: int = DAILY_LIMIT) -> int:
    """
    Comment on posts in joined FB groups matching `niche`.
    `region` is logged for tracking but groups are filtered by niche only
    (we join niche-appropriate groups per region via --join already).
    Returns number of comments posted this run.
    """
    already   = fb_db.get_fb_comments_today()
    remaining = min(daily_limit, DAILY_LIMIT - already)

    if remaining <= 0:
        log.info(f"[FB-COMMENTS] Daily limit {DAILY_LIMIT} reached ({already} done).")
        return 0

    log.info(f"[FB-COMMENTS] Starting — niche={niche}, region={region}, remaining={remaining}")

    groups = fb_db.get_joined_groups(niche=niche)
    if not groups:
        # Fall back: any active group
        groups = fb_db.get_joined_groups()
        if not groups:
            log.info(f"[FB-COMMENTS] No groups in DB. Run --join first.")
            return 0
        log.info(f"[FB-COMMENTS] No niche={niche} groups — using all {len(groups)} groups")

    random.shuffle(groups)
    commented = 0
    consecutive_fails = 0

    for group in groups:
        if commented >= remaining:
            break

        if detect_challenge(driver):
            fb_alerts.alert(
                "Facebook challenge detected during comments",
                f"Stopped after {commented} comments. Verify on phone.",
                level="error",
            )
            log.error("[FB-COMMENTS] Challenge detected — stopping.")
            break

        gid    = group["group_id"]
        gname  = group["group_name"]
        gurl   = group["group_url"]
        gniche = group["niche"] or niche

        log.info(f"[FB-COMMENTS] Group: '{gname}' ({gniche})")

        if not safe_get(driver, gurl):
            log.warning(f"  Could not load '{gname}'")
            consecutive_fails += 1
            if consecutive_fails >= 3:
                log.error("[FB-COMMENTS] 3 consecutive group load failures — stopping.")
                break
            continue

        dismiss_modals(driver)
        scroll(driver, times=5)
        jitter(2, 4)

        post_ids = _collect_post_ids(driver, gid)
        log.info(f"  {len(post_ids)} posts found in '{gname}'")

        group_commented = 0

        for post_id in post_ids:
            if commented >= remaining or group_commented >= 3:
                break

            if fb_db.has_fb_commented_on(post_id):
                continue

            post_url     = f"https://www.facebook.com/groups/{gid}/posts/{post_id}/"
            comment_text = _get_comment(gniche)

            log.info(f"  Post {post_id}: '{comment_text[:60]}'")

            ok = _comment_on_post(driver, post_url, comment_text)

            if ok:
                fb_db.log_fb_comment(post_id, gid, gname, gniche, comment_text)
                commented += 1
                group_commented += 1
                consecutive_fails = 0
                log.info(f"  [DONE #{commented}] '{gname}' post {post_id}")

                gap = random.randint(180, 360)
                log.info(f"  Waiting {gap // 60}m {gap % 60}s...")
                time.sleep(gap)
            else:
                consecutive_fails += 1
                log.warning(f"  [FAIL] post {post_id}")
                jitter(10, 20)
                if consecutive_fails >= 5:
                    fb_alerts.alert(
                        "FB Comments — 5 consecutive failures",
                        f"Stopping. {commented} comments done. Selectors may be broken.",
                        level="error",
                    )
                    log.error("[FB-COMMENTS] Too many failures — stopping.")
                    return commented

        jitter(5, 12)

    total = fb_db.get_fb_comments_today()
    log.info(f"[FB-COMMENTS] Done — {commented} this run | Today total: {total}/{DAILY_LIMIT}")

    if commented > 0:
        fb_alerts.alert(
            f"FB Comments — {commented} posted",
            f"Niche: {niche} | Total today: {total}",
            level="ok",
        )
    elif remaining > 0:
        fb_alerts.alert(
            "FB Comments — 0 posted",
            f"No posts found or all failed. Niche: {niche}. Check FB groups (--join first).",
            level="warn",
        )

    return commented
