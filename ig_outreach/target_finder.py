import json
import random
from google import genai

SEED_HASHTAGS_INDIA: dict[str, list[str]] = {
    "real estate": [
        "indianrealtor", "realtorsindia", "delhirealtor", "mumbairealtor",
        "bangalorerealtor", "realestateagentindia", "propertiesinindia",
        "hyderabadrealtor", "punerealtor", "realestateindia",
        "propertyinindia", "noidaproperties", "gurugram",
    ],
    "digital marketing agency": [
        "digitalmarketingindia", "digitalmarketingindelhi", "digitalmarketinginmumbai",
        "socialmediamarketingindia", "marketingagencyindia", "digitalagencyindia",
        "seoexpertindia", "contentmarketingindia", "instagrammarketingindia",
        "digitalmarketingbangalore", "marketingagencymumbai",
    ],
    "interior designer": [
        "interiordesignerindia", "interiordesigndelhi", "mumbaiinteriors",
        "bangaloreinteriordesign", "interiordesignhyderabad", "delhiinteriors",
        "indiainteriordesign", "interiordesignermumbai", "interiordesignerpune",
        "luxuryinteriorsIndia", "homedesignindia",
    ],
}

SEED_HASHTAGS_US: dict[str, list[str]] = {
    "real estate": [
        "realtor", "realtorlife", "realestateagent", "realtorsofinstagram",
        "homeforsale", "realestateteam", "realestatebroker",
        "househunting", "realtormarketing", "newlisting", "luxuryrealtor",
        "realtorsofamerica", "floridarealestate", "texasrealtor", "californiahomes",
    ],
    "digital marketing agency": [
        "digitalmarketingagency", "marketingagency", "socialmediamarketing",
        "digitalmarketingexpert", "marketingconsultant", "smallbusinessmarketing",
        "agencyowner", "marketingagencyowner", "growyourbusiness",
        "digitalagencyusa", "marketingusa",
    ],
    "interior designer": [
        "interiordesigner", "interiordesign", "interiordecorator",
        "homedesign", "interiorstylist", "designstudio", "homedecor",
        "interiordesignerlife", "luxuryinteriors", "interiordesignstudio",
        "nycinteriordesign", "lainteriordesign", "chicagointeriors",
    ],
}

# India: marketing agencies first (15), then realtors (5)
SEARCH_KEYWORDS_INDIA = [
    "digital marketing agency india", "social media agency india",
    "marketing agency delhi", "marketing agency mumbai", "digital agency india",
    "seo agency india", "performance marketing india",
    "social media marketing india", "digital marketing services india",
    "content marketing india", "marketing agency bangalore",
    "marketing agency pune", "digital agency mumbai",
    "property consultant delhi", "property consultant mumbai",
    "property consultant pune", "flat agent mumbai",
    "real estate consultant india",
    "interior designer india", "interior design delhi",
]

# US/Canada: HVAC + Med Spas + Coaches (no realtors, no agencies)
SEARCH_KEYWORDS_US = [
    # HVAC
    "hvac contractor", "hvac company", "air conditioning company",
    "heating cooling contractor", "hvac technician",
    # Med Spas
    "med spa", "medical spa", "medspa",
    "aesthetic clinic", "botox clinic", "skin care clinic",
    "laser clinic", "cosmetic clinic", "aesthetics",
    # Coaches
    "life coach", "business coach", "executive coach",
    "health coach", "fitness coach", "mindset coach",
    "success coach", "online coach", "coaching business",
]

# US coaches and consultants only
SEARCH_KEYWORDS_US_COACH = [
    "business coach", "life coach", "executive coach",
    "online coach", "mindset coach", "success coach",
    "health coach", "fitness coach", "coaching business",
    "business consultant", "marketing consultant",
    "strategy consultant", "consultant usa",
    "online consultant", "business consultant usa",
    "coaches and consultants", "coach entrepreneur",
    "consulting business", "certified coach",
]


# Niche-specific pools for precise targeting
SEARCH_KEYWORDS_INDIA_DMA = [
    "digital marketing agency india", "social media agency india",
    "marketing agency delhi", "marketing agency mumbai", "marketing agency bangalore",
    "digital agency india", "seo agency india", "performance marketing india",
    "social media marketing india", "digital marketing services india",
    "content marketing india", "marketing agency pune", "digital agency mumbai",
    "digital marketing agency hyderabad", "inbound marketing india",
    "ppc agency india", "google ads agency india", "facebook ads agency india",
    "growth marketing india", "lead generation agency india",
]

