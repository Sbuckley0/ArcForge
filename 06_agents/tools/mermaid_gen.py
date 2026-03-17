"""
Archim8 — mermaid_gen MCP tool

Reads pre-generated architecture views and produces Mermaid .mmd diagram files.
Writes to 05_deliver/output/diagrams/.

Supported diagram types:
  messaging       — C4Component diagram of the messaging framework
  layer-overview  — Flowchart of layers with live cross-layer edge counts
  violations      — Directed graph of upward-coupling boundary violations
  all             — All three diagrams
"""

import os
import re
from pathlib import Path


def _load_app_fqn_prefix() -> str:
    """Load Maven group FQN prefix from layers.yaml or ARCHIM8_MAVEN_GROUP env."""
    try:
        import yaml as _yaml
        _ly = Path(__file__).parents[2] / "01_ingest" / "jqassistant" / "config" / "layers.yaml"
        if _ly.exists():
            data = _yaml.safe_load(_ly.read_text(encoding="utf-8"))
            group = (data.get("app", {}) or {}).get("maven_group", "")
            if group:
                return group.rstrip(".") + "."
    except Exception:
        pass
    env_group = os.environ.get("ARCHIM8_MAVEN_GROUP", "")
    return env_group.rstrip(".") + "." if env_group else ""


_APP_FQN_PREFIX = _load_app_fqn_prefix()

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_archim8_root: Path = None

SUPPORTED = ["messaging", "messaging-classes", "layer-overview", "violations"]


def init_paths(archim8_root: Path):
    global _archim8_root
    _archim8_root = archim8_root


# ---------------------------------------------------------------------------
# C4 legend colours — consistent across all CX diagrams
# Reference: https://c4model.com/  (Person, Software System, Container,
# Component, External Person, External Software System)
# ---------------------------------------------------------------------------

_C4_INIT = (
    "%%{init: {'theme': 'base', 'themeVariables': {"
    "'background': '#ffffff', "
    "'primaryColor': '#7DBEF2', "
    "'primaryTextColor': '#ffffff', "
    "'primaryBorderColor': '#4a8fb8', "
    "'lineColor': '#555555', "
    "'secondaryColor': '#ffffff', "
    "'tertiaryColor': '#ffffff'"
    "}}}%%"
)

# Init for C1–C3 flowchart-based architecture views.
# primaryTextColor controls subgraph title labels and edge label text; keep mid-grey.
_C3_INIT = (
    "%%{init: {'theme': 'base', 'themeVariables': {"
    "'background': '#ffffff', "
    "'primaryColor': '#ffffff', "
    "'primaryTextColor': '#555555', "
    "'lineColor': '#666666', "
    "'secondaryColor': '#f0f0f0', "
    "'tertiaryColor': '#f0f0f0', "
    "'edgeLabelBackground': '#ffffff'"
    "}}}%%"
)

# Init for C4 classDiagram code views.
# primaryColor fills all class header bars — set to framework blue so header + body unify.
# primaryTextColor must be dark (#333333) for readable edge labels;
# classDef color:#ffffff independently keeps class-box text white.
_C4_CLASS_INIT = (
    "%%{init: {'theme': 'base', 'themeVariables': {"
    "'background': '#ffffff', "
    "'primaryColor': '#7DBEF2', "
    "'primaryTextColor': '#333333', "
    "'primaryBorderColor': '#5B9BD5', "
    "'lineColor': '#666666', "
    "'secondaryColor': '#ffffff', "
    "'tertiaryColor': '#ffffff', "
    "'edgeLabelBackground': '#f8f8f8'"
    "}}}%%"
)

# Full C4 colour palette (Person → External System) — applied as classDefs in every classDiagram
# Strokes are a slightly darker shade of the fill so nodes have a visible, clean border.
_C4_CLASSDEF_PERSON = (
    "classDef c4person      fill:#1E4074,stroke:#122448,color:#ffffff,font-weight:bold"
)
_C4_CLASSDEF_SYSTEM = (
    "classDef c4system      fill:#3162AF,stroke:#1e3d6a,color:#ffffff,font-weight:bold"
)
_C4_CLASSDEF_CONTAINER = (
    "classDef c4container   fill:#52A2D8,stroke:#2d6f9c,color:#ffffff,font-weight:bold"
)
_C4_CLASSDEF_FRAMEWORK = (
    "classDef framework     fill:#7DBEF2,stroke:#5B9BD5,color:#ffffff,font-weight:bold"
)
_C4_CLASSDEF_EXT_PERSON = (
    "classDef c4extperson   fill:#6B6477,stroke:#4a4056,color:#ffffff,font-style:italic"
)
_C4_CLASSDEF_EXTERNAL = (
    "classDef external      fill:#8B8496,stroke:#5e5a68,color:#ffffff,font-style:italic"
)
_C4_CLASSDEF_VIOLATION = (
    "classDef violation  fill:#8B0000,stroke:#ff4444,color:#ffffff,font-weight:bold"
)

# Force-include framework types that may not surface via IMPLEMENTS/EXTENDS queries
_MQ_FORCE_INCLUDE: frozenset[str] = frozenset({
    _APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageMapper",
})

