#!/usr/bin/env python3
"""
Archim8 Phase 7 — Rule Generator

Reads 01_ingest/jqassistant/config/layers.yaml and produces:

  1. 01_ingest/jqassistant/rules/baseline/generated-constraints.xml
     jQAssistant Cypher concepts (layer labelling) and constraints (upward
     dependency checks) — replaces any hand-written baseline.

  2. 01_ingest/jqassistant/config/constraint-context.yaml
     Human-readable architectural context for each constraint ID, loaded
     by jqa_violations_report.py in place of the hardcoded CONSTRAINT_CONTEXT.

  3. Updates 01_ingest/jqassistant/config/jqassistant.yml
     Replaces the groups: entry with the new namespace group ID.

Usage:
    python 01_ingest/jqassistant/scripts/jqa_generate_rules.py
    make jqa-generate-rules

Does NOT require Neo4j to be running — reads only layers.yaml.
Run jqa_discover_layers.py first if layers.yaml does not yet exist.
"""

import os
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone
from textwrap import indent

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR     = Path(__file__).resolve().parent
JQA_DIR        = SCRIPT_DIR.parent
CONFIG_DIR     = JQA_DIR / "config"
RULES_DIR      = JQA_DIR / "rules" / "baseline"
LAYERS_YAML    = CONFIG_DIR / "layers.yaml"
OUTPUT_XML     = RULES_DIR / "generated-constraints.xml"
OUTPUT_CONTEXT = CONFIG_DIR / "constraint-context.yaml"
JQA_YML        = CONFIG_DIR / "jqassistant.yml"


# ---------------------------------------------------------------------------
# Name derivation helpers
# ---------------------------------------------------------------------------

def app_id(name: str) -> str:
    """'My App' → 'MyApp'"""
    return re.sub(r"\s+", "", name.strip().title())


def layer_label(app: str, layer_id: str) -> str:
    """Label applied to Neo4j nodes. 'MyApp' + 'common' → 'MyApp_Common'"""
    return f"{app}_{layer_id.replace('-', '_').title()}"


def constraint_id(app: str, lower_id: str) -> str:
    """'MyApp' + 'common' → 'MyApp:CommonMustNotDependOnHigherLayers'"""
    name_part = lower_id.replace("-", "_").title().replace("_", "")
    return f"{app}:{name_part}MustNotDependOnHigherLayers"


def concept_id(app: str, layer_id: str) -> str:
    """'MyApp' + 'common' → 'MyApp:CommonLayer'"""
    name_part = layer_id.replace("-", "_").title().replace("_", "")
    return f"{app}:{name_part}Layer"


def group_id(app: str) -> str:
    return f"{app}:Default"


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------

def prefix_where_clause(patterns: list[str], alias: str = "a") -> str:
    """Build Cypher WHERE clause for multiple prefix patterns."""
    conditions = [f"{alias}.artifactId STARTS WITH '{p}'" for p in patterns]
    return " OR ".join(f"({c})" for c in conditions)


def generate_concept(app: str, layer: dict, maven_group: str) -> str:
    """Generate one <concept> XML element for a layer."""
    cid    = concept_id(app, layer["id"])
    label  = layer_label(app, layer["id"])
    desc   = layer.get("description") or f"{layer['id'].title()} layer modules."
    pats   = layer.get("prefix_patterns", [f"{layer['id']}-"])
    where  = prefix_where_clause(pats)
    order_val = layer.get("order", "?")
    group_filter = f"a.groupId = '{maven_group}' AND " if maven_group else ""

    return f"""\
  <concept id="{cid}">
    <description>Tag {layer['id']}-* Maven artifacts and :Jar nodes as :{label} (Layer {order_val}). {desc}</description>
    <cypher><![CDATA[
      MATCH (a:Maven:Artifact)
      WHERE {group_filter}({where})
      SET a:{label}
      WITH a
      OPTIONAL MATCH (j:Jar)
      WHERE j.name = a.artifactId + '.jar' OR j.name = a.artifactId
      SET j:{label}
      RETURN count(a) AS taggedArtifacts
    ]]></cypher>
  </concept>"""


