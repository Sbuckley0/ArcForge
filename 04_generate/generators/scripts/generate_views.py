#!/usr/bin/env python3
"""
Archim8 Phase 4 — Semantic View Generator
Runs each Cypher query against Neo4j and writes structured Markdown views
with YAML frontmatter to 05_deliver/output/views/.

Usage:
    python generate_views.py [--view <name>] [--force]

Options:
    --view <name>   Generate a single named view only (default: all)
    --force         Re-generate even if view already exists in manifest
    --bolt <url>    Neo4j bolt URL (default: env ARCHIM8_NEO4J_BOLT or bolt://localhost:7687)
    --user <user>   Neo4j username (default: env ARCHIM8_NEO4J_USER or neo4j)
    --password <pw> Neo4j password (default: env ARCHIM8_NEO4J_PASSWORD or password)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Target application identity (override via env)
# ---------------------------------------------------------------------------
TARGET_APP = os.environ.get("ARCHIM8_TARGET_APP", "target application")

# ---------------------------------------------------------------------------
# Path resolution (relative to this script's location)
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
ARCHIM8_ROOT = SCRIPT_DIR.parents[2]          # scripts/ → generators/ → 04_generate/ → archim8/
QUERY_DIR    = ARCHIM8_ROOT / "03_query" / "cypher" / "library" / "jqa"
OUTPUT_DIR   = ARCHIM8_ROOT / "05_deliver" / "output" / "views"
MANIFEST_PATH = ARCHIM8_ROOT / "05_deliver" / "output" / "manifest.json"

# ---------------------------------------------------------------------------
# View registry — maps view name → query file + metadata
# ---------------------------------------------------------------------------
VIEWS = {
    "module-deps": {
        "query": "module-deps.cypher",
        "title": "Module Dependency Graph",
        "description": f"All {TARGET_APP} module-to-module dependencies, grouped by architectural layer.",
        "key_columns": ["fromModule", "fromLayer", "toModule", "toLayer"],
        "scope": f"all {TARGET_APP} Jar-to-Jar jdeps edges",
    },
    "grpc-services": {
        "query": "grpc-services.cypher",
        "title": "gRPC Service Inventory (Pekko gRPC)",
        "description": f"All {TARGET_APP} types annotated with @PekkoGrpcGenerated — the gRPC API surface. The app uses Apache Pekko gRPC as its primary API protocol.",
        "key_columns": ["artifact", "layer", "typeFqn", "typeKind"],
        "scope": "com.avanade.* types with @PekkoGrpcGenerated",
    },
    "pekko-http-api": {
        "query": "pekko-http-api.cypher",
        "title": "Pekko HTTP / REST API Surface",
        "description": "Modules that participate in the HTTP layer via dependency on platform-api-rest or common-pekko-http.",
        "key_columns": ["module", "layer", "httpDependency"],
        "scope": "jdeps edges to HTTP infrastructure JARs",
    },
    "spring-components": {
        "query": "spring-components.cypher",
        "title": "Spring Component Inventory",
        "description": "All @Service, @Repository, @Component, @Configuration, and @Entity types per module.",
        "key_columns": ["artifact", "layer", "annotation", "typeFqn"],
        "scope": "com.avanade.* types with Spring/JPA stereotype annotations",
    },
    "observability-coverage": {
        "query": "observability-coverage.cypher",
        "title": "Observability Coverage",
        "description": f"Which {TARGET_APP} modules use Micrometer, OpenTelemetry, or structured logging frameworks at the type level.",
        "key_columns": ["status", "artifact", "layer", "observabilityFramework"],
        "scope": "com.avanade.* types with DEPENDS_ON to observability frameworks",
    },
    "violations": {
        "query": "violations.cypher",
        "title": "Architecture Violations",
        "description": "All upward-coupling violations — modules depending on higher architectural layers.",
        "key_columns": ["fromModule", "fromLayer", "toModule", "toLayer", "violationType"],
        "scope": "jdeps edges crossing layer boundaries upward",
    },
    "key-abstractions": {
        "query": "key-abstractions.cypher",
        "title": "Key Abstractions",
        "description": f"Most-implemented {TARGET_APP} interfaces — the core architectural extension points and contracts.",
        "key_columns": ["kind", "typeFqn", "artifact", "layer", "score"],
        "scope": "com.avanade.* interfaces ranked by implementation count",
    },
    "cobol-subsystem": {
        "query": "cobol-subsystem.cypher",
        "title": "COBOL Emulation Subsystem",
        "description": "All runtime-cobol-* modules, their type inventories, and dependencies into other layers.",
        "key_columns": ["kind", "artifact", "typeCount"],
        "scope": "runtime-cobol-* artifacts",
    },
}


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------
def get_driver(bolt: str, user: str, password: str):
    return GraphDatabase.driver(bolt, auth=(user, password))


def run_query(driver, cypher: str) -> list[dict]:
    with driver.session() as session:
        result = session.run(cypher)
        return [dict(record) for record in result]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------
def render_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "_No data returned._\n"
    # Use columns from first row if key_columns doesn't match
    actual_cols = [c for c in columns if c in rows[0]] or list(rows[0].keys())
    header = "| " + " | ".join(actual_cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(actual_cols)) + " |"
    lines  = [header, sep]
    for row in rows:
        cells = [str(row.get(c, "")) for c in actual_cols]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def render_view(view_name: str, meta: dict, rows: list[dict], scan_ts: str) -> str:
    frontmatter = f"""---
