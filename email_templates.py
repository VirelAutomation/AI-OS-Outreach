"""
Virel Automation — Email Campaign Templates

MORNING (10 AM IST):
  India — digital marketing agencies, fintech firms, business owners
  Mention we're from India. Familiar, peer tone.

EVENING (9 PM IST):
  US, Australia, Canada — HVAC firms
  Direct, pain-point focused.
"""

import random

# ── Morning: India ────────────────────────────────────────────────────────────

MORNING_SUBJECTS_INDIA = [
    "More revenue for your agency — fully automated sales pipeline",
    "Quick one for your agency — stronger pipeline, more revenue",
    "How we help agencies in India get a lot more revenue (from India)",
    "Your agency's sales pipeline, fully automated — from an Indian team",
    "Quick one for digital agencies in India",
]

MORNING_BODY_INDIA_DMA = """\
Hey {name},

Jace here — we're Virel Automation, an AI company based in India.

We help digital marketing agencies like yours get a lot more revenue by fully automating \
their sales pipeline — from the first touch all the way to a booked call.

Your pipeline captures leads, follows up with every single one and books discovery calls \
directly in your calendar. 24/7, without anyone on your team lifting a finger.

No more chasing leads. No more lost follow-ups. Your calendar fills itself.

We've been building this for agencies across India and the results are strong. \
Happy to show you it live in 15 minutes — no pitch, just a real demo.

Worth a look?

Jace
Virel Automation
"""

MORNING_BODY_INDIA_FINTECH = """\
Hey {name},

We're Virel Automation — an AI company from India.

We built an AI employee specifically for fintech and financial services companies \
that handles your entire lead outreach automatically:
- Reaches out to potential clients on Instagram, Facebook and email
- Follows up with every lead 24/7
- Books calls directly in your team's calendar

One demo is worth more than an explanation — happy to show you it live in 15 minutes.

Jace
Virel Automation
"""

MORNING_BODY_INDIA_BUSINESS = """\
Hey {name},

We're Virel Automation — we're from India too.

We built an AI employee that handles your entire outreach pipeline automatically:
- Finds and reaches out to potential clients on Instagram, Facebook and email
- Follows up with every single lead 24/7
- Books calls directly in your calendar

No manual work. You just show up to the meetings.

Happy to walk you through it in 15 minutes — just reply and we'll set it up.

Jace
Virel Automation
"""


def get_morning_india(recipient_type: str = "digital_marketing_agency") -> tuple[str, str]:
    """Returns (subject, body) for a morning India email. recipient_type: dma/fintech/business"""
    subject = random.choice(MORNING_SUBJECTS_INDIA)
    if "fintech" in recipient_type or "financial" in recipient_type:
        body = MORNING_BODY_INDIA_FINTECH
    elif "digital" in recipient_type or "agency" in recipient_type or "marketing" in recipient_type:
        body = MORNING_BODY_INDIA_DMA
    else:
        body = MORNING_BODY_INDIA_BUSINESS
    return subject, body


# ── Evening: US / Australia / Canada HVAC ────────────────────────────────────

EVENING_SUBJECTS_HVAC = [
    "Built an AI employee for HVAC businesses — never miss an after-hours call",
    "HVAC owners: AI that answers every call and books the job automatically",
    "Stop losing after-hours leads — built an AI employee for HVAC contractors",
    "We built an AI employee specifically for HVAC businesses",
    "Quick one for HVAC contractors in {region}",
]

EVENING_BODY_HVAC_US = """\
Hey {name},

We built an AI employee for HVAC contractors in the US.

It answers every call and message 24/7, books jobs directly in your calendar \
and follows up with leads automatically. After-hours calls, weekend inquiries — \
all handled without you lifting a finger.

One of our HVAC clients went from missing 40% of after-hours calls to booking \
every single one within the first week.

It costs less than one lost job per month.

Want to see a 15-minute live demo?

Jace
Virel Automation
"""

EVENING_BODY_HVAC_AU = """\
Hey {name},

We built an AI employee for HVAC and air conditioning businesses in Australia.

It answers every call and message 24/7, books jobs directly in your calendar \
and follows up with leads automatically. No more missed calls during busy seasons.

Happy to show you it running live — takes 15 minutes.

Jace
Virel Automation
"""

EVENING_BODY_HVAC_CA = """\
Hey {name},

We built an AI employee for HVAC contractors in Canada.

It handles every inbound call and message 24/7, books jobs straight into your schedule \
and follows up with every lead automatically. Peak season, off hours, weekends — covered.

Want to see a quick demo?

Jace
Virel Automation
"""


def get_evening_hvac(region: str = "us") -> tuple[str, str]:
    """Returns (subject, body) for an evening HVAC email. region: us/au/ca"""
    region_label = {"us": "the US", "au": "Australia", "ca": "Canada"}.get(region, "the US")
    subject = random.choice(EVENING_SUBJECTS_HVAC).replace("{region}", region_label)
    if region == "au":
        body = EVENING_BODY_HVAC_AU
    elif region == "ca":
        body = EVENING_BODY_HVAC_CA
    else:
        body = EVENING_BODY_HVAC_US
    return subject, body


# ── Generic helpers ───────────────────────────────────────────────────────────

def render(template: str, name: str = "there", **kwargs) -> str:
    """Fill {name} and any other placeholders in a template."""
    return template.format(name=name, **kwargs)


# ── Preview ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("MORNING INDIA — Digital Marketing Agency")
    print("=" * 60)
    subj, body = get_morning_india("digital_marketing_agency")
    print(f"Subject: {subj}")
    print(render(body, name="[Recipient Name]"))

    print("=" * 60)
    print("MORNING INDIA — Fintech")
    print("=" * 60)
    subj, body = get_morning_india("fintech")
    print(f"Subject: {subj}")
    print(render(body, name="[Recipient Name]"))

    print("=" * 60)
    print("EVENING US — HVAC")
    print("=" * 60)
    subj, body = get_evening_hvac("us")
    print(f"Subject: {subj}")
    print(render(body, name="[Recipient Name]"))

    print("=" * 60)
    print("EVENING AU — HVAC")
    print("=" * 60)
    subj, body = get_evening_hvac("au")
    print(f"Subject: {subj}")
    print(render(body, name="[Recipient Name]"))
