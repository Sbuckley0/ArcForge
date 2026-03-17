# 00_orchestrate — Pipeline Orchestration

The orchestration layer composes all other Archim8 layers into coherent flows. It contains **no tool-specific logic** — only configuration and wrapper scripts that invoke tools defined in the layer folders below.

---

## Structure

```
00_orchestrate/
├── config/
│   ├── archim8.env                  # Committed defaults (no secrets)
│   ├── archim8.local.env            # Machine-specific overrides — GITIGNORED
│   ├── archim8.local.env.template   # Copy this to create archim8.local.env
│   └── default.yaml                  # YAML config (Neo4j, project name)
└── scripts/
    ├── load-env.ps1                  # Loads archim8.env + archim8.local.env into shell
    ├── archim8-startup.ps1          # Starts infrastructure (Neo4j, Docker checks)
    ├── archim8-teardown.ps1         # Stops or removes infrastructure containers
    ├── archim8-doctor.ps1           # Full pre-flight environment check
    ├── archim8-status.ps1           # Quick session health check
    └── pipelines/
        └── run-jdeps-pipeline.ps1    # Orchestrates the jdeps ingest flow
```

---

## Key commands (from `archim8/` root)

| Command | What it does |
|---------|-------------|
| `make doctor` | Full environment check: Docker, Java, Python, LLM config |
| `make status` | Quick session check: tool versions, running services, graph state |
| `make docker-up` | Start Neo4j (calls `archim8-startup.ps1`) |
| `make stop` | Suspend containers — data safe, fast resume |
| `make teardown` | Remove containers, preserve graph data on disk |
| `make teardown-all` | **Destructive** — remove containers + delete all graph data |
| `make full-pipeline` | jdeps + jQAssistant ingest end-to-end |
| `make generate-all` | Generate views + diagrams from the current graph |

---

## Configuration

### First-time setup

```powershell
# Create your local override file (one-time per developer)
Copy-Item 00_orchestrate/config/archim8.local.env.template `
          00_orchestrate/config/archim8.local.env
```

Then edit `archim8.local.env`:

```env
# Required
ARCHIM8_TARGET_REPO=C:/path/to/your/java-project
GITHUB_TOKEN=ghp_...              # For GitHub Models LLM provider

# Optional — only if your Neo4j uses non-default credentials
ARCHIM8_NEO4J_USER=neo4j
ARCHIM8_NEO4J_PASSWORD=password
```

### Key variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ARCHIM8_TARGET_REPO` | Absolute path to Maven reactor root of your Java project | — (required) |
| `ARCHIM8_NEO4J_BOLT` | Bolt connection string | `bolt://localhost:7687` |
| `ARCHIM8_NEO4J_USER` | Neo4j username | `neo4j` |
| `ARCHIM8_NEO4J_PASSWORD` | Neo4j password | `password` |
| `ARCHIM8_NEO4J_IMPORT_DIR` | Path Docker mounts as Neo4j import dir | `05_deliver/input/01_ingest` |
| `ARCHIM8_NEO4J_EXPORT_DIR` | Path Docker mounts as Neo4j export dir | `05_deliver/input/03_query` |
| `GITHUB_TOKEN` | Auth token for GitHub Models LLM | — |
| `ARCHIM8_LLM_PROVIDER` | `github-models \| azure \| openai` | `github-models` |

### Config layering

`archim8.env` (committed defaults) → `archim8.local.env` (gitignored overrides). Local wins. Both are loaded automatically by `load-env.ps1`, which is sourced by every pipeline script.

---

## Pipelines

| Target | Sequence |
|--------|---------|
| `jdeps-pipeline` | `docker-up` → `neo4j-wait` → `jdeps-skip` → `neo4j-setup` → `neo4j-export` |
| `jqa-pipeline` | `docker-up` → `jqa-install` → `jqa-scan` → `jqa-analyze` → `jqa-verify` |
| `full-pipeline` | `jdeps-pipeline` → `jqa-pipeline` |
| `generate-pipeline` | `jqa-pipeline` → `generate-all` |