def generate_constraint(
    app: str,
    lower: dict,
    higher_layers: list[dict],
) -> str:
    """Generate one <constraint> checking that `lower` does not depend on any `higher_layers`."""
    cid         = constraint_id(app, lower["id"])
    lower_label = layer_label(app, lower["id"])
    lower_ord   = lower.get("order", "?")

    requires = "\n".join(
        f'    <requiresConcept refId="{concept_id(app, h["id"])}"/>'
        for h in higher_layers
    )
    requires = f'    <requiresConcept refId="{concept_id(app, lower["id"])}"/>\n' + requires

    # Build WHERE clause: to:Layer2 OR to:Layer3 ...
    where_parts = [f"to:{layer_label(app, h['id'])}" for h in higher_layers]
    where_clause = "\n         OR ".join(where_parts)

    # Build CASE for forbiddenLayer column
    case_lines = [
        f"          WHEN to:{layer_label(app, h['id']):<30} THEN 'Layer{h['order']}:{h['id'].replace(\"-\", \"_\").title()}'"
        for h in higher_layers
    ]
    case_block = "\n".join(case_lines)

    desc_layers = ", ".join(f"{h['id']} (order {h['order']})" for h in higher_layers)

    return f"""\
  <constraint id="{cid}" severity="major">
{requires}
    <description>{lower['id']} (order {lower_ord}) must not depend on higher-order layers: {desc_layers}.</description>
    <cypher><![CDATA[
      MATCH (from:Jar:{lower_label})-[r:DEPENDS_ON {{layer:'jdeps'}}]->(to:Jar)
      WHERE {where_clause}
      RETURN
        from.name AS violatingJar,
        to.name   AS forbiddenDependency,
        CASE
{case_block}
        END AS forbiddenLayer
      ORDER BY violatingJar, forbiddenLayer
    ]]></cypher>
  </constraint>"""


def generate_xml(app: str, maven_group: str, layers: list[dict]) -> str:
    """Generate the complete baseline XML."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gid = group_id(app)

    # Sort layers by order for consistent output
    sorted_layers = sorted(layers, key=lambda l: l.get("order", 99))

    # --- Concepts ---
    concepts = "\n\n".join(
        generate_concept(app, layer, maven_group) for layer in sorted_layers
    )

    # --- Constraints (each lower layer must not depend on any higher layer) ---
    constraints_xml = []
    for i, lower in enumerate(sorted_layers):
        higher = [h for h in sorted_layers if h.get("order", 99) > lower.get("order", 0)]
        if higher:
            constraints_xml.append(generate_constraint(app, lower, higher))
    constraints = "\n\n".join(constraints_xml)

    # --- Group includes ---
    concept_includes = "\n".join(
        f'    <includeConcept refId="{concept_id(app, l["id"])}"/>'
        for l in sorted_layers
    )
    constraint_includes = "\n".join(
        f'    <includeConstraint refId="{constraint_id(app, l["id"])}"/>'
        for l in sorted_layers[:-1]  # last layer (highest) has no upward violations
    )

    return f"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!--
  {app} Architecture Layer Rules
  Generated by jqa_generate_rules.py — {ts}
  Source: 01_ingest/jqassistant/config/layers.yaml

  DO NOT EDIT MANUALLY — regenerate with: make jqa-generate-rules

  Group: {gid} — includes all {len(sorted_layers)} layer concepts + {len(constraints_xml)} constraints.
  Reference with:  groups: [{gid}]  in jqassistant.yml
-->
<jqassistant-rules xmlns="http://schema.jqassistant.com/rule/v1.8">

  <!-- ======= Group ======= -->

  <group id="{gid}">
{concept_includes}
{constraint_includes}
  </group>


  <!-- ======= Concepts (layer labelling) ======= -->

{concepts}


  <!-- ======= Constraints (upward dependency checks) ======= -->

{constraints}

</jqassistant-rules>
"""


# ---------------------------------------------------------------------------
# Constraint context YAML generation
# ---------------------------------------------------------------------------

_ORDINAL = {1: "foundation", 2: "adapter", 3: "service", 4: "framework",
            5: "runtime", 6: "management", 7: "orchestration"}


def layer_role(layer: dict) -> str:
    order = layer.get("order", 0)
    return _ORDINAL.get(order, f"layer {order}")


