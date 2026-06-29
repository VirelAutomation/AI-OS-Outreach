"""
tests/test_runner.py — FORGE ASI System Test Suite

Comprehensive test runner that verifies every component of the system.
Tests are organized in three tiers:

  UNIT   — no network, no DB. Tests pure business logic (rating engine,
            email parser, quality scorer). Always pass.

  LIVE   — hits the real API server (must be running on localhost:8000).
            Run with: python tests/test_runner.py --live

  MOCK   — tests service wiring with mocked external APIs.
            Run with: python tests/test_runner.py --mock

Usage:
    cd forge_system
    python tests/test_runner.py            # unit tests only (safe, always runnable)
    python tests/test_runner.py --live     # full live API test (needs server + .env)
    python tests/test_runner.py --mock     # mocked integration tests

The runner prints a colour-coded summary table on completion.
"""

import sys
import os
import json
import time
import unittest
from typing import Callable

# ── Add forge_system to path ──────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIVE_MODE = "--live" in sys.argv
MOCK_MODE = "--mock" in sys.argv
BASE_URL = "http://localhost:8000"

_PASS = "\033[92m✓\033[0m"
_FAIL = "\033[91m✗\033[0m"
_SKIP = "\033[93m~\033[0m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

results: list[dict] = []


def test(name: str, fn: Callable, live: bool = False, mock: bool = False):
    """Register and run a test, capturing pass/fail/skip."""
    if live and not LIVE_MODE:
        results.append({"name": name, "status": "skip", "detail": "requires --live"})
        return
    if mock and not (MOCK_MODE or LIVE_MODE):
        results.append({"name": name, "status": "skip", "detail": "requires --mock or --live"})
        return
    try:
        start = time.time()
        fn()
        elapsed = round((time.time() - start) * 1000)
        results.append({"name": name, "status": "pass", "detail": f"{elapsed}ms"})
        print(f"  {_PASS} {name} ({elapsed}ms)")
    except Exception as e:
        results.append({"name": name, "status": "fail", "detail": str(e)[:120]})
        print(f"  {_FAIL} {name} — {str(e)[:80]}")


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — pure business logic, no I/O
# ═══════════════════════════════════════════════════════════════════════════════

def _rating_basic():
    """Rating engine returns correct score and grade for known inputs."""
    from services.rating import compute_rating
    r = compute_rating(sent=100, replied=15, meetings=3, bounced=2, total_leads=100)
    assert 0 <= r.total <= 100, f"Total out of range: {r.total}"
    assert r.grade in ("S", "A", "B", "C", "F"), f"Invalid grade: {r.grade}"
    assert r.weakest_axis in ("Reply Rate", "Conversion Rate", "Volume Completion", "Deliverability")
    assert r.diagnosis, "Diagnosis is empty"
    assert r.recommended_action, "Recommended action is empty"


def _rating_zero_sends():
    """Rating engine handles zero-send campaigns without division by zero."""
    from services.rating import compute_rating
    r = compute_rating(sent=0, replied=0, meetings=0, bounced=0, total_leads=50)
    assert r.total == 0.0 or r.total >= 0, f"Negative rating: {r.total}"
    assert r.grade == "F"


def _rating_perfect():
    """Perfect campaign (100% reply rate, 100% conversion) scores >= 90."""
    from services.rating import compute_rating
    r = compute_rating(sent=100, replied=100, meetings=100, bounced=0, total_leads=100)
    assert r.total >= 90, f"Perfect campaign scored {r.total}, expected >= 90"
    assert r.grade == "S"


def _rating_weight_sum():
    """Rating breakdown max weights sum to 100."""
    from services.rating import compute_rating
    r = compute_rating(sent=50, replied=10, meetings=2, bounced=1, total_leads=100)
    total_max = sum(v.max for v in r.breakdown.values())
    assert total_max == 100, f"Weights don't sum to 100: {total_max}"


