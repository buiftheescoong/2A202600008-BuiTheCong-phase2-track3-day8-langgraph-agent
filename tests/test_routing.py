from langgraph_agent_lab.routing import (
    route_after_approval,
    route_after_classify,
    route_after_evaluate,
    route_after_retry,
)
from langgraph_agent_lab.state import Route


def test_route_after_classify_simple() -> None:
    assert route_after_classify({"route": Route.SIMPLE.value}) == "answer"


def test_route_after_classify_tool() -> None:
    assert route_after_classify({"route": Route.TOOL.value}) == "tool"


def test_route_after_classify_risky() -> None:
    assert route_after_classify({"route": Route.RISKY.value}) == "risky_action"


def test_route_after_classify_missing_info() -> None:
    assert route_after_classify({"route": Route.MISSING_INFO.value}) == "clarify"


def test_route_after_classify_error() -> None:
    assert route_after_classify({"route": Route.ERROR.value}) == "retry"


def test_route_after_classify_unknown_defaults_to_answer() -> None:
    assert route_after_classify({"route": "not_a_real_route"}) == "answer"


def test_route_after_approval_approved() -> None:
    assert route_after_approval({"approval": {"approved": True}}) == "tool"


def test_route_after_approval_rejected() -> None:
    assert route_after_approval({"approval": {"approved": False}}) == "clarify"


def test_route_after_approval_missing() -> None:
    assert route_after_approval({}) == "clarify"


def test_route_after_retry_below_max() -> None:
    assert route_after_retry({"attempt": 0, "max_attempts": 3}) == "tool"
    assert route_after_retry({"attempt": 2, "max_attempts": 3}) == "tool"


def test_route_after_retry_at_max() -> None:
    assert route_after_retry({"attempt": 3, "max_attempts": 3}) == "dead_letter"


def test_route_after_retry_max_attempts_1() -> None:
    """S07 scenario: max_attempts=1 should dead-letter immediately after first retry."""
    assert route_after_retry({"attempt": 1, "max_attempts": 1}) == "dead_letter"


def test_route_after_evaluate_success() -> None:
    assert route_after_evaluate({"evaluation_result": "success"}) == "answer"


def test_route_after_evaluate_needs_retry() -> None:
    assert route_after_evaluate({"evaluation_result": "needs_retry"}) == "retry"


def test_route_after_evaluate_missing_defaults_to_answer() -> None:
    assert route_after_evaluate({}) == "answer"
