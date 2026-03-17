# 01_ingest/jdep — JAR-level Dependency Extraction

Uses the JDK `jdeps` tool to extract JAR-to-JAR dependency edges from compiled bytecode.
This is **Archim8 Layer 1a** — the fast, low-overhead structural foundation.

## What It Produces

| File | Location | Description |
|------|----------|-------------|
| `jdeps-output.txt` | `05_deliver/input/01_ingest/` | Raw jdeps output (all lines) |
| `jdeps-jar-edges.csv` | `05_deliver/input/01_ingest/` | Filtered edge list: `fromJar,toJar` |

Both files are gitignored (pipeline outputs).

## How to Run

```powershell
# From archim8/ root
make jdeps-skip     # jdeps + CSV extract, skip Maven build (most common)
make jdeps          # Maven build + jdeps + CSV
make jdeps-filter   # jdeps + CSV, skip build, strip JDK standard library edges
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/jdeps-run.ps1` | Iterates JARs, invokes jdeps, writes `jdeps-output.txt` |
| `scripts/jdeps-extract-edges.ps1` | Parses raw output → `jdeps-jar-edges.csv` |

## Key Behaviours

- **Fat JAR detection**: If a paired `original-*.jar` exists alongside a JAR, jdeps runs against the `original-` (thin JAR) to avoid hanging on 100MB+ Spring Boot fat JARs.
- **Output encoding**: Both scripts write UTF-8 output to avoid encoding issues in cypher-shell.
- **Idempotent**: Re-running always overwrites prior output files.

## Configuration

Environment variables (set in `00_orchestrate/config/archim8.local.env`):

| Variable | Purpose |
|----------|---------|
| `ARCHIM8_TARGET_REPO` | Path to the Maven reactor root directory |
| `ARCHIM8_NEO4J_IMPORT_DIR` | Destination for output files (= `05_deliver/input/01_ingest/`) |
| `ARCHIM8_JDEPS_OUTPUT` | Output filename for raw jdeps text (default: `jdeps-output.txt`) |
| `ARCHIM8_JDEPS_EDGES_CSV` | Output filename for edge CSV (default: `jdeps-jar-edges.csv`) |

## Relationship to jQAssistant

jdeps produces **JAR-level** edges (`:Jar` → `:DEPENDS_ON` → `:Jar`).  
jQAssistant (Layer 1b) produces **type/package/module-level** structure.  
They complement each other and share the same Neo4j instance with separate node labels.
