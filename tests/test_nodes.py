"""Tests for node functions — classify_node routing logic."""

from __future__ import annotations

import pytest

from langgraph_agent_lab.nodes import classify_node
from langgraph_agent_lab.state import Route

# ---------------------------------------------------------------------------
# Classify node — all 7 sample scenarios must route correctly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        # S01 — simple default
        ("How do I reset my password?", Route.SIMPLE.value),
        # S02 — tool keywords: lookup, order, status
        ("Please lookup order status for order 12345", Route.TOOL.value),
        # S03 — missing_info: 5 words + "it"
        ("Can you fix it?", Route.MISSING_INFO.value),
        # S04 — risky: refund + send
        ("Refund this customer and send confirmation email", Route.RISKY.value),
        # S05 — error: timeout + failure
        ("Timeout failure while processing request", Route.ERROR.value),
        # S06 — risky: delete
        ("Delete customer account after support verification", Route.RISKY.value),
        # S07 — error: failure
        ("System failure cannot recover after multiple attempts", Route.ERROR.value),
    ],
)
def test_classify_all_sample_scenarios(query: str, expected_route: str) -> None:
    result = classify_node({"query": query})
    assert result["route"] == expected_route, (
        f"Query '{query}' expected route '{expected_route}' but got '{result['route']}'"
    )


# ---------------------------------------------------------------------------
# Priority: risky beats everything
# ---------------------------------------------------------------------------


def test_risky_beats_tool_keyword() -> None:
    """A query with both risky and tool keywords must route to risky."""
    result = classify_node({"query": "Check refund status"})
    assert result["route"] == Route.RISKY.value


def test_risky_beats_error_keyword() -> None:
    result = classify_node({"query": "Cancel order due to system error"})
    assert result["route"] == Route.RISKY.value


# ---------------------------------------------------------------------------
# Extra risky keywords
# ---------------------------------------------------------------------------


def test_classify_cancel() -> None:
    assert classify_node({"query": "Cancel my subscription"})["route"] == Route.RISKY.value


def test_classify_remove() -> None:
    assert classify_node({"query": "Remove this item from the account"})["route"] == Route.RISKY.value


def test_classify_revoke() -> None:
    assert classify_node({"query": "Revoke user access immediately"})["route"] == Route.RISKY.value


# ---------------------------------------------------------------------------
# Extra tool keywords
# ---------------------------------------------------------------------------


def test_classify_check() -> None:
    assert classify_node({"query": "Check the current balance"})["route"] == Route.TOOL.value


def test_classify_track() -> None:
    assert classify_node({"query": "Track my shipment please"})["route"] == Route.TOOL.value


def test_classify_find() -> None:
    assert classify_node({"query": "Find all orders for customer"})["route"] == Route.TOOL.value


# ---------------------------------------------------------------------------
# Extra error keywords
# ---------------------------------------------------------------------------


def test_classify_error_keyword() -> None:
    assert classify_node({"query": "An error occurred in the system"})["route"] == Route.ERROR.value


def test_classify_crash() -> None:
    assert classify_node({"query": "The service crash unavailable"})["route"] == Route.ERROR.value


# ---------------------------------------------------------------------------
# Risk level
# ---------------------------------------------------------------------------


def test_risky_sets_high_risk_level() -> None:
    result = classify_node({"query": "Refund this customer"})
    assert result["risk_level"] == "high"


def test_simple_sets_low_risk_level() -> None:
    result = classify_node({"query": "How do I reset my password?"})
    assert result["risk_level"] == "low"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def test_classify_emits_event() -> None:
    result = classify_node({"query": "How do I reset my password?"})
    assert result["events"]
    assert result["events"][0]["node"] == "classify"