# Method/field names to skip when rendering class bodies (JDK noise)
_SKIP_MEMBER_NAMES: frozenset[str] = frozenset({
    "equals", "hashCode", "toString", "clone",
    "getClass", "wait", "notify", "notifyAll", "finalize",
})


# ---------------------------------------------------------------------------
# Legend helpers — render a visible legend inside the diagram
# ---------------------------------------------------------------------------

def _c4_legend_classDiagram() -> list[str]:
    """Full C4 colour-palette legend for classDiagram outputs (all 6 tiers).
    Legend items are empty-body classes — renders as simple colour swatches.
    """
    return [
        "    %% ── Legend ──",
        "    namespace Legend {",
        '        class _L1_["Person"]:::c4person { }',
        '        class _L2_["Software System"]:::c4system { }',
        '        class _L3_["Container"]:::c4container { }',
        '        class _L4_["Component"]:::framework { }',
        '        class _L5_["External Person"]:::c4extperson { }',
        '        class _L6_["External Software System"]:::external { }',
        "    }",
    ]


def _c4_legend_flowchart(items: list[tuple[str, str, str]]) -> list[str]:
    """Subgraph-based legend for flowchart outputs.
    items: list of (node_id, label, classDef_name)
    """
    rows = ['    subgraph _legend_["Legend"]', "        direction LR"]
    for nid, label, cls in items:
        rows.append(f'        {nid}["{label}"]:::{cls}')
    rows.append("    end")
    return rows


# ---------------------------------------------------------------------------
# View parser — reads 05_deliver/output/views/<name>.md into list of dicts
# ---------------------------------------------------------------------------

def _read_view_rows(view_name: str) -> list:
    if _archim8_root is None:
        return []
    view_file = _archim8_root / "05_deliver" / "output" / "views" / f"{view_name}.md"
    if not view_file.exists():
        return []
    content = view_file.read_text(encoding="utf-8")
    headers = None
    rows = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        parts = [p.strip() for p in stripped.strip("|").split("|")]
        if headers is None:
            headers = parts
        elif all(re.match(r"^-+$", p) for p in parts if p):
            continue  # separator row
        elif headers:
            rows.append(dict(zip(headers, parts)))
    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nid(name: str) -> str:
    """Convert a module/layer name to a safe Mermaid node ID."""
    return re.sub(r"[^a-zA-Z0-9]", "_", name.replace(".jar", ""))


_MODULE_DESC = {
    "message-queue-base.jar":      "MessageQueue interface + COBOL MQ options",
    "message-queue-ibmmq.jar":     "IBM MQ adapter",
    "message-queue-kafka.jar":     "Apache Kafka adapter",
    "common-messaging.jar":        "MessageKind enum",
    "platform-pekko-messages.jar": "MessageRoutes · MessageMapper · MessageServiceImpl",
}

# Desired top-to-bottom render order for layer-overview
_LAYER_ORDER = [
    "control-center", "runtime", "platform",
    "message-queue", "database", "system", "common",
]


def _layer_rank(layer: str) -> int:
    try:
        return _LAYER_ORDER.index(layer)
    except ValueError:
        return 99


# ---------------------------------------------------------------------------
# messaging — C4Component diagram
# ---------------------------------------------------------------------------

def _generate_messaging(diagrams_dir: Path) -> str:
    rows = _read_view_rows("module-deps")
    if not rows:
        raise RuntimeError("module-deps view not found — run `make generate-views` first.")

    # Collect messaging module -> layer
    mq_layers: dict = {}
    for row in rows:
        for mc, lc in (("fromModule", "fromLayer"), ("toModule", "toLayer")):
            mod, layer = row.get(mc, ""), row.get(lc, "")
            if any(x in mod for x in ("message-queue", "messaging", "pekko-messages")):
                mq_layers[mod] = layer

    # Consumers: modules that depend on messaging but aren't messaging themselves
    consumers: dict = {}
    for row in rows:
        to_mod = row.get("toModule", "")
        from_mod = row.get("fromModule", "")
        from_layer = row.get("fromLayer", "")
        if to_mod in mq_layers and from_mod not in mq_layers:
            if from_mod not in consumers:
                consumers[from_mod] = {"layer": from_layer, "deps": set()}
            consumers[from_mod]["deps"].add(to_mod)

    # Intra-messaging edges
    mq_edges = [
        (r["fromModule"], r["toModule"])
        for r in rows
        if r.get("fromModule", "") in mq_layers and r.get("toModule", "") in mq_layers
    ]

    lines = [
        _C4_INIT,
        "C4Component",
        "    title Messaging Framework — Component View",
        "    %% Generated by Archim8 archim8_generate_mermaid_diagram",
        "",
    ]

    # Provider boundaries grouped by layer
    layers_to_mods: dict = {}
    for mod, layer in mq_layers.items():
        layers_to_mods.setdefault(layer, []).append(mod)

    for layer in sorted(layers_to_mods, key=_layer_rank):
        bid = _nid(layer) + "_provider"
        lines.append(f'    Container_Boundary({bid}, "{layer} layer") {{')
        for mod in sorted(layers_to_mods[layer]):
            desc = _MODULE_DESC.get(mod, "")
            lines.append(f'        Component({_nid(mod)}, "{mod}", "Java", "{desc}")')
        lines.append("    }")
        lines.append("")

    # Consumer boundaries grouped by layer
    consumer_layers: dict = {}
    for mod, info in consumers.items():
        consumer_layers.setdefault(info["layer"], []).append(mod)

    for layer in sorted(consumer_layers, key=_layer_rank):
        bid = _nid(layer) + "_consumers"
        lines.append(f'    Container_Boundary({bid}, "{layer} layer — consumers") {{')
        for mod in sorted(consumer_layers[layer]):
            lines.append(f'        Component({_nid(mod)}, "{mod}", "Java", "")')
        lines.append("    }")
        lines.append("")

    # Relationships
    lines.append("    %% Intra-messaging dependencies")
    for from_mod, to_mod in sorted(set(mq_edges)):
        lines.append(f'    Rel({_nid(from_mod)}, {_nid(to_mod)}, "uses")')
    lines.append("")

    lines.append("    %% Consumer → messaging")
    for mod, info in sorted(consumers.items()):
        for dep in sorted(info["deps"]):
            lines.append(f'    Rel({_nid(mod)}, {_nid(dep)}, "uses")')
    lines.append("")

    lines.append('    UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="2")')

    layer_dir = diagrams_dir / "messaging"
    layer_dir.mkdir(parents=True, exist_ok=True)
    out = layer_dir / "C2-Messaging.mmd"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out.relative_to(_archim8_root))


