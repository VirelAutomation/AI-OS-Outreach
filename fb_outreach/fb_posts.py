"""Rotating post templates per niche. Plain ASCII only."""
import random, re

HVAC_POSTS = [
    (
        "Quick question for HVAC business owners - how are you handling missed calls after hours?\n\n"
        "I built an AI employee that answers every call 24/7, books the job directly in your calendar "
        "and follows up with estimates automatically. No more lost leads at night or on weekends.\n\n"
        "Happy to show you how it works, just drop a comment or DM me."
    ),
    (
        "HVAC owners - if a potential customer calls at 9pm and no one answers, "
        "they're calling your competitor next.\n\n"
        "I built an AI system that answers those calls, qualifies the lead and books them straight "
        "into your schedule. Works 24/7, costs less than one lost job a month.\n\n"
        "Anyone want to see a quick demo?"
    ),
    (
        "Built something I think HVAC contractors will find useful.\n\n"
        "It's an AI that handles your inbound calls and messages, books appointments and sends "
        "follow-up texts automatically. One of our clients went from missing 40% of after-hours "
        "calls to booking every single one.\n\n"
        "DM me if you want to see the numbers."
    ),
]

MEDSPA_POSTS = [
    (
        "Med spa owners - how much revenue are you losing to missed calls and slow follow-up?\n\n"
        "I built an AI employee that answers every call, books appointments directly in your "
        "calendar and follows up with new clients automatically 24/7.\n\n"
        "It also handles consultation requests while you're with patients. "
        "Drop a comment if you want to see it."
    ),
    (
        "Quick one for aesthetic clinic and med spa owners.\n\n"
        "I built an AI system that picks up every call and message, books the appointment "
        "and sends reminders - all automatically. Your staff can focus on patients, "
        "the AI handles the admin.\n\n"
        "Happy to walk anyone through it. Just DM me."
    ),
    (
        "If you run a med spa and you're still doing appointment booking manually, "
        "this might interest you.\n\n"
        "Built an AI employee that handles inbound calls, books consultations and follows "
        "up with leads 24/7. One clinic we worked with tripled their booking rate in 30 days.\n\n"
        "Anyone want a quick look?"
    ),
]

COACH_POSTS = [
    (
        "hey coaches and consultants - quick one\n\n"
        "we built a human sounding AI employee that runs your ads, reaches out to every lead "
        "automatically and books them directly in your calendar. calls, DMs, follow ups - all handled 24/7.\n\n"
        "you just show up to the calls. drop a comment or DM me if you want to see it"
    ),
    (
        "coaches - what if you never had to chase a lead again?\n\n"
        "we built an AI employee that sounds human, gets you leads through ads, "
        "reaches out to all of them automatically and books the calls straight into your calendar. "
        "works around the clock so you never miss one.\n\n"
        "happy to show you how it works. just DM me"
    ),
    (
        "for any coaches or consultants in here\n\n"
        "we built a human sounding AI employee that handles your entire client pipeline - "
        "runs ads to get leads, reaches out to every single one and books them directly in your calendar. "
        "24/7, no manual work.\n\n"
        "if you want to see a quick demo just comment below or DM me"
    ),
    (
        "coaches and consultants - genuine question\n\n"
        "how much time are you losing every week reaching out to leads and trying to book calls?\n\n"
        "we built an AI employee that does all of that automatically. sounds human, "
        "runs your ads, contacts your leads and books them straight in your calendar. day and night.\n\n"
        "DM me if you want to see it working"
    ),
    (
        "if you're a coach or consultant scaling your business this might be for you\n\n"
        "we built a human sounding AI employee - it gets leads through ads, "
        "reaches out to all of them and books discovery calls directly in your calendar. "
        "handles calls and messages 24/7 so nothing falls through the cracks.\n\n"
        "drop a comment or DM me to see it"
    ),
]

BUSINESS_OWNER_POSTS = [
    (
        "business owners - quick one\n\n"
        "we built a human sounding AI employee that runs your ads, reaches out to every lead "
        "automatically and books them directly in your calendar. calls, DMs, follow ups - all handled 24/7.\n\n"
        "you just show up to the calls. DM me or drop a comment if you want to see it"
    ),
    (
        "for any business owners in here\n\n"
        "we built a human sounding AI employee that gets you leads through ads, "
        "contacts every single lead automatically and books calls straight into your calendar. "
        "works around the clock so you never miss one.\n\n"
        "happy to show you how it works - just DM me"
    ),
    (
        "if you run a business and you're still chasing leads manually, this is for you\n\n"
        "we built an AI employee that sounds human, runs your ads to get leads, "
        "reaches out to all of them and books them directly in your calendar. 24/7, no manual work.\n\n"
        "drop a comment or DM me if you want a quick demo"
    ),
    (
        "business owners - how much time are you losing every week on lead follow up?\n\n"
        "we built a human sounding AI employee that handles your entire pipeline. "
        "gets leads through ads, reaches out to every one of them and books calls straight in your calendar. "
        "day and night.\n\n"
        "DM me if you want to see it working"
    ),
    (
        "genuine question for business owners in this group\n\n"
        "what would change in your business if every lead got followed up with instantly, 24/7?\n\n"
        "we built a human sounding AI employee that does exactly that - runs ads, contacts your leads "
        "and books them directly in your calendar automatically.\n\n"
        "comment below or DM me to see it"
    ),
]

