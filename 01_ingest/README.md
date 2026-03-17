# 01_ingest — Ingestion & Extraction (Layer 2)

Extracts structural facts from compiled Java bytecode and Maven build metadata, and loads them into Neo4j. Two complementary tools cover different levels of the graph:

| Sub-layer | Tool | What it scans | Granularity |
|-----------|------|--------------|-------------|
| **1a — jdeps** | JDK `jdeps` | JAR files | JAR → JAR compile/runtime deps |
| **1b — jQAssistant** | jQAssistant 2.9.1 | Bytecode + Maven POMs | Module · Package · Type · Method · Call graph |

Both layers write to the same Neo4j graph. Edges are tagged with `layer:'jdeps'` or `layer:'jqa'` so queries can be scoped to either source.

> **No source code is read.** Archim8 operates on compiled bytecode and build descriptors only. The target repository is never modified.

---

## Structure

```
01_ingest/
├── jdep/                           # Layer 1a — JAR-level dependency extraction
│   ├── config/
│   │   └── jdeps.env               # jdeps-specific env variable docs
│   ├── scripts/
│   │   ├── jdeps-run.ps1           # Iterates JARs, invokes jdeps, writes output
│   │   └── jdeps-extract-edges.ps1 # Parses output → jdeps-jar-edges.csv
│   └── README.md
└── jqassistant/                    # Layer 1b — structural code graph
    ├── Dockerfile                  # Packages jQA 2.9.1 + JRE into archim8-jqa:2.9.1
    ├── config/
    │   └── jqassistant.yml         # Scanner config: Neo4j URL, scope, file.exclude
    ├── plugins/                    # Optional plugin JARs (Spring, JPA, etc.)
    ├── rules/
    │   └── baseline/               # Cypher-based concepts and constraints
    ├── scripts/
    │   ├── jqa-install.ps1         # Builds Docker image (make jqa-install)
    │   ├── jqa-scan.ps1            # Runs Docker scan (make jqa-scan)
    │   ├── jqa-analyze.ps1         # Runs rules engine (make jqa-analyze)
    │   ├── scan-docker.sh          # Linux/macOS Docker scan wrapper
    │   └── scan.sh                 # Non-Docker fallback (CLI only)
    └── README.md
```

---

## How to run

```powershell
# Prerequisites: Docker running, Neo4j up (make docker-up)

# --- Layer 1a: jdeps ---
make jdeps-skip          # jdeps run + CSV extract (skip Maven build — most common)
make jdeps               # Maven build + jdeps + CSV
make jdeps-filter        # jdeps + CSV, skip build, strip JDK standard library edges

# --- Layer 1b: jQAssistant ---
make jqa-install         # Build Docker image archim8-jqa:2.9.1 (one-time, idempotent)
make jqa-scan            # Scan bytecode + POMs into Neo4j
make jqa-analyze         # Run Cypher rules (concepts + constraints)
make jqa-verify          # Print node counts to confirm scan success
make jqa-reset           # Remove all jQA-owned nodes from Neo4j (keeps jdeps data)

# --- End-to-end pipelines ---
make jdeps-pipeline      # Full jdeps flow (docker-up → scan → schema → load → export)
make jqa-pipeline        # Full jQA flow (docker-up → build image → scan → analyze → verify)
make full-pipeline       # Both pipelines sequentially
```

---

## Outputs

All outputs land in `05_deliver/input/01_ingest/` (gitignored):

| File | Source | Description |
|------|--------|-------------|
| `jdeps-output.txt` | jdeps | Raw jdeps text output |
| `jdeps-jar-edges.csv` | jdeps | Parsed edge list: `fromJar,toJar` |
| `jqa-scan.log` | jQAssistant | Scanner execution log |
| `jqa-analyze.log` | jQAssistant | Rules engine execution log |
| `.jqa-scan-ok` | jqa-scan.ps1 | Marker file — scan completed successfully |
| `.jqa-analyze-ok` | jqa-analyze.ps1 | Marker file — analysis completed successfully |

---

## Graph model

See the top-level [README Graph Model section](../README.md#️-graph-model) for the full node/relationship schema.

Key distinction:
- **jdeps** produces `:Jar` nodes with `:DEPENDS_ON {layer:'jdeps'}` — coarse-grained
- **jQAssistant** produces `:Maven:Module`, `:Java:Package`, `:Java:Type`, `:Java:Method` nodes with typed relationships — fine-grained