view: {view_name}
title: {meta["title"]}
scope: {meta["scope"]}
generated: {scan_ts}
cypher: 03_query/cypher/library/jqa/{meta["query"]}
row_count: {len(rows)}
---"""

    body = f"""# {meta["title"]}

> **Archim8 generated view** — All data sourced from Neo4j graph. Do not edit manually.

**Scope:** {meta["scope"]}  
**Generated:** {scan_ts}  
**Rows:** {len(rows)}  
**Query:** `03_query/cypher/library/jqa/{meta["query"]}`

---

## Description

{meta["description"]}

---

## Data

"""
    body += render_table(rows, meta["key_columns"])

    if not rows:
        body += "\n> **Note:** No data matched this query. The view may need adjustments for this codebase.\n"

    return frontmatter + "\n\n" + body


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {"views": {}, "last_updated": ""}


def save_manifest(manifest: dict):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  manifest updated → {MANIFEST_PATH.relative_to(ARCHIM8_ROOT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Archim8 view generator")
    parser.add_argument("--view",     help="Generate single view by name")
    parser.add_argument("--force",    action="store_true", help="Re-generate even if up to date")
    parser.add_argument("--bolt",     default=os.environ.get("ARCHIM8_NEO4J_BOLT", "bolt://localhost:7687"))
    parser.add_argument("--user",     default=os.environ.get("ARCHIM8_NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("ARCHIM8_NEO4J_PASSWORD", os.environ.get("ARCHIM8_NEO4J_PASS", "password")))
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    scan_ts  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = load_manifest()

    target_views = {args.view: VIEWS[args.view]} if args.view else VIEWS
    if args.view and args.view not in VIEWS:
        print(f"ERROR: Unknown view '{args.view}'. Valid views: {', '.join(VIEWS)}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to Neo4j at {args.bolt} ...")
    driver = get_driver(args.bolt, args.user, args.password)

    errors = []
    for view_name, meta in target_views.items():
        out_path = OUTPUT_DIR / f"{view_name}.md"

        # Check manifest — skip if exists and not forced
        if not args.force and view_name in manifest["views"] and out_path.exists():
            print(f"  [skip] {view_name} — already generated (use --force to regenerate)")
            continue

        query_path = QUERY_DIR / meta["query"]
        if not query_path.exists():
            print(f"  [ERROR] Query file not found: {query_path}", file=sys.stderr)
            errors.append(view_name)
            continue

        cypher = query_path.read_text(encoding="utf-8")
        # Strip comment header lines (start with //)
        cypher_lines = [l for l in cypher.splitlines() if not l.strip().startswith("//")]
        cypher_clean = "\n".join(cypher_lines).strip()

        print(f"  [run]  {view_name} ...")
        try:
            rows = run_query(driver, cypher_clean)
        except Exception as e:
            print(f"  [ERROR] {view_name}: {e}", file=sys.stderr)
            errors.append(view_name)
            continue

        content = render_view(view_name, meta, rows, scan_ts)
        out_path.write_text(content, encoding="utf-8")

        manifest["views"][view_name] = {
            "file":       f"05_deliver/output/views/{view_name}.md",
            "generated":  scan_ts,
            "row_count":  len(rows),
            "cypher":     f"03_query/cypher/library/jqa/{meta['query']}",
            "scope":      meta["scope"],
        }
        print(f"  [done] {view_name} → {len(rows)} rows → {out_path.name}")

    save_manifest(manifest)
    driver.close()

    if errors:
        print(f"\nFailed views: {errors}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\nAll views generated. Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