# ---------------------------------------------------------------------------
# messaging-classes — C3 class diagram with external consumers
# ---------------------------------------------------------------------------

# JAR namespace inference — ordered most-specific first
_MQ_JARS: list[tuple[str, str]] = [
    ("messagequeue.base.annotations", "message-queue-base"),
    ("messagequeue.base.definitions",  "message-queue-base"),
    ("messagequeue.base.exception",    "message-queue-base"),
    ("messagequeue.base.options",      "message-queue-base"),
    ("messagequeue.base",              "message-queue-base"),
    ("messagequeue.ibmmq",             "message-queue-ibmmq"),
    ("messagequeue.kafka",             "message-queue-kafka"),
    ("common.config.messagequeue",     "common-config"),
    ("common.messaging",               "common-messaging"),
    ("platform.pekko.messages",        "platform-pekko-messages"),
]

_CONSUMER_JARS: list[tuple[str, str]] = [
    ("common.config",                  "common-config"),
    ("controlcenter.api.core",         "control-center-core"),
    ("controlcenter.api.service",      "control-center-api-service"),
    ("platform.api.rest",              "platform-api-rest"),
    ("platform.boot",                  "platform-boot"),
    ("platform.pekko.cluster",         "platform-pekko-cluster"),
    ("runtime.cobol.ibm",              "runtime-cobol-ibm"),
    ("runtime.cobol.base",             "runtime-cobol-base"),
    ("runtime.cobol.utils",            "runtime-cobol-utils"),
]

# Human-readable namespace labels (PascalCase) for Mermaid classDiagram namespace blocks.
# The identifier IS the visual label — keep it readable but valid (no spaces/hyphens).
_NS_DISPLAY: dict[str, str] = {
    "message-queue-base":         "MessageQueueBase",
    "message-queue-ibmmq":        "MessageQueueIBMMQ",
    "message-queue-kafka":        "MessageQueueKafka",
    "common-config":              "CommonConfig",
    "common-messaging":           "CommonMessaging",
    "platform-pekko-messages":    "PlatformPekkoMessages",
    "control-center-core":        "ControlCenterCore",
    "control-center-api-service": "ControlCenterApiService",
    "platform-api-rest":          "PlatformApiRest",
    "platform-boot":              "PlatformBoot",
    "platform-pekko-cluster":     "PlatformPekkoCluster",
    "runtime-cobol-ibm":          "RuntimeCobolIBM",
    "runtime-cobol-base":         "RuntimeCobolBase",
    "runtime-cobol-utils":        "RuntimeCobolUtils",
}


def _ns_id(jar_name: str) -> str:
    """PascalCase namespace identifier — renders as a human-readable label in Mermaid."""
    return _NS_DISPLAY.get(jar_name, _nid(jar_name))


# ── Role-based namespace grouping (architecture-first, not JAR-first) ──
# Maps individual FQNs to the architectural role namespace they belong in.
# Any FQN not listed falls back to the JAR-based _NS_DISPLAY mapping.
_FQN_TO_ROLE: dict[str, str] = {
    # Core queue abstraction: interface + manager + wiring annotation
    _APP_FQN_PREFIX + "messagequeue.base.MessageQueue":                      "CoreQueue",
    _APP_FQN_PREFIX + "messagequeue.base.MessageQueueManager":               "CoreQueue",
    _APP_FQN_PREFIX + "messagequeue.base.annotations.MessageQueueWire":      "CoreQueue",
    # COBOL bridge: the concrete wrapper that CICS callers reach
    _APP_FQN_PREFIX + "messagequeue.base.FunctionMessageQueue":              "CobolBridge",
    # Transport adapters
    _APP_FQN_PREFIX + "messagequeue.ibmmq.IbmMessageQueue":                  "IBMTransport",
    _APP_FQN_PREFIX + "messagequeue.kafka.KafkaMessageQueue":                "KafkaTransport",
    # Configuration (sits next to the adapters it configures)
    _APP_FQN_PREFIX + "common.config.messagequeue.MessageQueueSetting":      "QueueConfig",
    # Shared messaging enum (used across layers)
    _APP_FQN_PREFIX + "common.messaging.MessageKind":                        "MessageSupport",
    # Platform REST-to-messaging bridge
    _APP_FQN_PREFIX + "platform.pekko.messages.rest.v1.MessageRoutes":       "RestMessaging",
    _APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageServiceImpl": "RestMessaging",
    _APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageMapper":    "RestMessaging",
}

