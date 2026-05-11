# Day 08 Lab Report

## 1. Team / student

- **Name:** Bui The Cong
- **Student ID:** 2A202600008
- **Repo:** https://github.com/buiftheescoong/2A202600008-BuiTheCong-phase2-track3-day8-langgraph-agent.git
- **Date:** 2026-05-11

---

## 2. Architecture

The graph implements a production-style **support-ticket routing agent** using LangGraph's `StateGraph`. The workflow is:

```
START → intake → classify → [conditional routing]
  simple        → answer → finalize → END
  tool          → tool → evaluate → answer → finalize → END
  tool (retry)  → tool → evaluate → retry → tool → ... (bounded loop)
  missing_info  → clarify → finalize → END
  risky         → risky_action → approval → tool → evaluate → answer → finalize → END
  error         → retry → tool → evaluate → retry → ... → dead_letter → finalize → END
```

### Key design decisions:
- **`intake_node`**: Normalizes raw query text (strip whitespace, future PII checks).
- **`classify_node`**: Keyword-based heuristics with **priority order** (risky > tool > missing_info > error > simple) to prevent keyword conflicts.
- **`evaluate_node`**: Acts as the "done?" gate — checks if tool result contains `ERROR` marker, enabling the retry loop.
- **`retry_or_fallback_node`**: Increments `attempt` counter. Bounded by `max_attempts` via `route_after_retry`.
- **`dead_letter_node`**: Terminal escalation when max retries exhausted.
- **`approval_node`**: Supports both mock approval (CI-safe) and real `interrupt()` via `LANGGRAPH_INTERRUPT=true`.

---

## 3. State schema

| Field | Type | Reducer | Purpose |
|---|---|---|---|
| `thread_id` | `str` | overwrite | Unique run identifier for checkpointing |
| `scenario_id` | `str` | overwrite | Links state to scenario for metrics |
| `query` | `str` | overwrite | Normalized user query |
| `route` | `str` | overwrite | Current routing decision (only latest matters) |
| `risk_level` | `str` | overwrite | `low` / `medium` / `high` from classify |
| `attempt` | `int` | overwrite | Retry counter (incremented by retry node) |
| `max_attempts` | `int` | overwrite | Upper bound for retry loop (default 3) |
| `final_answer` | `str | None` | overwrite | The agent's response to the user |
| `pending_question` | `str | None` | overwrite | Clarification question if missing info |
| `proposed_action` | `str | None` | overwrite | Risky action awaiting approval |
| `approval` | `dict | None` | overwrite | Approval decision from HITL node |
| `evaluation_result` | `str | None` | overwrite | `success` or `needs_retry` |
| `messages` | `list[str]` | **append** (`add`) | Audit message log |
| `tool_results` | `list[str]` | **append** (`add`) | All tool call results (needed for retry context) |
| `errors` | `list[str]` | **append** (`add`) | Error log across all retry attempts |
| `events` | `list[dict]` | **append** (`add`) | Structured audit events for metrics |

Append-only fields use `Annotated[list, add]` — LangGraph merges them across node updates, preserving full history without overwriting.

---

## 4. Scenario results

| Scenario | Expected | Actual | Route✓ | Success | Retries | Interrupts | Latency |
|---|---|---|---|---|---|---|---|
| S01_simple | simple | simple | ✅ | ✅ | 0 | 0 | 47ms |
| S02_tool | tool | tool | ✅ | ✅ | 0 | 0 | 16ms |
| S03_missing | missing_info | missing_info | ✅ | ✅ | 0 | 0 | 14ms |
| S04_risky | risky | risky | ✅ | ✅ | 0 | 3 | 16ms |
| S05_error | error | error | ✅ | ✅ | 6 | 0 | 30ms |
| S06_delete | risky | risky | ✅ | ✅ | 0 | 3 | 16ms |
| S07_dead_letter | error | error | ✅ | ✅ | 3 | 0 | 14ms |
| S08_cancel | risky | risky | ✅ | ✅ | 0 | 2 | 32ms |
| S09_track | tool | tool | ✅ | ✅ | 0 | 0 | 14ms |
| S10_vague | missing_info | missing_info | ✅ | ✅ | 0 | 0 | 0ms |