SEARCH_KEYWORDS_US_HVAC = [
    "hvac contractor", "hvac company", "air conditioning company",
    "heating cooling contractor", "hvac technician", "hvac service",
    "ac repair business", "furnace company", "hvac installer",
    "mechanical contractor", "hvac business owner",
]

SEARCH_KEYWORDS_US_MEDSPA = [
    "med spa", "medical spa", "medspa", "aesthetic clinic",
    "botox clinic", "skin care clinic", "laser clinic",
    "cosmetic clinic", "aesthetics business", "aesthetic nurse",
    "injector", "beauty clinic", "wellness clinic",
]


def get_search_keywords(region: str, niche: str = None) -> list[str]:
    if niche == "coach" or niche == "consultant":
        return list(SEARCH_KEYWORDS_US_COACH)
    if niche == "digital_marketing_agency":
        return list(SEARCH_KEYWORDS_INDIA_DMA) if region == "india" else [
            "digital marketing agency", "marketing agency", "social media agency",
            "digital agency", "seo agency", "content marketing agency",
            "growth marketing agency", "performance marketing agency",
        ]
    if niche == "hvac":
        return list(SEARCH_KEYWORDS_US_HVAC)
    if niche == "med_spa":
        return list(SEARCH_KEYWORDS_US_MEDSPA)
    pool = SEARCH_KEYWORDS_INDIA if region == "india" else SEARCH_KEYWORDS_US
    return list(pool)


def _call(client: genai.Client, prompt: str) -> str:
    """Single attempt — caller handles fallback on failure."""
    import os as _os
    _model = _os.getenv("GEMINI_MODEL_DEFAULT", "gemini-2.5-flash")
    resp = client.models.generate_content(model=_model, contents=prompt)
    return resp.text.strip()


def get_keyword_pool(region: str = "us", niche: str = None) -> list[str]:
    return get_search_keywords(region, niche=niche)


_KEYWORD_TARGETS = {
    "real estate":             ["realtor","real estate","property consultant","property agent",
                                "property dealer","home agent","flat agent","estate agent",
                                "realty","homes for sale","property dealer"],
    "digital marketing agency":["digital marketing","marketing agency","social media agency",
                                 "seo agency","digital agency","ppc","ads manager",
                                 "content marketing","growth agency","performance marketing"],
    "interior designer":       ["interior designer","interior design","home interior",
                                 "interior decorator","home decor","space designer"],
    "hvac":                    ["hvac","air conditioning","heating cooling","ac repair",
                                 "furnace","heat pump","ductwork","ventilation"],
    "med spa":                 ["med spa","medspa","medical spa","botox","filler","aesthetic",
                                 "laser","skin care clinic","cosmetic","injectables"],
    "coach":                   ["life coach","business coach","executive coach","health coach",
                                 "fitness coach","mindset coach","success coach","online coach",
                                 "coaching","certified coach","personal development"],
    "consultant":              ["consultant","consulting","business consultant","marketing consultant",
                                 "strategy consultant","management consultant","advisor",
                                 "fractional","growth consultant"],
}

def _keyword_validate(username: str, full_name: str, bio: str) -> dict:
    """Fast local check — no Gemini needed. Checks bio+name for target keywords."""
    text = f"{username} {full_name} {bio}".lower()
    for biz_type, keywords in _KEYWORD_TARGETS.items():
        if any(kw in text for kw in keywords):
            return {"is_valid": True, "business_type": biz_type, "confidence": 75,
                    "reason": "keyword match (Gemini offline)"}
    return {"is_valid": False, "business_type": None, "confidence": 0, "reason": "no keyword match"}


