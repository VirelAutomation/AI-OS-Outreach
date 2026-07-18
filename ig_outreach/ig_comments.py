"""
Instagram Comment Engine.

Strategy:
  1. Find posts via coaching/consulting hashtags
  2. Generate a genuine contextual comment (Claude if available, templates fallback)
  3. Like the post + comment
  4. Track everything — daily limit, no duplicates
  5. Comments draw the poster back to our profile → organic leads

Why comments > DMs alone:
  - Public visibility (others see the comment too)
  - Less intrusive — feels organic
  - Builds presence in the coaching community
  - Poster gets notified, checks your profile, may DM back

Daily safe limit: 20-30 comments (IG is more lenient than DMs here)
"""

import os, random, time, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import ig_client
import db
import ig_alerts

log  = logging.getLogger("virel.ig.comments")
_IST = timezone(timedelta(hours=5, minutes=30))

DAILY_LIMIT = int(os.getenv("INSTAGRAM_DAILY_COMMENT_LIMIT", "40"))

# ── Hashtags — Western (US / AU / CA) ────────────────────────────────────────

COMMENT_HASHTAGS_WESTERN = {
    "coach": [
        "businesscoach", "lifecoach", "executivecoach", "onlinecoach",
        "coachpreneur", "businesscoaching", "coachlife", "certifiedcoach",
        "mindsetcoach", "successcoach", "entrepreneurcoach", "coachesofinstagram",
        "businesscoachtips", "lifecoaching", "leadershipcoach",
    ],
    "consultant": [
        "businessconsultant", "marketingconsultant", "consultant",
        "businessconsulting", "consultantlife", "businessadvisor",
        "growthadvisor", "businessgrowth", "smallbusinessowner",
    ],
    "hvac": [
        "hvaccontractor", "hvaclife", "hvacbusiness", "hvactechnician",
        "airconditioning", "heatingandcooling", "hvacpro", "hvactech",
        "hvacowner", "hvaccompany",
    ],
    "med_spa": [
        "medspa", "medspabusiness", "aestheticpractice", "medicalesthetics",
        "aestheticclinic", "botoxbusiness", "aestheticnurse", "injector",
        "medspamktg", "aestheticclinicowner",
    ],
    "entrepreneur": [
        "entrepreneurmindset", "entrepreneurlife", "onlinebusiness",
        "businessowner", "digitalentrepreneur", "buildyourbusiness",
    ],
}

# ── Hashtags — India ─────────────────────────────────────────────────────────

COMMENT_HASHTAGS_INDIA = {
    "digital_marketing_agency": [
        "digitalmarketingagencyindia", "digitalmarketingindia",
        "digitalmarketingindelhi", "digitalmarketinginmumbai",
        "marketingagencyindia", "digitalagencyindia", "seoagencyindia",
        "socialmediamarketingindia", "contentmarketingindia",
        "performancemarketingindia", "growthmarketingindia",
        "googleadsagencyindia", "facebookadsagencyindia",
        "agencyowner", "digitalmarketingexpert",
    ],
    "business_owner": [
        "indianentrepreneur", "indianbusiness", "indianstartup",
        "startupindia", "businessownerindia", "msme",
        "entrepreneurindia", "smallbusiness", "businesstips",
    ],
}

# ── Backwards-compatible alias ────────────────────────────────────────────────
COMMENT_HASHTAGS = COMMENT_HASHTAGS_WESTERN  # used by legacy code

# ── Comment templates (fallback when no Claude) ───────────────────────────────

_TEMPLATES = {
    "agreement": [
        "This is exactly right. So many people skip this step.",
        "100%. The ones who get this early win.",
        "Facts. Wish I'd understood this sooner.",
        "This hits different. Needed to read this today.",
        "Couldn't agree more. This is what separates good from great.",
    ],
    "value": [
        "This is genuinely one of the most useful things I've seen on here.",
        "Solid advice. Saving this one.",
        "More coaches need to be saying this.",
        "This is the kind of content that actually moves the needle.",
        "Real value right here. Thank you for posting this.",
    ],
    "question": [
        "How long did it take you to figure this out?",
        "Do you find this works better with new clients or existing ones?",
        "Have you seen this work across different niches too?",
        "What's been the biggest shift for you since applying this?",
        "Is this something you teach in your program?",
    ],
    "short": [
        "Love this perspective 🙌",
        "This is gold.",
        "Needed this today.",
        "Such a good point.",
        "Saving this 🔥",
        "Real talk.",
        "This is it.",
        "Underrated advice right here.",
    ],
}

