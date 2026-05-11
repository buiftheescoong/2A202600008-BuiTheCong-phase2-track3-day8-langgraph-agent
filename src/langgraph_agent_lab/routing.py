"""Routing functions for conditional edges.

Priority design: all routing is explicit — unknown routes fall back to safe defaults.
"""

from __future__ import annotations

from .state import AgentState, Route


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node.

    Unknown routes default to 'answer' (safe fallback — never crash).
    """
    route = state.get("route", Route.SIMPLE.value)
    mapping = {
        Route.SIMPLE.value: "answer",
        Route.TOOL.value: "tool",
        Route.MISSING_INFO.value: "clarify",
        Route.RISKY.value: "risky_action",
        Route.ERROR.value: "retry",
    }
    return mapping.get(route, "answer")


def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry or escalate to dead-letter.

    Bounded by max_attempts — prevents infinite retry loops.
    When attempt >= max_attempts, route to dead_letter for manual review.
    """
    if int(state.get("attempt", 0)) >= int(state.get("max_attempts", 3)):
        return "dead_letter"
    return "tool"


def route_after_evaluate(state: AgentState) -> str:
    """Decide whether tool result is satisfactory or needs retry.

    This is the 'done?' check that enables retry loops — a key LangGraph
    advantage over LCEL chains. Uses structured evaluation_result field
    set by evaluate_node. Defaults to 'answer' if result is missing/unknown.
    """
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_approval(state: AgentState) -> str:
    """Continue to tool execution only if approved; otherwise ask for clarification.

    Handles three outcomes:
    - approved=True  → proceed to tool node
    - approved=False → redirect to clarify (safe fallback, informs user)
    - missing/None   → redirect to clarify (fail-safe)
    """
    approval = state.get("approval") or {}
    return "tool" if approval.get("approved") else "clarify"