def validate_account(client: genai.Client, username: str, full_name: str,
                     bio: str, followers: int, following: int,
                     is_business: bool, has_website: bool,
                     niche: str = None) -> dict:
    if niche == "hvac":
        prompt = (
            "Analyze this Instagram account. We ONLY want HVAC contractors, heating/cooling companies, "
            "air conditioning businesses (small-to-medium, not large national brands).\n\n"
            f"Username: {username}\nName: {full_name}\nBio: {bio[:300]}\n"
            f"Followers: {followers}\nFollowing: {following}\n"
            f"Business account: {is_business}\nHas website: {has_website}\n\n"
            'Return ONLY valid JSON:\n{"is_valid": true/false, "business_type": "hvac" or null, '
            '"confidence": 0-100, "reason": "one sentence"}'
        )
        try:
            text = _call(client, prompt).strip("`").lstrip("json").strip()
            return json.loads(text)
        except Exception:
            return _keyword_validate(username, full_name, bio)

    if niche == "med_spa":
        prompt = (
            "Analyze this Instagram account. We ONLY want med spas, medical spas, aesthetic clinics, "
            "botox/filler clinics, cosmetic clinics (small-to-medium businesses).\n\n"
            f"Username: {username}\nName: {full_name}\nBio: {bio[:300]}\n"
            f"Followers: {followers}\nFollowing: {following}\n"
            f"Business account: {is_business}\nHas website: {has_website}\n\n"
            'Return ONLY valid JSON:\n{"is_valid": true/false, "business_type": "med spa" or null, '
            '"confidence": 0-100, "reason": "one sentence"}'
        )
        try:
            text = _call(client, prompt).strip("`").lstrip("json").strip()
            return json.loads(text)
        except Exception:
            return _keyword_validate(username, full_name, bio)

    if niche == "digital_marketing_agency":
        prompt = (
            "Analyze this Instagram account. We ONLY want digital marketing agencies, social media agencies, "
            "SEO agencies, performance marketing agencies (small-to-mid size, not large corporations).\n\n"
            f"Username: {username}\nName: {full_name}\nBio: {bio[:300]}\n"
            f"Followers: {followers}\nFollowing: {following}\n"
            f"Business account: {is_business}\nHas website: {has_website}\n\n"
            'Return ONLY valid JSON:\n{"is_valid": true/false, "business_type": "digital marketing agency" or null, '
            '"confidence": 0-100, "reason": "one sentence"}'
        )
        try:
            text = _call(client, prompt).strip("`").lstrip("json").strip()
            return json.loads(text)
        except Exception:
            return _keyword_validate(username, full_name, bio)

    if niche == "coach":
        prompt = (
            "Analyze this Instagram account. We ONLY want:\n"
            "1. Life coaches / business coaches / executive coaches / mindset coaches\n"
            "2. Consultants (business consultants, marketing consultants, strategy consultants)\n\n"
            f"Username: {username}\nName: {full_name}\nBio: {bio[:300]}\n"
            f"Followers: {followers}\nFollowing: {following}\n"
            f"Business account: {is_business}\nHas website: {has_website}\n\n"
            "MUST EXCLUDE: personal diary accounts, pure influencers, meme pages, "
            "large corporations, unrelated businesses.\n\n"
            "Only mark is_valid=true if confident (70%+) it is a coach or consultant.\n\n"
            'Return ONLY valid JSON:\n{"is_valid": true/false, "business_type": "coach" or "consultant" or null, '
            '"confidence": 0-100, "reason": "one sentence"}'
        )
    else:
        prompt = (
            "Analyze this Instagram account. We ONLY want:\n"
            "1. Real estate agents / realtors (individual agents or small teams)\n"
            "2. Digital marketing agencies (small/boutique, not large corporations)\n"
            "3. Interior designers (individuals or small studios)\n"
            "4. HVAC contractors / heating cooling companies\n"
            "5. Med spas / aesthetic clinics / cosmetic clinics\n"
            "6. Life coaches / business coaches / consultants\n\n"
            f"Username: {username}\nName: {full_name}\nBio: {bio[:300]}\n"
            f"Followers: {followers}\nFollowing: {following}\n"
            f"Business account: {is_business}\nHas website: {has_website}\n\n"
            "MUST EXCLUDE: pure personal accounts, meme pages, fan pages, large national brands.\n\n"
            "Only mark is_valid=true if confident (70%+) it is one of the target types.\n\n"
            'Return ONLY valid JSON:\n{"is_valid": true/false, "business_type": "real estate" or "digital marketing agency" or "interior designer" or "hvac" or "med spa" or "coach" or "consultant" or null, '
            '"confidence": 0-100, "reason": "one sentence"}'
        )
    try:
        text = _call(client, prompt).strip("`").lstrip("json").strip()
        result = json.loads(text)
        return result
    except Exception:
        # Gemini unavailable (rate limit, quota, etc.) — instant keyword fallback
        return _keyword_validate(username, full_name, bio)
