# 14_tests — Tests & Acceptance Gates

Smoke tests for the Archim8 MCP server. The smoke test runs without live infrastructure
— no Neo4j required.

---

## Test files

| File | Type | Live deps? | What it tests |
|------|------|-----------|---------------|
| `test_mcp_server.py` | Smoke | None | MCP package, FastMCP, all tools registered, write-path markers, query/migration error handling |

---

## How to run

```powershell
# From archim8/ root

make smoke                  # MCP server smoke test
python 14_tests/test_mcp_server.py  # direct

make test                   # full pytest suite
```

---

## What the smoke test covers

### `test_mcp_server.py`

| Gate | What is checked |
|------|-----------------|
| T0 | `mcp` package importable |
| T1 | `FastMCP` can be instantiated |
| T2 | `mcp_server` module imports without error |
| T3 | All 9 expected tools are registered on the server |
| T4 | All 3 write-path tools have `⚠️` Human Anchor marker in docstring |
| T5 | `archim8_run_cypher_query` returns error when Neo4j driver not configured |
| T6 | `archim8_apply_cypher_migration` returns error when Neo4j driver not configured |

---

## Adding tests

- **Smoke tests**: extend `test_mcp_server.py` or add new `test_*.py` files
  using the same `check()` helper pattern
- **pytest tests**: add a `test_*.py` file and run with `make test`
- Keep smoke tests free of live dependencies so they can run without credentials


---

## Test files

| File | Type | Live deps? | Phase gate | What it tests |
|------|------|-----------|------------|--------------|
| `smoke_test_agent.py` | Smoke | None | Any | Config loading, tool module imports, single-agent build |
| `smoke_test_orchestrator.py` | Smoke | None | 5-T0 to 5-T5 | StateGraph compilation, profile loading, routing logic, safety guards, Human Anchor gate |
| `test_5t6_human_anchor.py` | Acceptance | Neo4j + LLM | 5-T6 | Human Anchor approve and deny paths with a live graph |

---

## How to run

### Smoke tests (no live deps — run any time)

```powershell
# From archim8/ root

# Both smoke tests together
make smoke

# Individually
make smoke-orchestrator     # Phase 5 gate: T0–T5  (graph compilation + safety)
make smoke-agent            # Legacy single-agent import sanity check

# Or directly
python 14_tests/smoke_test_orchestrator.py
python 14_tests/smoke_test_agent.py
```

### Acceptance test (requires live Neo4j + GITHUB_TOKEN)

```powershell
# Prerequisites: make docker-up, GITHUB_TOKEN set in archim8.local.env, graph ingested

python 14_tests/test_5t6_human_anchor.py
```

### Full test suite (pytest)

```powershell
make test         # runs pytest 14_tests/
```

---

## What the smoke tests cover

### `smoke_test_orchestrator.py`

- All tool modules import cleanly
- All specialist `build_agent()` functions are callable
- `build_orchestrator()` compiles the `StateGraph` without error
- All profiles (`analyst`, `pipeline`, `operator`, `local`) load and resolve env vars correctly
- Safety guards fire: Cypher write mutations blocked, path traversal blocked, target repo allowlist enforced
- Human Anchor: `interrupt_before` contains the three write-path agents

### `smoke_test_agent.py`

- `agent.yaml` loads and resolves environment variable substitution
- Tool modules import without error
- Single-agent construction succeeds

### `test_5t6_human_anchor.py` (5-T6)

- A write-path request pauses the LangGraph `StateGraph` at the interrupt checkpoint (deny path)
- `graph.invoke(None)` after the pause resumes and completes (approve path)

---

## Adding tests

- **Smoke tests**: extend the existing scripts — no pytest infrastructure needed, just `assert` and `print` statements
- **pytest tests**: add a `test_*.py` file and run with `make test`
- Keep smoke tests free of live dependencies so they can always run in CI without credentials