# Render order for framework role namespaces (top-to-bottom per architecture intent)
_MQ_ROLE_ORDER: list[str] = [
    "CoreQueue", "CobolBridge", "IBMTransport", "KafkaTransport",
    "QueueConfig", "MessageSupport", "RestMessaging",
]

# Maps consumer FQNs to consolidated role namespaces (4 groups instead of 9)
_CONSUMER_FQN_TO_ROLE: dict[str, str] = {
    # Bootstrap & runtime entry points
    _APP_FQN_PREFIX + "platform.boot.RuntimeBoot":                                            "BootstrapExt",
    _APP_FQN_PREFIX + "platform.pekko.cluster.rest.RESTServer":                               "BootstrapExt",
    # COBOL runtime callers
    _APP_FQN_PREFIX + "runtime.cobol.ibm.cics.ProcedureDivisionCopyIbmCics":                 "CobolCallersExt",
    _APP_FQN_PREFIX + "runtime.cobol.ibm.cics.ProgramIbmCics":                               "CobolCallersExt",
    _APP_FQN_PREFIX + "runtime.cobol.base.FunctionsBase":                                    "CobolCallersExt",
    _APP_FQN_PREFIX + "runtime.cobol.base.SkeletonBase":                                     "CobolCallersExt",
    _APP_FQN_PREFIX + "runtime.cobol.utils.ibm.dbutlty.Dbutlty":                             "CobolCallersExt",
    # Application-layer consumers of MessageKind
    _APP_FQN_PREFIX + "controlcenter.api.service.v1.message.Message":                        "AppConsumersExt",
    _APP_FQN_PREFIX + "controlcenter.api.core.message.MessageMapper":                        "AppConsumersExt",
    _APP_FQN_PREFIX + "platform.api.rest.message.v1.Message":                                "AppConsumersExt",
    # Configuration-layer readers of MessageQueueSetting
    _APP_FQN_PREFIX + "common.config.Configuration":                                          "ConfigReadersExt",
    _APP_FQN_PREFIX + "common.config.system.SystemSettings":                                  "ConfigReadersExt",
}

# Render order for external consumer role namespaces
_CONSUMER_ROLE_ORDER: list[str] = [
    "BootstrapExt", "CobolCallersExt", "AppConsumersExt", "ConfigReadersExt",
]

# Class display-label overrides for ambiguous simple names (e.g. two "Message" classes)
_FQN_DISPLAY: dict[str, str] = {
    _APP_FQN_PREFIX + "controlcenter.api.service.v1.message.Message":     "Message (ControlCenter)",
    _APP_FQN_PREFIX + "controlcenter.api.core.message.MessageMapper":      "MessageMapper (CC)",
    _APP_FQN_PREFIX + "platform.api.rest.message.v1.Message":             "Message (Platform)",
    _APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageMapper": "MessageMapper",
}

# Known stereotypes for core messaging types
_MQ_STEREOTYPES: dict[str, str] = {
    _APP_FQN_PREFIX + "messagequeue.base.MessageQueue":                     "interface",
    _APP_FQN_PREFIX + "messagequeue.base.annotations.MessageQueueWire":     "annotation",
    _APP_FQN_PREFIX + "messagequeue.base.exception.MessageQueueException":  "exception",
    _APP_FQN_PREFIX + "common.messaging.MessageKind":                       "enumeration",
}


def _classify_pkg(fqn: str, patterns: list[tuple[str, str]]) -> str:
    suffix = fqn.removeprefix(_APP_FQN_PREFIX)
    for pkg_prefix, jar_name in patterns:
        if suffix.startswith(pkg_prefix):
            return jar_name
    return "unknown"


def _simple_name(fqn: str) -> str:
    return fqn.rsplit(".", 1)[-1]


def _safe_id(fqn: str) -> str:
    """Stable, Mermaid-safe class ID from FQN (strips app FQN prefix, dots → underscores)."""
    suffix = fqn.removeprefix(_APP_FQN_PREFIX)
    return re.sub(r"[^a-zA-Z0-9]", "_", suffix)


# Types to omit from the C3 class diagram — too noisy or purely COBOL internal
_MQ_EXCLUDE_SUFFIXES: tuple[str, ...] = (
    "options.",          # all MQ options classes (CloseQueueOptions, etc.)
    "definitions.",      # MQ COBOL descriptors (Mqmd, Mqgmo, Mqod, Mqpmo)
    "MqConstants",
    "IbmMqInfo",
    "KafkaInfo",
    "MessageQueueResponse",
    "MessageQueueException",
    "MessageQueueSettingFactory",  # keep only the Setting itself for clarity
)