ALL_TEMPLATES = (
    _TEMPLATES["agreement"] * 2 +
    _TEMPLATES["value"] * 2 +
    _TEMPLATES["question"] +
    _TEMPLATES["short"] * 3
)


# ── Comment generation ────────────────────────────────────────────────────────

def _generate_comment(caption: str, username: str) -> str:
    """
    Generate a relevant comment for a post.
    Uses Gemini if available, otherwise picks the best template.
    """
    api_key = os.getenv("GEMINI_API_KEY_NOAH") or os.getenv("GEMINI_API_KEY", "")
    if api_key and caption and len(caption) > 30:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model  = genai.GenerativeModel("gemini-2.5-flash")
            r = model.generate_content(
                f"Write a genuine 1-sentence Instagram comment on this coaching post. "
                f"Sound like a peer in the coaching space, not a fan. "
                f"No emojis unless it feels natural. No self-promotion. "
                f"Post caption (first 200 chars): {caption[:200]}\n"
                f"Comment (max 15 words, no quotes):"
            )
            comment = r.text.strip().strip('"').strip("'")
            if comment and 5 < len(comment) < 200:
                return comment
        except Exception:
            pass

    # Template fallback — pick randomly but prefer agreement/value
    return random.choice(ALL_TEMPLATES)


# ── Main comment engine ───────────────────────────────────────────────────────

