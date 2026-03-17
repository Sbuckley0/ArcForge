#!/usr/bin/env python3
"""
Archim8 Phase 7 — Layer Discovery

Queries Neo4j (after jqa-scan) to cluster :Jar nodes by name prefix, ranks
them by fan-in/fan-out heuristics, attempts a topological sort, and writes a
draft layers.yaml to 01_ingest/jqassistant/config/.

The only value a human MUST review is `order` — which layer sits above which.
The script pre-fills order from heuristics and flags any cycles that require
a judgment call.

Usage:
    python 01_ingest/jqassistant/scripts/jqa_discover_layers.py [--force]
    make jqa-discover-layers

Requires: Neo4j running with :Jar nodes populated (run jqa-scan first).
Output:   01_ingest/jqassistant/config/layers.yaml  (gitignored)
"""

import os
import re
import sys
import argparse
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

try:
    from neo4j import GraphDatabase
except ImportError:
    print("ERROR: neo4j driver not installed. Run: pip install neo4j")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).resolve().parent
JQA_DIR     = SCRIPT_DIR.parent
CONFIG_DIR  = JQA_DIR / "config"
OUTPUT_PATH = CONFIG_DIR / "layers.yaml"


# ---------------------------------------------------------------------------
# Name → prefix extraction
# ---------------------------------------------------------------------------
# Strip .jar suffix, then take hyphen-delimited segments until we have 1-2
# that meaningfully identify a module family.
#
# Examples:
#   common-config.jar        → common
#   database-core.jar        → database
#   message-queue-base.jar   → message-queue
#   control-center-core.jar  → control-center
#   runtime-cobol-base.jar   → runtime
#   platform-pekko-grpc.jar  → platform
#   transaction-database.jar → transaction-database
#
# Heuristic: if first segment is a single word and second segment is also a
# single word that together form a well-known compound (not a version or
# technical descriptor), keep both.  Otherwise use first segment only.

_TWO_SEGMENT_COMPOUNDS = {
    "message-queue", "control-center", "transaction-database",
    "common-pekko", "platform-api",
}


def extract_prefix(jar_name: str) -> str:
    """Extract module family prefix from a JAR file name."""
    name = re.sub(r"\.jar$", "", jar_name.lower())
    parts = name.split("-")
    if len(parts) < 2:
        return name
    two = f"{parts[0]}-{parts[1]}"
    if two in _TWO_SEGMENT_COMPOUNDS:
        return two
    # If second segment looks like a version (digit) or generic descriptor, skip it
    return parts[0]


# ---------------------------------------------------------------------------
# Neo4j queries
# ---------------------------------------------------------------------------

JARS_QUERY = """
MATCH (j:Jar)
RETURN j.name AS name
"""

DEPS_QUERY = """
MATCH (a:Jar)-[:DEPENDS_ON {layer:'jdeps'}]->(b:Jar)
RETURN a.name AS from_jar, b.name AS to_jar
"""

MAVEN_GROUPS_QUERY = """
MATCH (a:Maven:Artifact)
WHERE a.groupId IS NOT NULL AND a.groupId <> ''
RETURN a.groupId AS groupId, count(*) AS cnt
ORDER BY cnt DESC
LIMIT 10
"""


def get_driver(bolt: str, user: str, password: str):
    return GraphDatabase.driver(bolt, auth=(user, password))


def run(driver, cypher: str) -> list[dict]:
    with driver.session() as session:
        return [dict(r) for r in session.run(cypher)]


# ---------------------------------------------------------------------------
# Graph analysis
# ---------------------------------------------------------------------------

def detect_maven_group(driver) -> str:
    """Auto-detect the primary Maven group ID of the target application."""
    rows = run(driver, MAVEN_GROUPS_QUERY)
    if not rows:
        return ""
    # Skip obvious framework groups (org.*, com.fasterxml.*, etc.)
    for row in rows:
        gid = row["groupId"]
        if not any(gid.startswith(skip) for skip in [
            "org.springframework", "com.fasterxml", "org.junit", "org.slf4j",
            "io.micrometer", "ch.qos", "org.apache", "com.google", "io.opentelemetry",
        ]):
            return gid
    return rows[0]["groupId"]


def build_groups(jar_names: list[str]) -> dict[str, list[str]]:
    """Map prefix → list of JAR names."""
    groups: dict[str, list[str]] = defaultdict(list)
    for name in jar_names:
        prefix = extract_prefix(name)
        groups[prefix].append(name)
    return dict(groups)