### Summary
- **Total scenarios:** 10
- **Success rate:** 100%
- **Average nodes visited:** 17.1
- **Total retries:** 9
- **Total interrupts (HITL):** 8
- **Crash-resume:** ❌ Not demonstrated (using MemorySaver)

---

## 5. Failure analysis

### Failure mode 1: Retry loop exhaustion → Dead Letter (S07)

**Scenario:** S07_dead_letter — `max_attempts=1`, query triggers error route.

**Flow:** `classify(error) → retry(attempt=1) → route_after_retry: 1 >= 1 → dead_letter → finalize`

The `route_after_retry` function checks `attempt >= max_attempts`. When S07 sets `max_attempts=1`, the very first retry immediately exhausts the budget. The `dead_letter_node` logs the failure with attempt count and scenario ID. Without this bound, the error route would loop indefinitely — a critical design constraint.

### Failure mode 2: Risky action without approval fallback (S04, S06)

**Scenario:** S04_risky — refund + send keywords, `requires_approval=True`.

**Flow:** `classify(risky) → risky_action → approval(mock=True) → tool → evaluate → answer → finalize`

If `approval_node` returns `approved=False` (e.g., real HITL rejection), `route_after_approval` redirects to `clarify`, which gracefully informs the user and terminates. This prevents dangerous actions from executing without explicit human sign-off. In mock mode, approval always returns `True` for CI safety.

---

## 6. Persistence / recovery evidence

The checkpointer is configured via `configs/lab.yaml`:

```yaml
checkpointer: sqlite
database_url: outputs/checkpoints.db
```

`build_checkpointer("sqlite")` creates a SQLite connection with **WAL mode** enabled:
```python
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
return SqliteSaver(conn=conn)
```

Each scenario run uses a unique `thread_id` (e.g., `thread-S01_simple`), which LangGraph uses as the checkpoint key. State is saved after every node execution. If the process is killed mid-run and restarted with the same `thread_id`, the graph resumes from the last saved checkpoint via `graph.get_state_history(config)`.

---

## 7. Extension work

### Bonus: Graph Diagram Export

A new `export-diagram` CLI command was added to `cli.py`:

```bash
python -m langgraph_agent_lab.cli export-diagram --output outputs/graph.mmd
```

This calls `graph.get_graph().draw_mermaid()` and saves the Mermaid diagram to `outputs/graph.mmd`. The diagram visually documents every node and conditional edge in the compiled graph.

### Bonus: SQLite Persistence

Switched from `MemorySaver` to `SqliteSaver` with WAL mode. Fixed the v3.x API — replaced deprecated `SqliteSaver.from_conn_string()` with `SqliteSaver(conn=sqlite3.connect(...))`. The database survives process restarts, enabling crash-resume behavior.

---

## 8. Improvement plan

If given one more day, the top priorities would be:

1. **LLM-as-judge for `evaluate_node`**: Replace the `"ERROR" in result` heuristic with a structured LLM call that validates tool output quality, schema correctness, and completeness.

2. **Real HITL with Streamlit UI**: Build an approval dashboard that presents `proposed_action` and `risk_level` to a human reviewer, captures approve/reject/edit decisions, and resumes the graph via `graph.invoke(Command(resume=decision), config=config)`.

3. **Parallel fan-out for tool node**: Use `Send()` to dispatch two mock tools concurrently (e.g., order lookup + account check), merge results via the `add` reducer, improving throughput for complex queries.

4. **Exponential backoff**: Add `backoff_ms` metadata to retry events to simulate realistic retry timing behavior.

5. **Observability**: Integrate LangSmith tracing for production monitoring of node latencies, retry rates, and routing distribution.