def run_comments(cl, niche: str = "coach", daily_limit: int = DAILY_LIMIT,
                 region: str = "auto") -> int:
    """
    Find posts from target hashtags and comment on them.
    region: 'india' uses India DMA hashtags, 'us'/'auto' uses Western hashtags.
    Returns number of comments posted.
    """
    already   = db.get_comments_today()
    remaining = daily_limit - already

    if remaining <= 0:
        log.info(f"[COMMENTS] Daily limit {daily_limit} reached ({already} done).")
        return 0

    log.info(f"[COMMENTS] Starting — {already} done today, {remaining} remaining | region={region} niche={niche}")

    # Pick hashtag pool based on region + niche
    if region == "india":
        pool = COMMENT_HASHTAGS_INDIA.get(niche, COMMENT_HASHTAGS_INDIA.get("digital_marketing_agency", []))
        if not pool:
            pool = COMMENT_HASHTAGS_INDIA["digital_marketing_agency"]
    else:
        pool = COMMENT_HASHTAGS_WESTERN.get(niche, COMMENT_HASHTAGS_WESTERN["coach"])

    hashtags = pool.copy()
    random.shuffle(hashtags)

    commented = 0
    seen_media = set()
    seen_users = set()

    # Build search keywords from hashtag pool (strip tag-style words to human phrases)
    _keyword_map = {
        "coach": ["business coach", "life coach", "online coach", "executive coach",
                  "coaching business", "mindset coach"],
        "consultant": ["business consultant", "marketing consultant", "strategy consultant",
                       "online consultant", "consulting business"],
        "hvac": ["hvac contractor", "hvac business", "hvac company", "hvac owner"],
        "med_spa": ["med spa", "aesthetic clinic", "medspa business", "botox clinic"],
        "entrepreneur": ["entrepreneur", "online business", "business owner"],
        "digital_marketing_agency": ["digital marketing agency india", "marketing agency",
                                     "digital agency india", "seo agency india"],
        "business_owner": ["indian entrepreneur", "indian business", "startup india"],
    }
    keywords = _keyword_map.get(niche, [niche])
    random.shuffle(keywords)

    for keyword in keywords:
        if commented >= remaining:
            break

        log.info(f"[SEARCH] '{keyword}'")
        try:
            user_results = cl.search_users(keyword)
        except Exception as e:
            log.warning(f"  search_users failed ('{keyword}'): {e}")
            time.sleep(random.uniform(5, 10))
            continue

        time.sleep(random.uniform(2, 4))

        if not user_results:
            log.info(f"  No users for '{keyword}'")
            continue

        log.info(f"  Found {len(user_results)} users")

        for user_obj in user_results[:12]:
            if commented >= remaining:
                break

            try:
                uid = str(user_obj.pk)
                uname = str(user_obj.username)
            except Exception:
                continue

            if uid in seen_users:
                continue
            if uname in ("virel.automation", "virel_automation"):
                continue
            seen_users.add(uid)

            posts = ig_client.get_user_recent_posts(cl, uid, amount=3)
            if not posts:
                continue

            for post in posts:
                if commented >= remaining:
                    break

                try:
                    media_id  = str(post.pk)
                    caption   = getattr(post, "caption_text", "") or ""
                    media_url = f"https://www.instagram.com/p/{getattr(post, 'code', '')}/"
                except Exception:
                    continue

                if media_id in seen_media or db.has_commented(media_id):
                    continue
                if not caption.strip():
                    continue

                seen_media.add(media_id)

                comment = _generate_comment(caption, uname)
                log.info(f"  [@{uname}] Commenting: {comment[:60]}...")

                ig_client.like_media(cl, media_id)
                time.sleep(random.uniform(1, 2))

                ok = ig_client.post_comment(cl, media_id, comment)

                if ok:
                    db.log_comment(
                        media_id=media_id,
                        username=uname,
                        comment_text=comment,
                        hashtag=keyword,
                        user_id=uid,
                        media_url=media_url,
                        caption_peek=caption[:200],
                    )
                    commented += 1
                    log.info(f"  [DONE #{commented}] @{uname} | '{keyword}'")

                    gap = random.randint(120, 300)
                    log.info(f"  Waiting {gap//60}m {gap%60}s...")
                    time.sleep(gap)
                else:
                    log.warning(f"  [FAIL] @{uname}")
                    time.sleep(random.uniform(15, 30))

        time.sleep(random.uniform(5, 10))

    total = db.get_comments_today()
    log.info(f"[COMMENTS] Done — {commented} posted | Today total: {total}/{daily_limit}")

    if commented > 0:
        ig_alerts.alert(
            f"IG Comments — {commented} posted",
            f"Hashtags: {', '.join(['#' + h for h in hashtags[:3]])}... | Total today: {total}",
            level="ok",
        )

    return commented


def comment_on_user_posts(cl, username: str, amount: int = 3) -> int:
    """
    Comment on a specific user's recent posts.
    Use this to engage with a specific lead's content before DMing.
    """
    log.info(f"[COMMENTS] Engaging with @{username}'s posts...")

    try:
        user_info = ig_client.get_user_info(cl, username)
        if not user_info:
            log.warning(f"  Could not find @{username}")
            return 0
        user_id = str(user_info.pk)
    except Exception as e:
        log.warning(f"  Error finding @{username}: {e}")
        return 0

    posts = ig_client.get_user_recent_posts(cl, user_id, amount=amount)
    if not posts:
        log.info(f"  No posts found for @{username}")
        return 0

    commented = 0
    for post in posts:
        try:
            media_id = str(post.pk)
            caption  = getattr(post, "caption_text", "") or ""
        except Exception:
            continue

        if db.has_commented(media_id):
            continue

        comment = _generate_comment(caption, username)
        ig_client.like_media(cl, media_id)
        time.sleep(random.uniform(2, 4))

        if ig_client.post_comment(cl, media_id, comment):
            db.log_comment(
                media_id=media_id, username=username,
                comment_text=comment, hashtag="direct_engage",
                user_id=user_id, caption_peek=caption[:200],
            )
            commented += 1
            log.info(f"  Commented on @{username} post: {comment[:50]}")
            time.sleep(random.uniform(30, 60))

    return commented
