"""
Archim8 MCP Server — Phase 8

Exposes all Archim8 tools to GitHub Copilot Chat via the Model Context Protocol.
Start via: python 06_agents/mcp_server.py
Or via VS Code: configured in .vscode/mcp.json (starts automatically).

Tool categories:
  read-only  — graph queries, view reads, file/health checks
  write-path — run_make_target, apply_cypher_migration  (Human Anchor applies)
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve workspace root and bootstrap Python path
# ---------------------------------------------------------------------------
ARCHIM8_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------------------
# Load archim8.local.env before anything else
# ---------------------------------------------------------------------------
_env_file = os.environ.get(
    "ARCHIM8_ENV_FILE",
    str(ARCHIM8_ROOT / "00_orchestrate" / "config" / "archim8.local.env"),
)
try:
    from dotenv import load_dotenv
    if Path(_env_file).exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    pass  # python-dotenv optional if vars are already in environment

# ---------------------------------------------------------------------------
# Create FastMCP instance
# ---------------------------------------------------------------------------
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Archim8")

# ---------------------------------------------------------------------------
# Initialise tool modules with runtime config
# ---------------------------------------------------------------------------
_neo4j_bolt     = os.environ.get("ARCHIM8_NEO4J_BOLT",     "bolt://localhost:7687")
_neo4j_user     = os.environ.get("ARCHIM8_NEO4J_USER",     "neo4j")
_neo4j_password = os.environ.get("ARCHIM8_NEO4J_PASSWORD", "password")

from tools.graph_query import (
    init_driver, init_migration_path,
    run_cypher_query, run_cypher_migration,
)
from tools.view_reader import (
    init_paths as _vr_init,
    list_available_views, read_architecture_view,
)
from tools.diagram_gen import (
    init_paths as _dg_init,
    generate_architecture_diagram,
)
from tools.mermaid_gen import (
    init_paths as _mg_init,
    generate_mermaid_diagram,
)
from tools.shell_exec import (
    init_paths as _se_init,
    run_make_target, check_file_exists, read_log_file,
)
from tools.docker_health import check_docker_health

init_driver(_neo4j_bolt, _neo4j_user, _neo4j_password)
init_migration_path(ARCHIM8_ROOT)
_vr_init(
    manifest_path=ARCHIM8_ROOT / "05_deliver" / "output" / "manifest.json",
    views_dir=ARCHIM8_ROOT / "05_deliver" / "output" / "views",
)
_dg_init(archim8_root=ARCHIM8_ROOT, python_exe=sys.executable)
_mg_init(archim8_root=ARCHIM8_ROOT)
_se_init(archim8_root=ARCHIM8_ROOT)

# ---------------------------------------------------------------------------
# Register read-only tools
# ---------------------------------------------------------------------------

@mcp.tool()
def archim8_run_cypher_query(cypher: str) -> str:
    """Run a read-only Cypher query against the architecture graph in Neo4j.

    Use this for ad-hoc structural questions not covered by an existing view.
    Only MATCH/RETURN/WITH/UNWIND/OPTIONAL MATCH are permitted — write
    operations (MERGE, CREATE, SET, DELETE, etc.) are blocked.

    Args:
        cypher: A read-only Cypher query string.

    Returns:
        Markdown table of results, or an error message.
    """
    return run_cypher_query(cypher)


@mcp.tool()
def archim8_list_available_views() -> str:
    """List all pre-generated architecture views from the Archim8 manifest.

    Returns view names, row counts, scope descriptions, and generation timestamps.
    Always call this before read_architecture_view to confirm which views exist.

    Returns:
        Markdown table of available views and their metadata.
    """
    return list_available_views()


@mcp.tool()
def archim8_read_architecture_view(view_name: str) -> str:
    """Read the content of a pre-generated architecture view.

    Available views (call list_available_views to confirm current set):
    module-deps, grpc-services, pekka-http-api, spring-components,
    observability-coverage, violations, key-abstractions, cobol-subsystem.

    Args:
        view_name: Name of the view (without .md extension).

    Returns:
        View content as Markdown text, or an error.
    """
    return read_architecture_view(view_name)


@mcp.tool()
def archim8_generate_architecture_diagram(diagram_type: str) -> str:
    """Generate a PlantUML C4 architecture diagram from the live Neo4j graph.

    Writes to 05_deliver/output/ as .puml files.
    Available types: "containers", "cobol", "all".

    ⚠️  Write-path tool — confirm with user before calling.

    Args:
        diagram_type: One of "containers", "cobol", or "all".

    Returns:
        Confirmation message with output file paths.
    """
    return generate_architecture_diagram(diagram_type)


@mcp.tool()
def archim8_check_file_exists(file_path: str) -> str:
    """Check whether a file or directory exists within the Archim8 workspace.

    Args:
        file_path: Workspace-relative path (e.g. "05_deliver/output/manifest.json").

    Returns:
        Status: exists/not-found, type (file/dir), size in bytes.
    """
    return check_file_exists(file_path)


@mcp.tool()
def archim8_read_log_file(log_name: str, lines: int = 50) -> str:
    """Read the last N lines of a named Archim8 log file.

    Searches within allowed log directories:
      - 05_deliver/input/01_ingest/
      - 02_store/neo4j/docker/logs/

    Args:
        log_name: Plain filename (no path separators), e.g. "jdeps-output.txt".
        lines:    Number of lines to return (default 50, max 200).

    Returns:
        The last `lines` lines of the log, or an error message.
    """
    return read_log_file(log_name, lines)


@mcp.tool()
def archim8_check_docker_health(container_names: str) -> str:
    """Check health and running status of Archim8 Docker containers.

    Allowed containers: archim8-neo4j, archim8-jqa, neo4j.

    Args:
        container_names: Comma-separated container names.

    Returns:
        Markdown table with Name, Status, Health, Ports.
    """
    return check_docker_health(container_names)


@mcp.tool()
def archim8_generate_mermaid_diagram(diagram_type: str) -> str:
    """Generate a Mermaid diagram from the Archim8 architecture views and write it to disk.

    Reads pre-generated views from 05_deliver/output/views/ and writes .mmd files
    to 05_deliver/output/diagrams/. Run `make generate-views` first if the graph
    has changed.

    ⚠️  WRITE-PATH TOOL — writes files to 05_deliver/output/diagrams/.
    Confirm with user before calling.

    Supported diagram types:
      messaging       — C4Component diagram of the messaging framework
      layer-overview  — Flowchart of all layers with live cross-layer edge counts
      violations      — Directed graph of upward-coupling boundary violations
      all             — All three diagrams

    Args:
        diagram_type: One of "messaging", "layer-overview", "violations", "all".

    Returns:
        Paths of written .mmd files, or an error message.
    """
    return generate_mermaid_diagram(diagram_type)


# ---------------------------------------------------------------------------
# Register write-path tools (Human Anchor applies — always confirm first)
# ---------------------------------------------------------------------------

@mcp.tool()
def archim8_run_make_target(target: str) -> str:
    """Run an allowlisted Archim8 Makefile target.

    ⚠️  WRITE-PATH TOOL — HUMAN ANCHOR APPLIES.
    Before calling this tool, explicitly state what the target will do,
    what it will change, and what cannot be undone. Wait for user confirmation.

    Allowlisted targets:
      Infrastructure: docker-up, docker-down, docker-restart, docker-logs, neo4j-wait
      Ingestion:      jdeps, jdeps-pipeline, jdeps-filter
      jQAssistant:    jqa-install, jqa-scan, jqa-analyze, jqa-pipeline, jqa-reset,
                      jqa-verify, jqa-export
      Neo4j:          neo4j-init, neo4j-migrate, neo4j-ingest, neo4j-setup,
                      neo4j-export, neo4j-verify
      Generation:     generate-views, generate-diagrams, generate-all, generate-pipeline
      Composite:      ingest-pipeline, full-pipeline
      Info:           help

    Args:
        target: The Makefile target name.

    Returns:
        Combined stdout/stderr output, or an error message.
    """
    return run_make_target(target)


@mcp.tool()
def archim8_apply_cypher_migration(cypher_file: str) -> str:
    """Execute a Cypher migration script against Neo4j to update schema or seed data.

    ⚠️  WRITE-PATH TOOL — HUMAN ANCHOR APPLIES.
    Before calling this tool, state: what file will be executed, what schema changes
    it makes, and that it cannot easily be undone. Wait for user confirmation.

    The file must reside under 02_store/neo4j/config/schema/ (path-gated).
    Permitted operations: CREATE/MERGE/SET constraints, indexes, seed data.

    Args:
        cypher_file: Workspace-relative path, e.g.
                     "02_store/neo4j/config/schema/001_constraints.cypher".

    Returns:
        Summary of statements executed and rows affected, or an error message.
    """
    return run_cypher_migration(cypher_file)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