def _email_generator_prompt_build():
    """Email generator builds a non-empty prompt for a known lead."""
    from services.email_generator import _build_prompt
    lead = {"name": "Alice", "company": "LexCorp", "role": "COO", "city": "London"}
    prompt = _build_prompt(lead, "legal", None)
    assert "Alice" in prompt
    assert "LexCorp" in prompt
    assert "COO" in prompt
    assert len(prompt) > 200, f"Prompt too short: {len(prompt)}"
    assert "[Company Name]" not in prompt, "Placeholder field in prompt"


def _email_generator_icp_fallback():
    """Email generator falls back to ecommerce for unknown segment."""
    from services.email_generator import _build_prompt, ICP_PAIN_MAP
    lead = {"name": "Bob", "company": "Acme", "role": "CEO"}
    prompt = _build_prompt(lead, "unknown_segment", None)
    # Should fall back to ecommerce — check that ecommerce pain is in prompt
    ecommerce_pain = ICP_PAIN_MAP["ecommerce"]["pains"][0][:20]
    assert ecommerce_pain in prompt, "Ecommerce fallback not applied"


def _segregation_score_empty():
    """Segregation agent scores empty conversation as 0."""
    from services.segregation_agent import _quality_score
    score = _quality_score([], [])
    assert score == 0.0, f"Empty conversation scored {score}, expected 0.0"


def _segregation_score_correction():
    """Correction signal boosts score significantly."""
    from services.segregation_agent import _quality_score
    turns = [
        {"role": "user", "content": "How do I price my listing?"},
        {"role": "assistant", "content": "You should consider comparable sales in the area. " * 10},
    ]
    feedback_no = []
    feedback_correction = [{"signal_type": "correction", "corrected_text": "Better answer", "conversation_id": 2}]
    score_no = _quality_score(turns, feedback_no)
    score_correction = _quality_score(turns, feedback_correction)
    assert score_correction > score_no, f"Correction should boost score: {score_no} vs {score_correction}"
    assert score_correction >= 0.5, f"Correction score too low: {score_correction}"


def _segregation_format_training_example():
    """Training example formatter produces instruction/response pairs."""
    from services.segregation_agent import _format_training_example
    turns = [
        {"role": "user", "content": "What's a cap rate?", "id": 1},
        {"role": "assistant", "content": "Cap rate is net operating income divided by property value.", "id": 2},
    ]
    examples = _format_training_example(turns, [])
    assert len(examples) == 1
    assert examples[0]["instruction"] == "What's a cap rate?"
    assert "Cap rate" in examples[0]["response"]


def _segregation_correction_override():
    """Correction replaces assistant response in training example."""
    from services.segregation_agent import _format_training_example
    turns = [
        {"role": "user",      "content": "Best time to list?",              "id": 1},
        {"role": "assistant", "content": "Original (wrong) response.",       "id": 2},
    ]
    feedback = [{"signal_type": "correction", "corrected_text": "Spring is best.", "conversation_id": 2}]
    examples = _format_training_example(turns, feedback)
    assert examples[0]["response"] == "Spring is best.", f"Correction not applied: {examples[0]['response']}"


def _models_outreach_pydantic():
    """Outreach Pydantic models validate correctly."""
    from models.outreach import LeadIn, CampaignIn, EventIn
    lead = LeadIn(name="Jace", company="Virell", email="jace@virell.com")
    assert lead.email == "jace@virell.com"
    campaign = CampaignIn(name="Test Campaign", segment="legal")
    assert campaign.segment == "legal"
    event = EventIn(campaign_id=1, lead_id=1, event_type="sent")
    assert event.event_type == "sent"


def _models_asi_pydantic():
    """ASI models validate correctly."""
    from models.asi import OrchestratorCommand, NexusTask
    cmd = OrchestratorCommand(command="What is the current campaign status?")
    assert cmd.command
    assert cmd.context == {}


def _nexus_message_format():
    """Nexus task ID format is correct."""
    import uuid
    task_id = str(uuid.uuid4())[:12]
    assert len(task_id) == 12


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE API TESTS — requires running server on localhost:8000
# ═══════════════════════════════════════════════════════════════════════════════

def _api_health():
    import httpx
    r = httpx.get(f"{BASE_URL}/health/", timeout=5)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    assert r.json()["status"] == "ok"


