#!/usr/bin/env python3
"""
Archim8 Phase 4 — PlantUML C4 Diagram Generator
Queries Neo4j directly and writes two C4 container diagrams:
  - 05_deliver/output/arc-containers.puml  (full module topology)
  - 05_deliver/output/arc-cobol-emulation.puml  (COBOL subsystem)

Usage:
    python generate_plantuml.py [--force]
    python generate_plantuml.py --diagram containers
    python generate_plantuml.py --diagram cobol
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase
# ---------------------------------------------------------------------------
# Target application identity (override via env)
# ---------------------------------------------------------------------------
TARGET_APP = os.environ.get("ARCHIM8_TARGET_APP", "target application")
SCRIPT_DIR    = Path(__file__).resolve().parent
ARCHIM8_ROOT = SCRIPT_DIR.parents[2]
OUTPUT_DIR    = ARCHIM8_ROOT / "05_deliver" / "output"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

# Layer colour palette for C4
LAYER_COLOUR = {
    "control-center": "#7B2D8B",
    "platform":       "#1168BD",
    "runtime":        "#23A2B8",
    "database":       "#E67E22",
    "message-queue":  "#27AE60",
    "common":         "#7F8C8D",
    "system":         "#C0392B",
    "unknown":        "#BDC3C7",
}

LAYER_RANK = {
    "control-center": 5,
    "platform":       4,
    "runtime":        3,
    "database":       2,
    "message-queue":  2,
    "common":         1,
    "system":         0,
    "unknown":        0,
}

# ---------------------------------------------------------------------------
# Neo4j / Layer logic
# ---------------------------------------------------------------------------
def get_driver(bolt: str, user: str, password: str):
    return GraphDatabase.driver(bolt, auth=(user, password))


def classify_layer(module_name: str) -> str:
    name = module_name.lower()
    if name.startswith("control-center"): return "control-center"
    if name.startswith("platform"):       return "platform"
    if name.startswith("runtime"):        return "runtime"
    if name.startswith("database"):       return "database"
    if name.startswith("message-queue"):  return "message-queue"
    if name.startswith("common"):         return "common"
    if name.startswith("system"):         return "system"
    return "unknown"


def safe_id(name: str) -> str:
    """Convert module name to safe PlantUML identifier."""
    return name.replace("-", "_").replace(".", "_")


# ---------------------------------------------------------------------------
# Full container diagram
# ---------------------------------------------------------------------------
MODULE_DEPS_CYPHER = """
MATCH (from:Jar)-[r:DEPENDS_ON {layer:'jdeps'}]->(to:Jar)
WHERE NOT from.name STARTS WITH 'java.'
  AND NOT from.name STARTS WITH 'jdk.'
  AND NOT to.name STARTS WITH 'java.'
  AND NOT to.name STARTS WITH 'jdk.'
RETURN
  from.name AS fromModule,
  to.name   AS toModule
ORDER BY fromModule, toModule
"""

def generate_containers(driver, force: bool) -> str:
    out_path = OUTPUT_DIR / "arc-containers.puml"
    if not force and out_path.exists():
        print("  [skip] arc-containers.puml — already exists (use --force)")
        return str(out_path)

    print("  [query] loading module dependency graph ...")
    with driver.session() as session:
        rows = [dict(r) for r in session.run(MODULE_DEPS_CYPHER)]

    # Collect all modules and classify
    modules = set()
    for row in rows:
        modules.add(row["fromModule"])
        modules.add(row["toModule"])

    by_layer: dict[str, list[str]] = {}
    for m in sorted(modules):
        layer = classify_layer(m)
        by_layer.setdefault(layer, []).append(m)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        "@startuml arc-containers",
        "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml",
        "",
        f"' Archim8 generated — {ts}",
        "' Source: Neo4j jdeps graph",
        "' Do not edit manually",
        "",
        "LAYOUT_TOP_DOWN()",
        "skinparam wrapWidth 200",
        "skinparam maxMessageSize 150",
        "",
        f"title {TARGET_APP} Architecture — Module Dependency Graph",
        "",
    ]

    # Emit boundary blocks per layer (sorted by rank descending)
    layer_order = sorted(by_layer.keys(), key=lambda l: LAYER_RANK.get(l, 0), reverse=True)
    for layer in layer_order:
        colour = LAYER_COLOUR.get(layer, "#BDC3C7")
        lines.append(f'System_Boundary({safe_id(layer)}_boundary, "{layer.title()} Layer") {{')
        for mod in sorted(by_layer[layer]):
            lines.append(f'  Container({safe_id(mod)}, "{mod}", "Jar", $tags="{layer}")')
        lines.append("}")
        lines.append("")

    # Emit relationships
    lines.append("' Dependencies")
    for row in rows:
        fm = safe_id(row["fromModule"])
        tm = safe_id(row["toModule"])
        lines.append(f"Rel({fm}, {tm}, \"depends on\")")

    lines += ["", "@enduml", ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [done] arc-containers.puml → {len(rows)} edges, {len(modules)} modules")
    return str(out_path)


# ---------------------------------------------------------------------------
# COBOL emulation subsystem diagram
# ---------------------------------------------------------------------------
COBOL_CYPHER = """
MATCH (a:Jar)
WHERE a.name STARTS WITH 'runtime-cobol'
OPTIONAL MATCH (a)-[r:DEPENDS_ON {layer:'jdeps'}]->(dep:Jar)
WHERE NOT dep.name STARTS WITH 'java.'
  AND NOT dep.name STARTS WITH 'jdk.'
