"""
Archim8 Phase 8 — MCP server smoke test

Verifies:
  T0  mcp package is importable
  T1  FastMCP can be instantiated
  T2  mcp_server module imports without error
  T3  All expected tool names are registered on the server
  T4  Write-path tools have ⚠️ in their docstring (Human Anchor marker)
  T5  Tool functions are callable (without live deps — pass None args where safe)
  T6  archim8_apply_cypher_migration returns error when driver not initialised
      (confirms path-gate is active even without Neo4j)

Run:
    python 14_tests/test_mcp_server.py
or:
    make smoke
"""

import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
ARCHIM8_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ARCHIM8_ROOT / "06_agents"))

PASS = "\033[32m[PASS]\033[0m"
FAIL = "\033[31m[FAIL]\033[0m"
_failures = 0


def check(label: str, condition: bool, detail: str = ""):
    global _failures
    if condition:
        print(f"{PASS} {label}")
    else:
        print(f"{FAIL} {label}" + (f" — {detail}" if detail else ""))
        _failures += 1


# ---------------------------------------------------------------------------
# T0: mcp importable
# ---------------------------------------------------------------------------
try:
    import mcp  # noqa: F401
    check("T0  mcp package importable", True)
except ImportError as e:
    check("T0  mcp package importable", False, str(e))
    print("\nInstall with: pip install mcp")
    sys.exit(1)

# ---------------------------------------------------------------------------
# T1: FastMCP instantiable
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
    _test_mcp = FastMCP("test")
    check("T1  FastMCP instantiable", True)
except Exception as e:
    check("T1  FastMCP instantiable", False, str(e))
    sys.exit(1)

# ---------------------------------------------------------------------------
# T2: mcp_server imports without error
# ---------------------------------------------------------------------------
try:
    import mcp_server  # noqa: F401
    check("T2  mcp_server module imports", True)
except Exception as e:
    check("T2  mcp_server module imports", False, str(e))
    sys.exit(1)

# ---------------------------------------------------------------------------
# T3: All expected tools registered
# ---------------------------------------------------------------------------
EXPECTED_TOOLS = {
    "archim8_run_cypher_query",
    "archim8_list_available_views",
    "archim8_read_architecture_view",
    "archim8_generate_architecture_diagram",
    "archim8_generate_mermaid_diagram",
    "archim8_check_file_exists",
    "archim8_read_log_file",
    "archim8_check_docker_health",
    "archim8_run_make_target",
    "archim8_apply_cypher_migration",
}

try:
    # FastMCP stores tools in ._tool_manager or ._tools depending on version
    tool_manager = getattr(mcp_server.mcp, "_tool_manager", None)
    if tool_manager is not None:
        registered = set(tool_manager._tools.keys())
    else:
        registered = set(getattr(mcp_server.mcp, "_tools", {}).keys())

    missing = EXPECTED_TOOLS - registered
    check("T3  all expected tools registered", not missing,
          f"missing: {missing}" if missing else "")
except Exception as e:
    check("T3  all expected tools registered", False, str(e))

# ---------------------------------------------------------------------------
# T4: Write-path tools have ⚠️ Human Anchor marker in docstring
# ---------------------------------------------------------------------------
WRITE_PATH_TOOLS = {
    "archim8_run_make_target",
    "archim8_apply_cypher_migration",
    "archim8_generate_architecture_diagram",
    "archim8_generate_mermaid_diagram",
}

for tool_name in WRITE_PATH_TOOLS:
    fn = getattr(mcp_server, tool_name, None)
    if fn is None:
        check(f"T4  {tool_name} has ⚠️ marker", False, "function not found on module")
    else:
        doc = fn.__doc__ or ""
        check(f"T4  {tool_name} has ⚠️ marker", "⚠️" in doc,
              "missing ⚠️ in docstring")

# ---------------------------------------------------------------------------
# T5: archim8_run_cypher_query returns error (driver not configured)
# ---------------------------------------------------------------------------
try:
    # Force driver to None to simulate cold start
    import tools.graph_query as gq
    _saved_driver = gq._driver
    gq._driver = None

    result = mcp_server.archim8_run_cypher_query("MATCH (n) RETURN count(n)")
    check("T5  run_cypher_query returns error when driver not configured",
          "ERROR" in result, f"got: {result[:80]}")

    gq._driver = _saved_driver
except Exception as e:
    check("T5  run_cypher_query returns error when driver not configured", False, str(e))

# ---------------------------------------------------------------------------
# T6: archim8_apply_cypher_migration returns error when driver not configured
# ---------------------------------------------------------------------------
try:
    _saved_driver2 = gq._driver
    gq._driver = None

    result2 = mcp_server.archim8_apply_cypher_migration(
        "02_store/neo4j/config/schema/001_constraints.cypher"
    )
    check("T6  apply_cypher_migration returns error when driver not configured",
          "ERROR" in result2, f"got: {result2[:80]}")

    gq._driver = _saved_driver2
except Exception as e:
    check("T6  apply_cypher_migration returns error when driver not configured", False, str(e))

# ---------------------------------------------------------------------------
# T7: archim8_generate_mermaid_diagram returns error for unknown type
# ---------------------------------------------------------------------------
try:
    result3 = mcp_server.archim8_generate_mermaid_diagram("__invalid__")
    check("T7  generate_mermaid_diagram rejects unknown diagram_type",
          "ERROR" in result3, f"got: {result3[:80]}")
except Exception as e:
    check("T7  generate_mermaid_diagram rejects unknown diagram_type", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
if _failures == 0:
    print(f"\033[32mAll tests passed.\033[0m")
else:
    print(f"\033[31m{_failures} test(s) failed.\033[0m")
    sys.exit(1)
