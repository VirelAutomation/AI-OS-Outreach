"""
services/rating.py

The campaign rating engine. Given raw event counts, produces a 0-100
score across four axes, a letter grade, a human-readable diagnosis,
and a concrete recommended action.

The formula is intentionally weighted toward reply rate (40 pts) and
conversion rate (35 pts) because those are the signal-bearing metrics —
a high-volume, low-reply campaign is failing at the message level, which
is a different root cause than a high-reply, low-conversion campaign,
which is failing at the call-booking or offer level.
"""

from models.outreach import CampaignRatingOut, RatingBreakdown


DIAGNOSES = {
    "Reply Rate": (
        "Reply rate is the weakest axis. This is almost always a messaging problem — "
        "either the subject line is not opening, the opener is too generic, or the "
        "pain framing does not resonate with this segment. Pause, audit the last 10 "
        "sent drafts, and identify the most common structural flaw."
    ),
    "Conversion Rate": (
        "Conversion rate is the weakest axis. Replies are coming in but not converting "
        "to meetings. The offer or the CTA is the bottleneck — either the ask is too "
        "large for a cold email, the value proposition is unclear, or the response "
        "handling is slow. Tighten the CTA to one specific ask and respond to every "
        "reply within 2 hours."
    ),
    "Volume Completion": (
        "Volume completion is the weakest axis. Not enough emails are being sent relative "
        "to the lead pool. This is an execution problem, not a messaging problem. Check "
        "the sending schedule and identify what is blocking batch completion."
    ),
    "Deliverability": (
        "Deliverability is the weakest axis. A high bounce rate signals list quality "
        "issues — the emails themselves may not be reaching inboxes. Verify email "
        "addresses before the next batch and check your sending domain's SPF/DKIM records."
    ),
}

ACTIONS = {
    "Reply Rate": "Rewrite subject lines and openers for the bottom 50% of sent drafts. A/B test two angles.",
    "Conversion Rate": "Simplify CTA to a single calendar link. Add a one-line social proof sentence before the ask.",
    "Volume Completion": "Review the sending schedule. If behind, send a larger batch today to catch up.",
    "Deliverability": "Run the lead list through an email verification service before the next batch.",
}


def compute_rating(
    sent: int,
    replied: int,
    meetings: int,
    bounced: int,
    total_leads: int,
) -> CampaignRatingOut:
    # Guard against division by zero for campaigns that have not sent yet
    safe_sent = sent or 1
    safe_replied = replied or 1
    safe_leads = total_leads or 1

    reply_rate       = replied  / safe_sent
    conversion_rate  = meetings / safe_replied
    volume_completion = min(sent / safe_leads, 1.0)
    deliverability   = max(1 - (bounced / safe_sent), 0.0) if sent > 0 else 1.0

    reply_pts      = reply_rate       * 40
    conversion_pts = conversion_rate  * 35
    volume_pts     = volume_completion * 15
    delivery_pts   = deliverability   * 10
    total          = reply_pts + conversion_pts + volume_pts + delivery_pts

    grade = (
        "S" if total >= 90 else
        "A" if total >= 75 else
        "B" if total >= 60 else
        "C" if total >= 40 else
        "F"
    )

    # Identify the axis performing worst relative to its maximum
    axes = {
        "Reply Rate":        reply_pts      / 40,
        "Conversion Rate":   conversion_pts / 35,
        "Volume Completion": volume_pts     / 15,
        "Deliverability":    delivery_pts   / 10,
    }
    weakest = min(axes, key=axes.get)

    return CampaignRatingOut(
        campaign_id=0,      # caller fills this in
        name="",            # caller fills this in
        total=round(total, 1),
        grade=grade,
        breakdown={
            "reply_rate":        RatingBreakdown(value=round(reply_rate * 100, 1),        points=round(reply_pts, 1),      max=40),
            "conversion_rate":   RatingBreakdown(value=round(conversion_rate * 100, 1),   points=round(conversion_pts, 1), max=35),
            "volume_completion": RatingBreakdown(value=round(volume_completion * 100, 1), points=round(volume_pts, 1),     max=15),
            "deliverability":    RatingBreakdown(value=round(deliverability * 100, 1),    points=round(delivery_pts, 1),   max=10),
        },
        weakest_axis=weakest,
        diagnosis=DIAGNOSES[weakest],
        recommended_action=ACTIONS[weakest],
        raw={"sent": sent, "replied": replied, "meetings": meetings, "bounced": bounced, "leads": total_leads},
    )