def _is_excluded_mq_type(fqn: str) -> bool:
    suffix = fqn.removeprefix(_APP_FQN_PREFIX)
    return any(excl in suffix for excl in _MQ_EXCLUDE_SUFFIXES)


def _generate_messaging_c3(diagrams_dir: Path) -> str:
    """Generate a C3 class diagram of the messaging framework."""
    try:
        from tools.graph_query import run_cypher_raw
    except ImportError:
        raise RuntimeError(
            "Neo4j driver not available — start the MCP server first."
        )

    # ── Query 1: external consumers → messaging types (no test / inner classes) ──
    consumer_rows = run_cypher_raw(f"""
        MATCH (consumerType)-[:DEPENDS_ON]->(mqType)
        WHERE 'ByteCode' IN labels(mqType)
          AND 'ByteCode' IN labels(consumerType)
          AND consumerType.fqn STARTS WITH '{_APP_FQN_PREFIX.rstrip(".")}'
          AND (   mqType.fqn CONTAINS 'messagequeue'
               OR mqType.fqn CONTAINS '.messaging.'
               OR mqType.fqn CONTAINS 'pekko.messages')
          AND NOT consumerType.fqn CONTAINS 'messagequeue'
          AND NOT consumerType.fqn CONTAINS '.messaging.'
          AND NOT consumerType.fqn CONTAINS 'pekko.messages'
          AND NOT consumerType.fqn ENDS WITH 'Test'
          AND NOT consumerType.fqn CONTAINS '$'
          AND NOT mqType.fqn ENDS WITH 'Test'
          AND NOT mqType.fqn CONTAINS '$'
        RETURN DISTINCT
          consumerType.fqn AS consumerFqn,
          mqType.fqn        AS mqFqn
        ORDER BY consumerFqn, mqFqn
    """)
    if not consumer_rows:
        raise RuntimeError(
            "No consumer relationships found — is Neo4j running? "
            "Try `archim8_check_docker_health`."
        )

    # ── Query 2: IMPLEMENTS / EXTENDS between messaging types ──
    impl_rows = run_cypher_raw(f"""
        MATCH (a)-[r:IMPLEMENTS|EXTENDS]->(b)
        WHERE 'ByteCode' IN labels(a) AND 'ByteCode' IN labels(b)
          AND a.fqn STARTS WITH '{_APP_FQN_PREFIX.rstrip(".")}'
          AND (   a.fqn CONTAINS 'messagequeue'
               OR a.fqn CONTAINS '.messaging.'
               OR a.fqn CONTAINS 'pekko.messages')
          AND (   b.fqn CONTAINS 'messagequeue'
               OR b.fqn CONTAINS '.messaging.'
               OR b.fqn CONTAINS 'pekko.messages')
          AND NOT a.fqn ENDS WITH 'Test'
          AND NOT a.fqn CONTAINS '$'
          AND NOT b.fqn ENDS WITH 'Test'
          AND NOT b.fqn CONTAINS '$'
        RETURN DISTINCT a.fqn AS fromFqn, type(r) AS rel, b.fqn AS toFqn
    """)

    # ── Query 3: Methods and fields for framework types (class diagram detail) ──
    # Fields surface as class variables (attributes); methods surface with () suffix.
    # memberType comes from jQAssistant's typeFullyQualifiedName — absent for bytecode
    # without debug info, but included here where available.
    member_rows = run_cypher_raw(f"""
        MATCH (t:Type)-[:DECLARES]->(m)
        WHERE t.fqn STARTS WITH '{_APP_FQN_PREFIX.rstrip(".")}'
          AND (   t.fqn CONTAINS 'messagequeue'
               OR t.fqn CONTAINS '.messaging.'
               OR t.fqn CONTAINS 'pekko.messages')
          AND NOT t.fqn ENDS WITH 'Test'
          AND NOT t.fqn CONTAINS '$'
          AND NOT t.fqn CONTAINS 'options.'
          AND NOT t.fqn CONTAINS 'definitions.'
          AND (m:Method OR m:Field)
          AND NOT m.name IN ['<init>', '<clinit>']
          AND coalesce(m.synthetic, false) = false
        RETURN
          t.fqn AS typeFqn,
          CASE WHEN 'Method' IN labels(m) THEN 'Method' ELSE 'Field' END AS memberKind,
          m.name AS memberName,
          coalesce(m.visibility, 'public') AS visibility,
          coalesce(m.typeFullyQualifiedName, '') AS memberType
        ORDER BY t.fqn, memberKind DESC, m.name
        LIMIT 500
    """) or []

    # ── Collect all FQNs and classify ──
    mq_fqns: set[str]       = set()
    consumer_fqns: set[str] = set()
    consumer_edges: list[tuple[str, str]] = []

    for row in consumer_rows:
        c_fqn, mq_fqn = row.get("consumerFqn", ""), row.get("mqFqn", "")
        if c_fqn and mq_fqn and not _is_excluded_mq_type(mq_fqn):
            mq_fqns.add(mq_fqn)
            consumer_fqns.add(c_fqn)
            consumer_edges.append((c_fqn, mq_fqn))

    # Supplement with any messaging types only seen in impl_rows
    for row in impl_rows:
        for k in ("fromFqn", "toFqn"):
            fqn = row.get(k, "")
            if fqn and not _is_excluded_mq_type(fqn):
                mq_fqns.add(fqn)
    mq_fqns.discard("")

    # Force-include bridge types that may be absent from graph query results
    mq_fqns.update(f for f in _MQ_FORCE_INCLUDE if not _is_excluded_mq_type(f))

    # ── Build member dict (fields + methods) per framework type ──
    _members_by_type: dict[str, list[str]] = {}
    for row in member_rows:
        tfqn = row.get("typeFqn", "")
        kind = row.get("memberKind", "Method")
        name = row.get("memberName", "")
        vis  = row.get("visibility", "public")
        if not (tfqn and name):
            continue
        if _is_excluded_mq_type(tfqn):
            continue
        if name in _SKIP_MEMBER_NAMES or name.startswith("lambda$") or name.startswith("access$"):
            continue
        vis_char = {"+": "+", "public": "+", "private": "-", "protected": "#"}.get(vis, "+")
        if kind == "Method":
            member_str = f"{vis_char}{name}()"
        else:
            member_type = row.get("memberType", "")
            type_short = member_type.rsplit(".", 1)[-1] if member_type else ""
            member_str = f"{vis_char}{type_short} {name}" if type_short else f"{vis_char}{name}"
        bucket = _members_by_type.setdefault(tfqn, [])
        # Deduplicate: identical member_str (same name+visibility) from overloads is noise
        if member_str not in bucket and len(bucket) < 6:
            bucket.append(member_str)

    # ── Build role-based namespace → fqn groupings ──
    mq_ns: dict[str, list[str]]       = {}
    consumer_ns: dict[str, list[str]] = {}

    for fqn in sorted(mq_fqns):
        role = _FQN_TO_ROLE.get(fqn) or _ns_id(_classify_pkg(fqn, _MQ_JARS))
        mq_ns.setdefault(role, []).append(fqn)

    for fqn in sorted(consumer_fqns):
        role = _CONSUMER_FQN_TO_ROLE.get(fqn)
        if not role:
            jar  = _classify_pkg(fqn, _CONSUMER_JARS)
            role = _ns_id(jar) + "Ext"
        consumer_ns.setdefault(role, []).append(fqn)

    # ── Desired internal dep edges (non-trivial, excluding options noise) ──
    _INTERNAL_DEPS: list[tuple[str, str, str]] = [
        (_APP_FQN_PREFIX + "messagequeue.base.FunctionMessageQueue",
         _APP_FQN_PREFIX + "messagequeue.base.MessageQueue",          "uses"),
        (_APP_FQN_PREFIX + "messagequeue.base.FunctionMessageQueue",
         _APP_FQN_PREFIX + "messagequeue.base.MessageQueueManager",   "uses"),
        (_APP_FQN_PREFIX + "messagequeue.base.MessageQueueManager",
         _APP_FQN_PREFIX + "messagequeue.base.MessageQueue",          "manages"),
        (_APP_FQN_PREFIX + "messagequeue.ibmmq.IbmMessageQueue",
         _APP_FQN_PREFIX + "messagequeue.base.annotations.MessageQueueWire", "annotated with"),
        (_APP_FQN_PREFIX + "messagequeue.kafka.KafkaMessageQueue",
         _APP_FQN_PREFIX + "messagequeue.base.annotations.MessageQueueWire", "annotated with"),
        (_APP_FQN_PREFIX + "messagequeue.ibmmq.IbmMessageQueue",
         _APP_FQN_PREFIX + "common.config.messagequeue.MessageQueueSetting", "configured by"),
        (_APP_FQN_PREFIX + "messagequeue.kafka.KafkaMessageQueue",
         _APP_FQN_PREFIX + "common.config.messagequeue.MessageQueueSetting", "configured by"),
        (_APP_FQN_PREFIX + "platform.pekko.messages.rest.v1.MessageRoutes",
         _APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageServiceImpl", "delegates to"),
        (_APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageServiceImpl",
         _APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageMapper", "uses"),
        (_APP_FQN_PREFIX + "platform.pekko.messages.service.v1.MessageMapper",
         _APP_FQN_PREFIX + "common.messaging.MessageKind", "maps"),
        (_APP_FQN_PREFIX + "common.config.system.SystemSettingsFactoryImpl",
         _APP_FQN_PREFIX + "common.config.messagequeue.MessageQueueSettingFactory", "creates"),
    ]

    # ── Relationship label for consumer → mq type ──
    def _rel_label(consumer_fqn: str, mq_fqn: str) -> str:
        simple_mq = _simple_name(mq_fqn)
        if "MessageQueueManager" in mq_fqn:
            return "bootstraps"
        if "MessageQueue" == simple_mq:
            return "injects"
        if "FunctionMessageQueue" in mq_fqn:
            return "calls via CICS"
        if "MessageRoutes" in mq_fqn:
            return "mounts"
        if "MessageServiceImpl" in mq_fqn:
            return "wires"
        if "MessageQueueSetting" in mq_fqn:
            return "reads config"
        if "MessageQueueSettingFactory" in mq_fqn:
            return "creates settings"
        return f"uses {simple_mq}"

    # ── Build diagram lines ──
    lines: list[str] = [
        _C3_INIT,
        "flowchart TB",
        "    %% Messaging Framework — C3 Architecture View",
        "    %% Generated by Archim8 archim8_generate_mermaid_diagram(messaging-classes)",
        "    %% C4 colours: Component(framework)=#7DBEF2  External System(consumer)=#8B8496",
        "",
        f"    {_C4_CLASSDEF_PERSON}",
        f"    {_C4_CLASSDEF_SYSTEM}",
        f"    {_C4_CLASSDEF_CONTAINER}",
        f"    {_C4_CLASSDEF_FRAMEWORK}",
        f"    {_C4_CLASSDEF_EXT_PERSON}",
        f"    {_C4_CLASSDEF_EXTERNAL}",
        "",
    ]

    # ── Framework subgraphs — in architectural role order ──
    all_mq_present: set[str] = set()
    ordered_mq_ns = (
        [ns for ns in _MQ_ROLE_ORDER if ns in mq_ns]
        + sorted(ns for ns in mq_ns if ns not in _MQ_ROLE_ORDER)
    )
    for ns in ordered_mq_ns:
        lines.append(f"    subgraph {ns}[\"{ns}\"]")
        for fqn in sorted(mq_ns[ns]):
            all_mq_present.add(fqn)
            cid   = _safe_id(fqn)
            label = _FQN_DISPLAY.get(fqn, _simple_name(fqn))
            lines.append(f'        {cid}["{label}"]:::framework')
        lines.append("    end")
        lines.append("")

    # ── Consumer subgraphs — consolidated role groups ──
    ordered_consumer_ns = (
        [ns for ns in _CONSUMER_ROLE_ORDER if ns in consumer_ns]
        + sorted(ns for ns in consumer_ns if ns not in _CONSUMER_ROLE_ORDER)
    )
    for ns in ordered_consumer_ns:
        lines.append(f"    subgraph {ns}[\"{ns}\"]")
        for fqn in sorted(consumer_ns[ns]):
            cid   = _safe_id(fqn)
            label = _FQN_DISPLAY.get(fqn, _simple_name(fqn))
            lines.append(f'        {cid}["{label}"]:::external')
        lines.append("    end")
        lines.append("")

    # ── IMPLEMENTS / EXTENDS ──
    if impl_rows:
        lines.append("    %% ── Inheritance / implementation ──")
        for row in impl_rows:
            a, rel, b = row.get("fromFqn", ""), row.get("rel", ""), row.get("toFqn", "")
            if not (a and b):
                continue
            aid, bid = _safe_id(a), _safe_id(b)
            if rel == "IMPLEMENTS":
                lines.append(f"    {aid} -.->|implements| {bid}")
            else:
                lines.append(f"    {aid} -.->|extends| {bid}")
        lines.append("")

    # ── Core structural deps ──
    lines.append("    %% ── Core framework internals ──")
    for from_fqn, to_fqn, label in _INTERNAL_DEPS:
        if from_fqn in all_mq_present and to_fqn in all_mq_present:
            lines.append(
                f"    {_safe_id(from_fqn)} -->\"|{label}\"| {_safe_id(to_fqn)}"
            )
    lines.append("")

    # ── Consumer arrows — deduplicated, MessageQueueWire suppressed (low value) ──
    lines.append("    %% ── External consumers ──")
    seen_edges: set[tuple[str, str, str]] = set()
    for c_fqn, mq_fqn in sorted(consumer_edges):
        if mq_fqn not in all_mq_present:
            continue
        if "MessageQueueWire" in mq_fqn:
            continue
        label = _rel_label(c_fqn, mq_fqn)
        key   = (_safe_id(c_fqn), _safe_id(mq_fqn), label)
        if key not in seen_edges:
            seen_edges.add(key)
            lines.append(
                f"    {_safe_id(c_fqn)} -->\"|{label}\"| {_safe_id(mq_fqn)}"
            )
    lines.append("")

    # ── Visible legend ──
    lines.extend(_c4_legend_flowchart([
        ("_L1_", "Person",                   "c4person"),
        ("_L2_", "Software System",          "c4system"),
        ("_L3_", "Container",                "c4container"),
        ("_L4_", "Component",                "framework"),
        ("_L5_", "External Person",          "c4extperson"),
        ("_L6_", "External Software System", "external"),
    ]))
    lines.append("")

    layer_dir = diagrams_dir / "messaging"
    layer_dir.mkdir(parents=True, exist_ok=True)
    out = layer_dir / "C3-Messaging-Classes.mmd"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out.relative_to(_archim8_root))


# ---------------------------------------------------------------------------
# layer-overview — flowchart with edge counts
# ---------------------------------------------------------------------------

def _generate_layer_overview(diagrams_dir: Path) -> str:
    rows = _read_view_rows("module-deps")
    if not rows:
        raise RuntimeError("module-deps view not found — run `make generate-views` first.")

    layer_mods: dict = {}
    edge_counts: dict = {}

    for row in rows:
        fl, fm = row.get("fromLayer", "unknown"), row.get("fromModule", "")
        tl, tm = row.get("toLayer", "unknown"), row.get("toModule", "")
        layer_mods.setdefault(fl, set()).add(fm)
        layer_mods.setdefault(tl, set()).add(tm)
        if fl != tl:
            edge_counts[(fl, tl)] = edge_counts.get((fl, tl), 0) + 1

    all_layers = sorted(layer_mods.keys(), key=_layer_rank)

    lines = [
        _C3_INIT,
        "flowchart TB",
        "    %% Archim8 generated — Layer topology with live cross-layer edge counts",
        "",
    ]

    for layer in all_layers:
        nid = _nid(layer)
        n = len(layer_mods[layer])
        lines.append(f'    subgraph {nid}["{layer} ({n} jars)"]')
        lines.append(f"        direction LR")
        lines.append(f'        {nid}_lbl["{layer}"]')
        lines.append("    end")
        lines.append("")

    lines.append("    %% Cross-layer dependency counts")
    for (fl, tl), count in sorted(edge_counts.items(), key=lambda x: -x[1]):
        lines.append(f'    {_nid(fl)} -->|"{count} edges"| {_nid(tl)}')

    overview_dir = diagrams_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    out = overview_dir / "C1-Layer-Overview.mmd"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out.relative_to(_archim8_root))


