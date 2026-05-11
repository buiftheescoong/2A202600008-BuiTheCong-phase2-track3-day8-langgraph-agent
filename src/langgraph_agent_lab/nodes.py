"""Node skeletons for the LangGraph workflow.

Each function should be small, testable, and return a partial state update. Avoid mutating the
input state in place.
"""

from __future__ import annotations

import re

from .state import AgentState, ApprovalDecision, Route, make_event

# ---------------------------------------------------------------------------
# Keyword sets for classify_node — priority: risky > tool > missing_info > error > simple
# ---------------------------------------------------------------------------

_RISKY_KEYWORDS: set[str] = {"refund", "delete", "send", "cancel", "remove", "revoke"}

_TOOL_KEYWORDS: frozenset[str] = frozenset(
    {"status", "order", "lookup", "check", "track", "find", "search"}
)

_ERROR_KEYWORDS: frozenset[str] = frozenset(
    {"timeout", "fail", "failure", "error", "crash", "unavailable"}
)


def _clean_words(text: str) -> set[str]:
    """Lowercase, strip punctuation, split into word set."""
    return set(re.sub(r"[?!.,;:]", "", text.lower()).split())


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def intake_node(state: AgentState) -> dict:
    """Normalize raw query into state fields."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using keyword-based heuristics.

    Priority order: risky > tool > missing_info > error > simple.
    This prevents conflicts when a query contains keywords from multiple categories.
    """
    query = state.get("query", "").lower()
    words = _clean_words(query)

    # Priority 1: RISKY — refund, delete, send, cancel, remove, revoke
    if _RISKY_KEYWORDS & words or any(k in query for k in _RISKY_KEYWORDS):
        route = Route.RISKY
        risk_level = "high"

    # Priority 2: TOOL — status, order, lookup, check, track, find, search
    elif any(k in query for k in _TOOL_KEYWORDS):
        route = Route.TOOL
        risk_level = "low"

    # Priority 3: MISSING_INFO — short/vague query (<= 5 words) containing pronoun "it"
    elif len(words) <= 5 and "it" in words:
        route = Route.MISSING_INFO
        risk_level = "low"

    # Priority 4: ERROR — timeout, fail/failure, error, crash, unavailable
    elif any(k in query for k in _ERROR_KEYWORDS):
        route = Route.ERROR
        risk_level = "medium"

    # Default: SIMPLE
    else:
        route = Route.SIMPLE
        risk_level = "low"

    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    question = (
        "Could you please provide more details? "
        "For example, include an order ID, account number, "
        "or describe the specific issue you are facing."
    )
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "missing information requested")],
    }


def tool_node(state: AgentState) -> dict:
    """Call a mock tool.

    Simulates transient failures for error-route scenarios to demonstrate retry loops.
    The tool succeeds once attempt >= 2, enabling the retry loop to terminate.
    """
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    if state.get("route") == Route.ERROR.value and attempt < 2:
        result = f"ERROR: transient failure attempt={attempt} scenario={scenario_id}"
    else:
        result = f"mock-tool-result for scenario={scenario_id} attempt={attempt}"
    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", f"tool executed attempt={attempt}")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for approval.

    Records the proposed action with risk justification before escalating to HITL approval.
    """
    query = state.get("query", "")
    risk = state.get('risk_level', 'high')
    proposed = (
        f"Action proposed from query: '{query[:60]}'. "
        f"Risk level: {risk}. Approval required."
    )
    return {
        "proposed_action": proposed,
        "events": [make_event("risky_action", "pending_approval", "approval required")],
    }


def approval_node(state: AgentState) -> dict:
    """Human approval step with optional LangGraph interrupt().

    Set LANGGRAPH_INTERRUPT=true to use real interrupt() for HITL demos.
    Default uses mock decision so tests and CI run offline.
    """
    import os

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt  # type: ignore[import]

        value = interrupt(
            {
                "proposed_action": state.get("proposed_action"),
                "risk_level": state.get("risk_level"),
            }
        )
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        decision = ApprovalDecision(approved=True, comment="mock approval for lab")

    return {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt. Bounded by max_attempts — see route_after_retry."""
    attempt = int(state.get("attempt", 0)) + 1
    return {
        "attempt": attempt,
        "errors": [f"transient failure attempt={attempt}"],
        "events": [make_event("retry", "completed", "retry attempt recorded", attempt=attempt)],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response grounded in tool_results and approval context."""
    tool_results = state.get("tool_results") or []
    approval = state.get("approval") or {}

    if tool_results:
        last_result = tool_results[-1]
        if approval.get("approved"):
            answer = f"Action approved and executed. Result: {last_result}"
        else:
            answer = f"Found the following information: {last_result}"
    else:
        answer = "Your request has been processed. No additional data was required."

    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the 'done?' check that enables retry loops.

    Returns 'needs_retry' if the latest tool result contains an ERROR marker,
    otherwise returns 'success' to proceed to the answer node.
    """
    tool_results = state.get("tool_results") or []
    latest = tool_results[-1] if tool_results else ""
    if "ERROR" in latest:
        return {
            "evaluation_result": "needs_retry",
            "events": [
                make_event("evaluate", "needs_retry", "tool result indicates failure, retry needed")
            ],
        }
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "success", "tool result satisfactory")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Log unresolvable failures for manual review.

    Third layer of error strategy: retry -> fallback -> dead letter.
    In production this would persist to a dead-letter queue and alert on-call.
    """
    attempt = state.get("attempt", 0)
    scenario_id = state.get("scenario_id", "unknown")
    return {
        "final_answer": (
            f"Request '{scenario_id}' could not be completed after {attempt} attempt(s). "
            "Logged for manual review."
        ),
        "events": [
            make_event(
                "dead_letter",
                "completed",
                "max retries exceeded",
                attempt=attempt,
                scenario_id=scenario_id,
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