NICHE_POSTS = {
    "hvac":            HVAC_POSTS,
    "med spa":         MEDSPA_POSTS,
    "med_spa":         MEDSPA_POSTS,
    "coach":           COACH_POSTS,
    "consultant":      COACH_POSTS,
    "business_owner":  BUSINESS_OWNER_POSTS,
    "business owner":  BUSINESS_OWNER_POSTS,
}

# Minimum member counts per niche and region
# UK groups need higher thresholds — smaller country, concentrate on high-quality groups
MIN_GROUP_MEMBERS = {
    "business_owner": 30_000,
    "coach":           5_000,
    "hvac":            1_000,
    "med spa":         2_000,
    # UK-specific overrides (keyed "uk_<niche>")
    "uk_business_owner": 5_000,
    "uk_coach":          3_000,
    "uk_hvac":           500,
    "uk_med spa":        1_000,
    # Australia/West — relaxed (smaller market)
    "au_business_owner": 3_000,
    "au_coach":          1_000,
    "au_hvac":           300,
}


def get_min_members(niche: str, country: str = "us") -> int:
    key = f"{country}_{niche}".lower()
    if key in MIN_GROUP_MEMBERS:
        return MIN_GROUP_MEMBERS[key]
    return MIN_GROUP_MEMBERS.get(niche.lower(), 500)


def parse_member_count(text: str) -> int:
    """Extract member count from page text. Returns 0 if not found."""
    m = re.search(r'([\d,\.]+)\s*([KkMm])?\s*[Mm]ember', text)
    if not m:
        return 0
    raw    = float(m.group(1).replace(',', ''))
    suffix = (m.group(2) or '').lower()
    if suffix == 'k':
        raw *= 1_000
    elif suffix == 'm':
        raw *= 1_000_000
    return int(raw)


GROUP_SEARCH_TERMS = {
    # ── US groups ─────────────────────────────────────────────────────────────
    "hvac": [
        "HVAC contractors", "HVAC business owners", "HVAC technicians",
        "heating cooling contractors", "HVAC professionals",
        "air conditioning business", "HVAC service company",
        "HVAC contractors USA", "HVAC business USA",
    ],
    "med spa": [
        "med spa owners", "medical spa business", "aesthetic clinic owners",
        "medspa business", "cosmetic clinic owners",
        "botox business owners", "aesthetic professionals",
        "med spa USA", "aesthetic clinic USA",
    ],
    "coach": [
        "coaches and consultants USA",
        "business coaches USA",
        "online coaches entrepreneurs",
        "life coaches USA",
        "coaching business owners USA",
        "consultants entrepreneurs USA",
        "online coaching business owners",
        "executive coaches USA",
        "coaches scaling business",
        "consultant community USA",
    ],
    "business_owner": [
        "business owners USA",
        "entrepreneurs USA",
        "small business owners USA",
        "business networking USA",
        "CEO entrepreneurs USA",
        "online business owners USA",
        "entrepreneurs network USA",
        "business owners community",
        "startup founders USA",
        "business growth USA",
    ],

    # ── Australia groups ──────────────────────────────────────────────────────
    "au_business_owner": [
        "business owners Australia",
        "entrepreneurs Australia",
        "small business Australia",
        "business networking Australia",
        "Australian entrepreneurs",
        "startup founders Australia",
        "Australian business community",
    ],
    "au_coach": [
        "coaches Australia",
        "business coaches Australia",
        "consultants Australia",
        "life coaches Australia",
        "coaching business Australia",
    ],
    "au_hvac": [
        "HVAC Australia",
        "air conditioning Australia",
        "HVAC contractors Australia",
        "heating cooling Australia",
    ],

    # ── UK groups (higher member threshold applies) ───────────────────────────
    "uk_business_owner": [
        "business owners UK",
        "entrepreneurs UK",
        "small business UK",
        "UK business networking",
        "British entrepreneurs",
        "startup founders UK",
        "UK business owners community",
    ],
    "uk_coach": [
        "coaches UK",
        "business coaches UK",
        "life coaches UK",
        "consultants UK",
        "coaching business UK",
        "coaches and consultants UK",
    ],
    "uk_hvac": [
        "HVAC UK",
        "heating engineers UK",
        "plumbing heating UK",
        "HVAC contractors UK",
        "gas engineers UK",
    ],

    # ── India groups ──────────────────────────────────────────────────────────
    "india_business_owner": [
        "business owners India",
        "entrepreneurs India",
        "Indian entrepreneurs",
        "Indian business owners",
        "startup founders India",
        "India business networking",
        "MSME India",
        "Indian SME owners",
    ],
    "india_digital_marketing": [
        "digital marketing India",
        "digital marketing agencies India",
        "marketing professionals India",
        "SEO professionals India",
        "social media marketing India",
    ],
}


def get_post(niche: str) -> str:
    key = niche.lower()
    posts = NICHE_POSTS.get(key) or NICHE_POSTS.get(key.replace("_", " ")) or COACH_POSTS
    return random.choice(posts)