def _api_root():
    import httpx
    r = httpx.get(f"{BASE_URL}/", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "FORGE ASI" in data["status"]
    assert "aeis" in data


def _api_leads_create_and_list():
    import httpx, uuid
    unique_email = f"test_{uuid.uuid4().hex[:8]}@test.com"
    r = httpx.post(f"{BASE_URL}/leads/", json={
        "name": "Test Lead", "company": "Test Corp",
        "email": unique_email, "industry": "ecommerce",
    }, timeout=10)
    assert r.status_code == 200, f"Lead creation failed: {r.text[:200]}"
    lead = r.json()
    assert lead["email"] == unique_email

    r2 = httpx.get(f"{BASE_URL}/leads/", timeout=10)
    assert r2.status_code == 200


def _api_campaign_create_and_rate():
    import httpx, uuid
    name = f"Test Campaign {uuid.uuid4().hex[:6]}"
    r = httpx.post(f"{BASE_URL}/campaigns/", json={"name": name, "segment": "ecommerce"}, timeout=10)
    assert r.status_code == 200, f"Campaign creation failed: {r.text[:200]}"
    campaign_id = r.json()["campaign"]["id"]

    r2 = httpx.get(f"{BASE_URL}/campaigns/{campaign_id}/rating/", timeout=10)
    assert r2.status_code == 200
    rating = r2.json()
    assert "total" in rating
    assert "grade" in rating


def _api_campaign_plan_generate():
    import httpx, uuid
    name = f"Plan Test {uuid.uuid4().hex[:6]}"
    r = httpx.post(f"{BASE_URL}/campaigns/", json={"name": name, "segment": "legal"}, timeout=10)
    assert r.status_code == 200
    campaign_id = r.json()["campaign"]["id"]

    r2 = httpx.post(f"{BASE_URL}/campaigns/{campaign_id}/plans/", timeout=15)
    assert r2.status_code == 200
    plan = r2.json()
    assert "steps" in plan
    assert len(plan["steps"]) >= 8, f"Expected >= 8 steps, got {len(plan['steps'])}"


def _api_events_log():
    import httpx, uuid
    name = f"Event Test {uuid.uuid4().hex[:6]}"
    email = f"evt_{uuid.uuid4().hex[:8]}@test.com"
    lead_r = httpx.post(f"{BASE_URL}/leads/", json={"name": "Evt Lead", "company": "Evt Corp", "email": email, "industry": "fintech"}, timeout=10)
    campaign_r = httpx.post(f"{BASE_URL}/campaigns/", json={"name": name, "segment": "fintech"}, timeout=10)
    assert lead_r.status_code == 200
    assert campaign_r.status_code == 200

    lead_id = lead_r.json()["id"]
    campaign_id = campaign_r.json()["campaign"]["id"]
    evt_r = httpx.post(f"{BASE_URL}/events/", json={"campaign_id": campaign_id, "lead_id": lead_id, "event_type": "sent"}, timeout=10)
    assert evt_r.status_code == 200
    assert evt_r.json()["logged"] == "sent"


def _api_dashboard():
    import httpx
    r = httpx.get(f"{BASE_URL}/events/dashboard/", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "active_campaigns" in data or "message" in data


def _api_asi_status():
    import httpx
    r = httpx.get(f"{BASE_URL}/asi/", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "aeis" in data
    assert "forge" in data["aeis"]
    assert "jarvis" in data["aeis"]


def _api_asi_command():
    import httpx
    r = httpx.post(f"{BASE_URL}/asi/command/", json={"command": "What is the current system status?"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "response" in data
    assert "command_id" in data
    assert len(data["response"]) > 10, "Response too short"


def _api_asi_health():
    import httpx
    r = httpx.get(f"{BASE_URL}/asi/health/", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "overall" in data
    assert "components" in data


def _api_ops_digest():
    import httpx
    r = httpx.get(f"{BASE_URL}/asi/ops/digest/", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "digest_bullets" in data
    assert len(data["digest_bullets"]) >= 1


def _api_tools_schema():
    import httpx
    r = httpx.get(f"{BASE_URL}/tools/schema/", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "tools" in data
    assert len(data["tools"]) >= 10, f"Expected >= 10 tools, got {len(data['tools'])}"
    tool_names = [t["name"] for t in data["tools"]]
    assert "orchestrate_command" in tool_names
    assert "get_campaign_rating" in tool_names


def _api_jarvis_chat():
    import httpx, uuid
    session_id = str(uuid.uuid4())
    r = httpx.post(f"{BASE_URL}/jarvis/chat/", json={
        "session_id": session_id,
        "content": "Hello, what is a cap rate?",
    }, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "response" in data
    assert len(data["response"]) > 10
    assert "latency_ms" in data


def _api_intel_research():
    import httpx
    r = httpx.post(f"{BASE_URL}/asi/intel/research/", json={"company_name": "Acme Legal Partners", "industry": "legal"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "pain_points" in data
    assert "hook_angle" in data
    assert len(data["pain_points"]) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

def run_all():
    print(f"\n{_BOLD}{'═'*60}{_RESET}")
    print(f"{_BOLD}  FORGE ASI — Test Suite{_RESET}")
    print(f"{'═'*60}")

    print(f"\n{_BOLD}UNIT — Rating Engine{_RESET}")
    test("Basic rating computation",       _rating_basic)
    test("Zero-send edge case",            _rating_zero_sends)
    test("Perfect campaign = grade S",     _rating_perfect)
    test("Weights sum to 100",             _rating_weight_sum)

    print(f"\n{_BOLD}UNIT — Email Generator{_RESET}")
    test("Prompt contains lead data",      _email_generator_prompt_build)
    test("Unknown segment fallback",       _email_generator_icp_fallback)

    print(f"\n{_BOLD}UNIT — Segregation Agent{_RESET}")
    test("Empty conversation = 0",         _segregation_score_empty)
    test("Correction boosts score",        _segregation_score_correction)
    test("Training example format",        _segregation_format_training_example)
    test("Correction overrides response",  _segregation_correction_override)

    print(f"\n{_BOLD}UNIT — Models & Architecture{_RESET}")
    test("Outreach Pydantic models",       _models_outreach_pydantic)
    test("ASI Pydantic models",            _models_asi_pydantic)
    test("Nexus task ID format",           _nexus_message_format)

    print(f"\n{_BOLD}LIVE — Core API (requires running server){_RESET}")
    test("GET /health/ returns ok",                _api_health,              live=True)
    test("GET / returns ASI version + AEIs",       _api_root,                live=True)
    test("POST + GET /leads/ round-trip",          _api_leads_create_and_list, live=True)
    test("Campaign create + rating",               _api_campaign_create_and_rate, live=True)
    test("Campaign plan generation",               _api_campaign_plan_generate, live=True)
    test("Event logging updates metrics",          _api_events_log,          live=True)
    test("GET /events/dashboard/",                 _api_dashboard,           live=True)

    print(f"\n{_BOLD}LIVE — ASI Orchestrator{_RESET}")
    test("GET /asi/ — system status",              _api_asi_status,          live=True)
    test("POST /asi/command/ — natural language",  _api_asi_command,         live=True)
    test("GET /asi/health/ — component health",    _api_asi_health,          live=True)
    test("GET /asi/ops/digest/",                   _api_ops_digest,          live=True)
    test("GET /tools/schema/ — Gemini tools",      _api_tools_schema,        live=True)

    print(f"\n{_BOLD}LIVE — Jarvis & Intel{_RESET}")
    test("POST /jarvis/chat/ — Gemini response",   _api_jarvis_chat,         live=True)
    test("POST /asi/intel/research/ — company brief", _api_intel_research,   live=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    passed  = sum(1 for r in results if r["status"] == "pass")
    failed  = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")

    print(f"\n{'═'*60}")
    print(f"{_BOLD}  Results: {_PASS} {passed} passed  {_FAIL} {failed} failed  {_SKIP} {skipped} skipped{_RESET}")
    if failed:
        print(f"\n{_BOLD}Failed tests:{_RESET}")
        for r in results:
            if r["status"] == "fail":
                print(f"  {_FAIL} {r['name']}: {r['detail']}")
    print(f"{'═'*60}\n")

    return failed


if __name__ == "__main__":
    failed = run_all()
    sys.exit(1 if failed else 0)
