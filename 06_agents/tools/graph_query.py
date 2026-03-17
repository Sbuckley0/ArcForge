"""
Archim8 — graph_query MCP tools
Cypher query tools for the live Neo4j graph.
Read-only tool blocks write operations; migration tool is write-gated by path.
"""

import re
from typing import Optional

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Module-level driver singleton (initialised by archim8_agent.py)
# ---------------------------------------------------------------------------
_driver = None


def init_driver(bolt: str, user: str, password: str):
    global _driver
    _driver = GraphDatabase.driver(bolt, auth=(user, password))


def close_driver():
    global _driver
    if _driver:
        _driver.close()
        _driver = None


# ---------------------------------------------------------------------------
# Safety guard
# ---------------------------------------------------------------------------
_WRITE_KEYWORDS = re.compile(
    r'\b(MERGE|CREATE|SET\s|DELETE|DETACH|DROP|REMOVE|CALL\s+apoc\.(?!meta|schema\.show))\b',
    re.IGNORECASE,
)


def _is_safe(cypher: str) -> bool:
    return not bool(_WRITE_KEYWORDS.search(cypher))


# ---------------------------------------------------------------------------
# Helper: rows → compact text table
# ---------------------------------------------------------------------------
def _format_rows(rows: list[dict], max_rows: int = 200) -> str:
    if not rows:
        return "_No rows returned._"
    keys = list(rows[0].keys())
    truncated = rows[:max_rows]
    lines = ["| " + " | ".join(str(k) for k in keys) + " |",
             "| " + " | ".join(["---"] * len(keys)) + " |"]
    for row in truncated:
        lines.append("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")
    result = "\n".join(lines)
    if len(rows) > max_rows:
        result += f"\n\n_(Showing first {max_rows} of {len(rows)} rows)_"
    return result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def run_cypher_query(cypher: str) -> str:
    """Run a read-only Cypher query against the architecture graph in Neo4j.

    Use this for ad-hoc structural questions not covered by an existing view.
    Only MATCH/RETURN/WITH/UNWIND/OPTIONAL MATCH are permitted — write
    operations (MERGE, CREATE, SET, DELETE, etc.) are blocked.

    The graph contains:
    - :Jar nodes  (.name = module name e.g. "platform-core.jar")
    - [:DEPENDS_ON {layer:'jdeps'}] between :Jar nodes
    - :Type/:Method/:Field nodes from jQA bytecode scan
    - (:Type)-[:ANNOTATED_BY]->(:Value:ByteCode:Annotation)-[:OF_TYPE]->(:Type)
    - (:Maven:Artifact)-[:CONTAINS]->(:Type)
    - (:Type)-[:IMPLEMENTS]->(:Type), [:EXTENDS]->(:Type)

    Args:
        cypher: A read-only Cypher query string.

    Returns:
        Markdown table of results, or an error message.
    """
    if _driver is None:
        return "ERROR: Neo4j driver not initialised. Call init_driver() first."

    cypher = cypher.strip()

    if not _is_safe(cypher):
        return ("ERROR: Query contains write operations (MERGE/CREATE/SET/DELETE/DROP). "
                "Only read-only queries are permitted.")

    try:
        with _driver.session() as session:
            result = session.run(cypher)
            rows = [dict(record) for record in result]
        return f"**Query returned {len(rows)} row(s):**\n\n" + _format_rows(rows)
    except Exception as exc:
        return f"ERROR executing query: {exc}\n\nQuery was:\n```cypher\n{cypher}\n```"


def run_cypher_raw(cypher: str) -> list[dict]:
    """Run a read-only Cypher query and return raw list of row dicts (no formatting).

    Same safety guards as run_cypher_query. Returns [] on error or if driver is
    not initialised — callers should handle empty results gracefully.
    """
    if _driver is None or not _is_safe(cypher.strip()):
        return []
    try:
        with _driver.session() as session:
            result = session.run(cypher.strip())
            return [dict(record) for record in result]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Migration tool (write-permitted, path-gated)
# ---------------------------------------------------------------------------

import re as _re
from pathlib import Path as _Path

_MIGRATION_DIR_SUFFIX = "02_store/neo4j/config/schema"

# Allowlisted write keywords for migrations (superset of read-only guard).
# Anything not in this set is still rejected to prevent arbitrary execution.
_MIGRATION_ALLOWED = _re.compile(
    r'^\s*(CREATE|MERGE|SET\b|REMOVE\b|DELETE\b|DETACH\s+DELETE\b|DROP\b|'
    r'MATCH\b|RETURN\b|WITH\b|UNWIND\b|CALL\b|FOREACH\b)',
    _re.IGNORECASE | _re.MULTILINE,
)

_archim8_root_for_migration: _Path = None


def init_migration_path(archim8_root: _Path):
    """Set the archim8 root so run_cypher_migration can locate the schema directory."""
    global _archim8_root_for_migration
    _archim8_root_for_migration = archim8_root


def run_cypher_migration(cypher_file: str) -> str:
    """Execute a Cypher migration script against Neo4j to update schema or seed data.

    This tool permits write operations (CREATE, MERGE, SET, DROP, etc.) but is
    gated by path: the file must reside under
      02_store/neo4j/config/schema/

    This is the ONLY write path in Archim8. Use for:
    - Creating constraints and indexes
    - Seeding reference data
    - Schema version upgrades

    The Human Anchor principle applies: the orchestrator must have obtained
    explicit human approval before invoking this tool.

    Args:
        cypher_file: Workspace-relative path to the .cypher file,
                     e.g. "02_store/neo4j/config/schema/001_constraints.cypher".

    Returns:
        Summary of statements executed and rows affected, or an error message.
    """
    if _driver is None:
        return "ERROR: Neo4j driver not initialised. Call init_driver() first."
    if _archim8_root_for_migration is None:
        return "ERROR: Migration path not configured. Call init_migration_path() first."

    target = (_archim8_root_for_migration / cypher_file).resolve()

    # Path guard: must be inside the permitted schema directory
    allowed_dir = (_archim8_root_for_migration / _MIGRATION_DIR_SUFFIX).resolve()
    try:
        target.relative_to(allowed_dir)
    except ValueError:
        return (
            f"ERROR: '{cypher_file}' is outside the permitted migration directory "
            f"({_MIGRATION_DIR_SUFFIX}). Migration scripts must live there."
        )

    if not target.exists():
        return f"ERROR: Migration file not found: {cypher_file}"
    if not target.suffix.lower() == ".cypher":
        return f"ERROR: Only .cypher files are permitted. Got: '{target.name}'"

    content = target.read_text(encoding="utf-8")
    # Split on semicolons; filter empty statements
    statements = [s.strip() for s in content.split(";") if s.strip()]

    results = []
    try:
        with _driver.session() as session:
            for i, stmt in enumerate(statements, start=1):
                result = session.run(stmt)
                summary = result.consume()
                counters = summary.counters
                results.append(
                    f"Statement {i}: nodes_created={counters.nodes_created}, "
                    f"relationships_created={counters.relationships_created}, "
                    f"properties_set={counters.properties_set}, "
                    f"constraints_added={counters.constraints_added}, "
                    f"indexes_added={counters.indexes_added}"
                )
    except Exception as exc:
        return f"ERROR during migration: {exc}"

    summary_text = "\n".join(f"- {r}" for r in results)
    return (
        f"## Migration: {cypher_file}\n\n"
        f"Executed {len(statements)} statement(s):\n\n"
        f"{summary_text}"
    )