def generate_context_entry(app: str, lower: dict, higher_layers: list[dict]) -> dict:
    """Generate a constraint context dict entry for one lower layer."""
    cid = constraint_id(app, lower["id"])
    low_name  = lower["id"]
    low_role  = layer_role(lower)
    high_desc = ", ".join(h["id"] for h in higher_layers)

    return {
        "rule": (
            f"{low_name} modules (order {lower.get('order','?')}) must not depend on "
            f"higher-order layers: {high_desc}."
        ),
        "layers_involved": (
            f"Layer {lower.get('order','?')}: {low_name} → upward to "
            + ", ".join(f"Layer {h.get('order','?')}: {h['id']}" for h in higher_layers)
        ),
        "arch_why": (
            f"The {low_name} layer acts as the {low_role} of the stack — it is designed to be "
            f"consumed by higher layers, not to consume them. Once a {low_name} module "
            f"imports from {higher_layers[0]['id'] if higher_layers else 'a higher layer'}, "
            f"the layering contract breaks: the foundation now has knowledge of the layers "
            f"built on top of it, making independent reasoning, testing, and evolution of "
            f"either layer significantly harder."
        ),
        "practical_impact": (
            f"Unit testing a {low_name} utility now requires bootstrapping higher-layer "
            f"infrastructure it was never designed to know about. Build times grow because "
            f"{low_name} can no longer be compiled in isolation. Any change to {high_desc} "
            f"must also be audited against {low_name} — turning independent work streams "
            f"into coordinated, higher-risk releases."
        ),
    }


# ---------------------------------------------------------------------------
# jqassistant.yml update
# ---------------------------------------------------------------------------

def update_jqa_yml(new_group: str) -> bool:
    """Replace the groups: entry in jqassistant.yml with the new group ID."""
    if not JQA_YML.exists():
        print(f"  [skip] {JQA_YML.name} not found — update groups: manually to [{new_group}]")
        return False

    content = JQA_YML.read_text(encoding="utf-8")
    # Pattern: match an indented `- SomeNamespace:Something` line under groups:
    updated, n = re.subn(
        r"([ \t]+groups:\s*\n)((?:[ \t]+-[ \t]+\S+\n?)+)",
        lambda m: m.group(1) + f"{' ' * 6}- {new_group}\n",
        content,
    )
    if n == 0:
        print(f"  [warn] Could not auto-update groups: in {JQA_YML.name}")
        print(f"         Set manually: groups: [{new_group}]")
        return False

    JQA_YML.write_text(updated, encoding="utf-8")
    print(f"  [done] {JQA_YML.name}: groups updated to [{new_group}]")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Archim8 Phase 7 — generate jQA rules + context from layers.yaml"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print generated XML to stdout without writing files")
    args = parser.parse_args()

    if not LAYERS_YAML.exists():
        print(f"ERROR: {LAYERS_YAML} not found.")
        print("       Run: make jqa-discover-layers")
        sys.exit(1)

    data = yaml.safe_load(LAYERS_YAML.read_text(encoding="utf-8"))
    app_cfg     = data.get("app", {})
    app_name    = app_cfg.get("name", os.environ.get("ARCHIM8_TARGET_APP", "App"))
    app         = app_cfg.get("id") or app_id(app_name)
    maven_group = app_cfg.get("maven_group", "")
    layers      = data.get("layers", [])

    if not layers:
        print("ERROR: layers.yaml has no `layers:` entries.")
        sys.exit(1)

    # Validate that all orders are set and unique
    orders = [l.get("order") for l in layers]
    if any(o is None for o in orders):
        print("ERROR: One or more layers have no `order` set in layers.yaml.")
        print("       Set `order` for each layer and re-run.")
        sys.exit(1)

    print(f"  [config] app={app_name}  id={app}  maven_group={maven_group or '(not set)'}")
    print(f"  [layers] {len(layers)} layers: " +
          ", ".join(f"{l['id']}(order {l.get('order','?')})" for l in sorted(layers, key=lambda x: x.get("order", 99))))

    # Generate XML
    xml = generate_xml(app, maven_group, layers)

    if args.dry_run:
        print("\n--- GENERATED XML ---\n")
        print(xml)
        return

    RULES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_XML.write_text(xml, encoding="utf-8")
    print(f"  [done] {OUTPUT_XML.name}")

    # Generate constraint-context.yaml
    sorted_layers = sorted(layers, key=lambda l: l.get("order", 99))
    ctx = {}
    for i, lower in enumerate(sorted_layers):
        higher = [h for h in sorted_layers if h.get("order", 99) > lower.get("order", 0)]
        if higher:
            cid = constraint_id(app, lower["id"])
            ctx[cid] = generate_context_entry(app, lower, higher)

    OUTPUT_CONTEXT.write_text(
        yaml.dump(ctx, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"  [done] {OUTPUT_CONTEXT.name}")

    # Update jqassistant.yml
    gid = group_id(app)
    update_jqa_yml(gid)

    print()
    print(f"  Next steps:")
    print(f"    1. Run:  make jqa-analyze              (applies new rules to graph)")
    print(f"    2. Run:  make jqa-violations-report    (generates health report)")
    print(f"    Note: the generated XML is committed to git — it documents architectural intent.")


if __name__ == "__main__":
    main()