def build_group_graph(
    groups: dict[str, list[str]],
    deps: list[dict],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """
    Build group-level directed graph from JAR-level dependencies.
    Returns: (successors, predecessors) where successors[A] = set of groups that A depends on.
    """
    jar_to_group = {}
    for prefix, jars in groups.items():
        for j in jars:
            jar_to_group[j] = prefix

    successors: dict[str, set[str]] = defaultdict(set)
    predecessors: dict[str, set[str]] = defaultdict(set)

    for dep in deps:
        from_g = jar_to_group.get(dep["from_jar"])
        to_g   = jar_to_group.get(dep["to_jar"])
        if from_g and to_g and from_g != to_g:
            successors[from_g].add(to_g)
            predecessors[to_g].add(from_g)

    # Ensure all groups have entries even if no cross-group deps
    for g in groups:
        successors.setdefault(g, set())
        predecessors.setdefault(g, set())

    return dict(successors), dict(predecessors)


def detect_cycles(successors: dict[str, set[str]]) -> list[tuple[str, str]]:
    """Return list of (A, B) pairs where A depends on B AND B depends on A."""
    cycles = []
    groups = list(successors.keys())
    for i, a in enumerate(groups):
        for b in groups[i+1:]:
            if b in successors.get(a, set()) and a in successors.get(b, set()):
                cycles.append((a, b))
    return cycles


def topological_sort(
    groups: list[str],
    successors: dict[str, set[str]],
    cycles: list[tuple[str, str]],
) -> dict[str, int]:
    """
    Assign order values 1..N.
    Layers with no inbound dependencies from non-cycle partners get lower order numbers.
    Kahn's algorithm on a DAG produced by removing one edge from each cycle.

    Returns dict: group → order (1 = foundation, N = top of stack).
    Convention matches the arch intent: low-order layers are depended UPON.
    So we rank by "how many others depend on me" — high fan-in = low order.
    """
    # Compute fan_in per group (count of other groups that depend on this group)
    fan_in:  dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    for g, deps in successors.items():
        fan_out[g] = len(deps)
        for d in deps:
            fan_in[d] += 1

    # Sort by fan_in descending (most depended-upon = foundation = order 1)
    sorted_groups = sorted(groups, key=lambda g: (-fan_in[g], fan_out[g], g))

    order = {}
    for i, g in enumerate(sorted_groups, start=1):
        order[g] = i

    return order, dict(fan_in), dict(fan_out)


def confidence(fan_in: int, fan_out: int) -> str:
    """Heuristic confidence for the proposed order value."""
    if fan_in > 10 and fan_out <= 3:
        return "high"
    if fan_in <= 2 and fan_out > 10:
        return "high"
    if fan_in <= 1 and fan_out <= 1:
        return "low"   # isolated module — unclear
    return "medium"


# ---------------------------------------------------------------------------
# YAML generation
# ---------------------------------------------------------------------------

def build_yaml_doc(
    app_name: str,
    maven_group: str,
    groups: dict[str, list[str]],
    order: dict[str, int],
    fan_in: dict[str, int],
    fan_out: dict[str, int],
    cycles: list[tuple[str, str]],
) -> str:
    """Build the layers.yaml content as a string."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    app_id = re.sub(r"\s+", "", app_name.strip().title())  # "My App" → "MyApp"

    lines = [
        f"# Archim8 layer model — generated {ts}",
        "#",
        "# Review `order` values to reflect your architectural intent:",
        "#   Lower number = foundation (depended upon by many).",
        "#   Higher number = orchestration/management (depends on many).",
        "# Heuristic: high fan_in → low order. High fan_out → high order.",
        "#",
        "# Edit `prefix_patterns` if your module naming doesn't follow the auto-detected prefix.",
        "# Multiple patterns are OR'd together.",
        "#",
        "# Run `make jqa-generate-rules` when satisfied.",
        "",
        "app:",
        f"  name: {app_name}",
        f"  id: {app_id}       # auto-derived — do not edit",
        f"  maven_group: {maven_group or 'UNKNOWN — set manually'}",
        "",
        "layers:",
    ]

    sorted_groups = sorted(groups.keys(), key=lambda g: order.get(g, 99))
    for g in sorted_groups:
        fi = fan_in.get(g, 0)
        fo = fan_out.get(g, 0)
        conf = confidence(fi, fo)
        ord_val = order.get(g, 99)
        in_cycle = any(g in pair for pair in cycles)
        note = "  # ⚠️  CYCLE DETECTED — review manually" if in_cycle else ""

        lines += [
            f"  - id: {g}",
            f"    order: {ord_val}{note}",
            f"    prefix_patterns:",
            f"      - {g}-",
            f"    description: \"\"",
            f"    heuristic_fan_in: {fi}    # {fi} other module families depend on this",
            f"    heuristic_fan_out: {fo}    # this family depends on {fo} others",
            f"    heuristic_confidence: {conf}",
            "",
        ]

    if cycles:
        lines += [
            "# ---------------------------------------------------------------------------",
            "# CYCLES DETECTED — bi-directional dependencies between these module pairs.",
            "# The proposed `order` values for cyclic pairs are a best guess.",
            "# Review the specific JARs below and decide which module belongs at higher order.",
            "# ---------------------------------------------------------------------------",
            "# cycles:",
        ]
        for a, b in cycles:
            lines.append(f"#   - [{a}, {b}]")
        lines.append("")
    else:
        lines += [
            "# No cycles detected. Proposed ordering confidence: based on heuristics above.",
            "",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Archim8 Phase 7 — discover layer structure from live Neo4j graph"
    )
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing layers.yaml")
    parser.add_argument("--bolt", default=os.environ.get("ARCHIM8_NEO4J_BOLT", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("ARCHIM8_NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("ARCHIM8_NEO4J_PASSWORD", "password"))
    args = parser.parse_args()

    app_name = os.environ.get("ARCHIM8_TARGET_APP", "YourAppName")

    if OUTPUT_PATH.exists() and not args.force:
        print(f"  [skip] {OUTPUT_PATH.name} already exists. Use --force to overwrite.")
        print(f"         Edit layers.yaml and run: make jqa-generate-rules")
        sys.exit(0)

    print(f"  [connect] Neo4j at {args.bolt} ...")
    driver = get_driver(args.bolt, args.user, args.password)

    try:
        print("  [query] loading :Jar nodes ...")
        jars = [r["name"] for r in run(driver, JARS_QUERY) if r["name"]]
        if not jars:
            print("ERROR: No :Jar nodes found. Run jqa-scan first.")
            sys.exit(1)
        print(f"         {len(jars)} JAR nodes found")

        print("  [query] loading DEPENDS_ON edges ...")
        deps = run(driver, DEPS_QUERY)
        print(f"         {len(deps)} dependency edges found")

        print("  [query] detecting Maven group ...")
        maven_group = detect_maven_group(driver)
        print(f"         maven_group = {maven_group or '(none detected)'}")
    finally:
        driver.close()

    print("  [analyse] clustering JARs by prefix ...")
    groups = build_groups(jars)
    print(f"           {len(groups)} module families: {', '.join(sorted(groups))}")

    successors, predecessors = build_group_graph(groups, deps)
    cycles = detect_cycles(successors)

    if cycles:
        print(f"  [warn] {len(cycles)} cycle(s) detected: ", end="")
        print(", ".join(f"{a}↔{b}" for a, b in cycles))
        print("         These pairs have dependencies in BOTH directions.")
        print("         Proposed ordering is a best guess — review layers.yaml before proceeding.")
    else:
        print("  [ok]   No cycles detected")

    order, fan_in, fan_out = topological_sort(list(groups.keys()), successors, cycles)

    print("  [propose] Layer ordering (lower = foundation):")
    for g in sorted(groups.keys(), key=lambda x: order.get(x, 99)):
        fi = fan_in.get(g, 0)
        fo = fan_out.get(g, 0)
        conf = confidence(fi, fo)
        cycle_flag = " ⚠️CYCLE" if any(g in pair for pair in cycles) else ""
        print(f"           order {order[g]:>2}  {g:<22}  fan_in={fi}  fan_out={fo}  ({conf}){cycle_flag}")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    yaml_content = build_yaml_doc(
        app_name, maven_group, groups, order, fan_in, fan_out, cycles
    )
    OUTPUT_PATH.write_text(yaml_content, encoding="utf-8")
    _print_completion_banner(ORDER_PATH=OUTPUT_PATH, cycles=cycles,
                             groups=groups, order=order,
                             fan_in=fan_in, fan_out=fan_out)


# ---------------------------------------------------------------------------
# Terminal output helpers
# ---------------------------------------------------------------------------

# ANSI colour codes — degrade gracefully if terminal doesn't support them
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_WHITE  = "\033[97m"
_RED    = "\033[91m"
_BG_GRN = "\033[42m"
_BG_YLW = "\033[43m"
_BG_BLU = "\033[44m"


def _hyperlink(uri: str, label: str) -> str:
    """OSC 8 terminal hyperlink — clickable in Windows Terminal, VS Code, iTerm2."""
    return f"\033]8;;{uri}\033\\{label}\033]8;;\033\\"


def _file_link(path: "Path") -> str:
    """Return a clickable file:// hyperlink label for a Path."""
    uri = path.as_uri()
    return _hyperlink(uri, str(path))


def _conf_colour(conf: str) -> str:
    if conf == "high":
        return _GREEN
    if conf == "medium":
        return _YELLOW
    return _RED


def _print_completion_banner(ORDER_PATH, cycles, groups, order, fan_in, fan_out):
    has_cycles = bool(cycles)
    p = print  # alias

    p()
    p(f"  {_BG_GRN}{_WHITE}{_BOLD}  ✓ LAYER DISCOVERY COMPLETE  {_RESET}")
    p()

    # ── Layer table ──────────────────────────────────────────────────────────
    p(f"  {_BOLD}{_CYAN}Proposed layer ordering  {_DIM}(lower order = foundation, higher order = orchestration){_RESET}")
    p()
    col = f"  {_DIM}{'ORDER':<7}{'LAYER':<26}{'FAN-IN':>8}  {'FAN-OUT':<9}{'CONFIDENCE':<12}{'NOTE'}{_RESET}"
    p(col)
    p(f"  {'─'*72}")
    for g in sorted(groups.keys(), key=lambda x: order.get(x, 99)):
        fi   = fan_in.get(g, 0)
        fo   = fan_out.get(g, 0)
        conf = confidence(fi, fo)
        cc   = _conf_colour(conf)
        in_cycle = any(g in pair for pair in cycles)
        note = f"  {_YELLOW}⚠  CYCLE — review manually{_RESET}" if in_cycle else ""
        p(f"  {_WHITE}{_BOLD}  {order[g]:<5}{_RESET}"
          f"{_WHITE}{g:<26}{_RESET}"
          f"{_DIM}{fi:>8}  {fo:<9}{_RESET}"
          f"{cc}{conf:<12}{_RESET}"
          f"{note}")
    p()

    # ── Output file ──────────────────────────────────────────────────────────
    p(f"  {_BOLD}Generated:{_RESET}  {_CYAN}{_file_link(ORDER_PATH)}{_RESET}")
    p()

    # ── Optional review block ────────────────────────────────────────────────
    if has_cycles:
        p(f"  {_BG_YLW}  ⚠  ACTION REQUIRED  {_RESET}  "
          f"{_YELLOW}{_BOLD}Cycles detected — you must review layers.yaml before continuing.{_RESET}")
        p()
        p(f"  {_BOLD}Why:{_RESET}  A cycle means two module groups depend on each other in both directions.")
        p(f"        The graph cannot tell which one is 'above' the other — that is a design")
        p(f"        intent decision that only you can make.")
        p()
        p(f"  {_BOLD}What to do:{_RESET}")
        p(f"    1. Open  {_CYAN}{_file_link(ORDER_PATH)}{_RESET}")
        p(f"    2. Search for  {_YELLOW}⚠️  CYCLE DETECTED{_RESET}  entries")
        p(f"    3. Swap the {_BOLD}order:{_RESET} value between the two modules to reflect intent")
        p(f"       {_DIM}e.g. if 'system' depends on 'platform' by mistake — platform should be higher order{_RESET}")
        p()
        p(f"  {_DIM}Cycles found:{_RESET}")
        for a, b in cycles:
            p(f"    {_YELLOW}  {a}  ↔  {b}{_RESET}")
        p()
        next_cmd = "make jqa-generate-rules"
        p(f"  {_BOLD}When done:{_RESET}  run  {_CYAN}{_BOLD}{next_cmd}{_RESET}")

    else:
        p(f"  {_BG_BLU}  ★ NO CYCLES DETECTED  {_RESET}  "
          f"{_GREEN}{_BOLD}The proposed ordering is heuristically reliable.{_RESET}")
        p()
        p(f"  {_BOLD}Review is OPTIONAL.{_RESET}  "
          f"The ordering was inferred automatically from dependency counts in your graph.")
        p(f"  {_DIM}High fan-in → low order (foundation).  High fan-out → high order (orchestration).{_RESET}")
        p()
        p(f"  {_BOLD}Want to eyeball it?{_RESET}  Open: {_CYAN}{_file_link(ORDER_PATH)}{_RESET}")
        p(f"  {_DIM}Look at the `order` and `heuristic_confidence` fields.")
        p(f"  Change any `order` value if your arch intent differs from the heuristic.{_RESET}")
        p()
        next_cmd = "make jqa-generate-rules"
        p(f"  {_BG_GRN}{_WHITE}{_BOLD}  → Ready to continue  {_RESET}  "
          f"run  {_CYAN}{_BOLD}{next_cmd}{_RESET}")
        p(f"  {_DIM}(This generates the jQA XML rules and constraint context from layers.yaml){_RESET}")

    p()


if __name__ == "__main__":
    main()