RETURN
  a.name   AS module,
  dep.name AS dependsOn
ORDER BY module, dependsOn
"""

def generate_cobol(driver, force: bool) -> str:
    out_path = OUTPUT_DIR / "arc-cobol-emulation.puml"
    if not force and out_path.exists():
        print("  [skip] arc-cobol-emulation.puml — already exists (use --force)")
        return str(out_path)

    print("  [query] loading COBOL subsystem ...")
    with driver.session() as session:
        rows = [dict(r) for r in session.run(COBOL_CYPHER)]

    cobol_mods = sorted({r["module"] for r in rows if r["module"]})
    ext_deps   = sorted({r["dependsOn"] for r in rows if r["dependsOn"] and not r["dependsOn"].startswith("runtime-cobol")})

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        "@startuml arc-cobol-emulation",
        "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml",
        "",
        f"' Archim8 generated — {ts}",
        "' Source: Neo4j jdeps graph — runtime-cobol-* subsystem",
        "' Do not edit manually",
        "",
        "LAYOUT_TOP_DOWN()",
        "",
        f"title {TARGET_APP} Architecture — COBOL Emulation Subsystem",
        "",
        'System_Boundary(cobol_boundary, "COBOL Emulation Runtime") {',
    ]
    for mod in cobol_mods:
        lines.append(f'  Container({safe_id(mod)}, "{mod}", "Jar")')
    lines += ["}", ""]

    if ext_deps:
        lines.append(f'System_Boundary(ext_boundary, "External {TARGET_APP} Dependencies") {{')
        for dep in ext_deps:
            layer = classify_layer(dep)
            lines.append(f'  Container({safe_id(dep)}, "{dep}", "Jar", $tags="{layer}")')
        lines += ["}", ""]

    lines.append("' Dependencies")
    emitted = set()
    for row in rows:
        if row["module"] and row["dependsOn"]:
            key = (row["module"], row["dependsOn"])
            if key not in emitted:
                lines.append(f'Rel({safe_id(row["module"])}, {safe_id(row["dependsOn"])}, "depends on")')
                emitted.add(key)

    lines += ["", "@enduml", ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [done] arc-cobol-emulation.puml → {len(cobol_mods)} modules, {len(ext_deps)} ext deps")
    return str(out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Archim8 PlantUML C4 generator")
    parser.add_argument("--diagram",  choices=["containers", "cobol", "all"], default="all")
    parser.add_argument("--force",    action="store_true")
    parser.add_argument("--bolt",     default=os.environ.get("ARCHIM8_NEO4J_BOLT", "bolt://localhost:7687"))
    parser.add_argument("--user",     default=os.environ.get("ARCHIM8_NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("ARCHIM8_NEO4J_PASSWORD", os.environ.get("ARCHIM8_NEO4J_PASS", "password")))
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to Neo4j at {args.bolt} ...")
    driver = get_driver(args.bolt, args.user, args.password)

    try:
        if args.diagram in ("containers", "all"):
            generate_containers(driver, args.force)
        if args.diagram in ("cobol", "all"):
            generate_cobol(driver, args.force)
    finally:
        driver.close()

    print(f"\nDiagrams written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