# ---------------------------------------------------------------------------
# violations — directed violation graph
# ---------------------------------------------------------------------------

def _generate_violations(diagrams_dir: Path) -> str:
    rows = _read_view_rows("violations")
    if not rows:
        raise RuntimeError("violations view not found — run `make generate-views` first.")

    lines = [
        _C3_INIT,
        "flowchart LR",
        "    %% Archim8 generated — Upward-coupling architecture violations",
        "",
        f"    {_C4_CLASSDEF_VIOLATION}",
        "",
    ]

    seen: set = set()
    edge_lines = []

    for row in rows:
        fm, fl = row.get("fromModule", ""), row.get("fromLayer", "")
        tm, tl = row.get("toModule", ""), row.get("toLayer", "")
        if not (fm and tm):
            continue
        fi, ti = _nid(fm), _nid(tm)
        if fi not in seen:
            lines.append(f'    {fi}["{fm}\\n[{fl}]"]:::violation')
            seen.add(fi)
        if ti not in seen:
            lines.append(f'    {ti}["{tm}\\n[{tl}]"]:::violation')
            seen.add(ti)
        edge_lines.append(f'    {fi} -->|"violates ↑"| {ti}')

    lines.append("")
    lines.extend(edge_lines)

    # ── Visible legend ──
    lines.append("")
    lines.extend(_c4_legend_flowchart([
        ("_viol_", "Upward-coupling violation", "violation"),
    ]))

    overview_dir = diagrams_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    out = overview_dir / "Violations.mmd"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out.relative_to(_archim8_root))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_mermaid_diagram(diagram_type: str) -> str:
    """Generate a Mermaid diagram from pre-computed Archim8 architecture views.

    Reads from 05_deliver/output/views/ — run `make generate-views` first if the
    graph has changed. Writes .mmd files to 05_deliver/output/diagrams/.

    Supported types:
      messaging         — C4Component diagram of the messaging framework
      messaging-classes — C3 class diagram with external consumers and relationships
      layer-overview    — Flowchart of all layers with live cross-layer edge counts
      violations        — Directed graph of upward-coupling boundary violations
      all               — All four diagrams

    Args:
        diagram_type: One of "messaging", "layer-overview", "violations", "all".

    Returns:
        Paths of generated files, or an error message.
    """
    if _archim8_root is None:
        return "ERROR: archim8 root not configured. Call init_paths() first."

    types_to_run = SUPPORTED if diagram_type == "all" else [diagram_type]
    if diagram_type not in SUPPORTED and diagram_type != "all":
        return (
            f"ERROR: diagram_type must be one of {SUPPORTED + ['all']}. "
            f"Got: '{diagram_type}'"
        )

    diagrams_dir = _archim8_root / "05_deliver" / "output" / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for dt in types_to_run:
        try:
            if dt == "messaging":
                path = _generate_messaging(diagrams_dir)
            elif dt == "messaging-classes":
                path = _generate_messaging_c3(diagrams_dir)
            elif dt == "layer-overview":
                path = _generate_layer_overview(diagrams_dir)
            else:
                path = _generate_violations(diagrams_dir)
            generated.append(path)
        except Exception as exc:
            return f"ERROR generating '{dt}' diagram: {exc}"

    file_list = "\n".join(f"  - {p}" for p in generated)
    return (
        f"Mermaid diagram(s) written:\n{file_list}\n\n"
        "Open in VS Code — press Ctrl+Shift+P → 'Mermaid: Open Preview to the Side'.\n"
        "Or install the 'Mermaid Preview' extension and click the preview icon in the editor."
    )
