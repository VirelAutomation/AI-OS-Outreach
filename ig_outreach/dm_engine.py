"""
DM templates per niche and region. No Gemini needed.
All text is plain ASCII to avoid encoding issues on any platform.
"""

# ── India DMs ─────────────────────────────────────────────────────────────────

_INDIA_REALTOR = (
    "hey I built an AI employee that reaches out to all your leads automatically "
    "and generates new ones for you 24/7. want me to show you how it works for real estate?"
)

_INDIA_MARKETING = (
    "hey I help digital marketing agencies get a lot more revenue and build a fully automated sales pipeline "
    "that captures leads, follows up and books calls on its own 24/7. no manual chasing. "
    "interested in seeing how it works?"
)

_INDIA_INTERIOR = (
    "hey I built an AI employee that reaches out to potential clients for you automatically "
    "and generates leads 24/7. want me to show you what it looks like for interior design?"
)

# ── US / Canada DMs ───────────────────────────────────────────────────────────

_US_REALTOR = (
    "hey I built an AI employee that reaches out to all your leads automatically "
    "and generates new ones 24/7 so you never miss a hot lead. interested in checking it out?"
)

_US_MARKETING = (
    "hey I built an AI employee that does your outreach automatically, "
    "reaches out to leads, follows up and books calls 24/7. want to see it?"
)

_US_HVAC = (
    "hey we built an AI employee for HVAC businesses that makes sure you never miss a lead — "
    "answers every call and inquiry 24/7, books jobs straight in your calendar automatically. "
    "want to see it?"
)

_US_MEDSPA = (
    "hey we built an AI employee for med spas that makes sure you never miss a booking — "
    "answers every call and inquiry 24/7 and books appointments straight in your calendar. "
    "want to see how it works?"
)

_US_INTERIOR = (
    "hey I built an AI employee that reaches out to potential clients for you automatically "
    "and books consultations 24/7. interested in checking it out?"
)

_US_COACH = (
    "hey we built a system for coaches that helps you get more leads and fully automates "
    "how you convert and manage them — follows up 24/7, books calls on its own, zero manual work. "
    "want to see it?"
)

_US_COACH_PERSONALIZED = (
    "hey saw you have {follower_str} followers — we built a system that helps you get more leads "
    "and fully automates how you convert and manage them, follows up 24/7 and books calls on its own. "
    "want to see it?"
)

_US_CONSULTANT = (
    "hey we built a system for consultants that captures every lead, reaches out automatically "
    "and books them straight in your calendar. calls and messages handled 24/7, zero manual work. "
    "want to see how it works?"
)

_NO_WEBSITE_ADD = (
    " also noticed you dont have a website yet, "
    "I can build one that actually brings in leads too"
)

# ── Follow-ups ────────────────────────────────────────────────────────────────

FOLLOWUP_1 = (
    "hey just checking in, did you get a chance to see my last message? "
    "still happy to walk you through the AI system real quick"
)

FOLLOWUP_2 = (
    "last one from me, if the timing isnt right no worries. "
    "just let me know whenever you want to see how it works?"
)

# ── Lookup maps ───────────────────────────────────────────────────────────────

_INDIA_MAP = {
    "real estate":              _INDIA_REALTOR,
    "realtor":                  _INDIA_REALTOR,
    "digital marketing agency": _INDIA_MARKETING,
    "interior designer":        _INDIA_INTERIOR,
}

_US_MAP = {
    "hvac":                     _US_HVAC,
    "med spa":                  _US_MEDSPA,
    "medspa":                   _US_MEDSPA,
    "coach":                    _US_COACH,
    "consultant":               _US_CONSULTANT,
    "interior designer":        _US_INTERIOR,
}


def _format_followers(n: int) -> str:
    if n >= 10_000:
        return f"{n // 1000}k"
    if n >= 1_000:
        return f"{n / 1000:.1f}k"
    return str(n)


def generate_dm(_client, username: str, business_type: str,
                bio: str, has_website: bool, region: str = "us",
                followers: int = 0) -> str:
    biz    = (business_type or "").lower()
    lookup = _INDIA_MAP if region == "india" else _US_MAP

    message = None
    for key, template in lookup.items():
        if key in biz:
            # Personalized coach DM if follower count is available
            if key == "coach" and followers > 0:
                message = _US_COACH_PERSONALIZED.format(
                    follower_str=_format_followers(followers)
                )
            else:
                message = template
            break

    if message is None:
        message = _INDIA_MARKETING if region == "india" else _US_MEDSPA

    if not has_website and region == "india":
        message = message.rstrip("?") + "." + _NO_WEBSITE_ADD + "?"

    return message
