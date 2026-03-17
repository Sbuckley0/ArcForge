# 01_ingest/jqassistant — Structural Code Graph (Layer 1b)

jQAssistant is **Archim8 Layer 1b** — the structural enrichment layer on top of the JAR-level jdeps graph.
It scans Maven metadata and compiled bytecode to populate Neo4j with a rich code structure graph.

> **Status: Phase 2 Complete — Running as Docker container (`archim8-jqa:2.9.1`).**  
> See [JQASSISTANT-INTEGRATION.md](../../JQASSISTANT-INTEGRATION.md) for full integration history and phase progress.

## What jQAssistant Adds to the Graph

| Layer | Node Labels | Relationships |
|-------|-------------|---------------|
| Maven structure | `:MavenProject`, `:MavenModule`, `:Artifact` | `:CONTAINS`, `:DEPENDS_ON` |
| Code structure | `:Package`, `:Type`, `:Method`, `:Field` | `:CONTAINS`, `:DECLARES` |
| Metadata | `:Annotation` | `:ANNOTATED_WITH`, `:IMPLEMENTS`, `:EXTENDS` |

All jQA nodes carry `layer:'jqa'` to distinguish from jdeps `:Jar` nodes (`layer:'jdeps'`).

## How to Run

```powershell
# From archim8/ root — pre-requisites: Docker running, Neo4j up (make docker-up)
make jqa-install    # Build Docker image archim8-jqa:2.9.1 (one-time; re-run to rebuild)
make jqa-scan       # Run scanner: bytecode + POMs -> Neo4j (~5-10 min first scan)
make jqa-verify     # Print jQA node counts to confirm scan success
make jqa-pipeline   # jqa-install + jqa-scan + jqa-verify (end-to-end)
make full-pipeline  # jdeps-pipeline + jqa-pipeline (full ingest)
```

> `make jqa-analyze` — Phase 3 (rules engine) — not yet configured.

## Folder Structure

```
jqassistant/
  Dockerfile              # Packages jQA 2.9.1 + JRE alpine into archim8-jqa:2.9.1
  config/
    jqassistant.yml       # Scanner config: Neo4j bolt URL, scan scope, file.exclude
  plugins/                # Optional plugin JARs (Spring, JPA, etc.)
  rules/
    baseline/             # Cypher-based concepts and constraints — Phase 3+
  scripts/
    jqa-install.ps1       # PowerShell: builds Docker image (called by make jqa-install)
    jqa-scan.ps1          # PowerShell: runs Docker scan (called by make jqa-scan)
    scan-docker.sh        # Shell: Docker scan wrapper (Linux/macOS)
    scan.sh               # Shell: runs jQA CLI directly (non-Docker fallback)
```

## Scanning Scope

Configured in `config/jqassistant.yml`:

- **Primary sources**: Maven reactor root — bytecode (`.class`), JARs, `pom.xml` files
- **Excluded (Phase 2)**: `*-sources.jar`, `*-tests.jar`, `*original-*.jar` via `scan.properties.file.exclude`
- **Maven transitive deps**: disabled (`maven3.dependencies.scan: false`) — only reactor modules scanned
- **Third-party `.m2/` cache**: excluded by scanner scope configuration

The `file.exclude` filter was added in Phase 2 to remove ~219 out-of-scope artifacts.
See migration `0002_phase2-jqa-scope-cleanup.cypher` in [`02_store/neo4j/config/schema/migrations/`](../../02_store/neo4j/config/schema/migrations/).

## Graph Model Coexistence

jdeps and jQAssistant share the same Neo4j instance:

| Layer | Owns | Does Not Touch |
|-------|------|----------------|
| jdeps | `:Jar`, `:DEPENDS_ON {layer:'jdeps'}` | jQA nodes |
| jQAssistant | `:MavenModule`, `:Package`, `:Type`, etc. | `:Jar` nodes |

The two layers are linkable via shared artifact name properties for cross-layer queries.


## What It Scans

### Primary (always scanned)
- **Bytecode** — `.class` files inside reactor JARs (authoritative source of truth)
- **Maven POM** — `pom.xml` module structure, declared dependencies
- **Compiled JARs** — all `**/target/*.jar` matching the reactor (sources/tests excluded in Phase 2)
- **Package structure** — hierarchical Java package hierarchy

### Excluded (Phase 2 configuration)
- `*-sources.jar` — source JARs (no bytecode value for graph)
- `*-tests.jar` — test JARs (scope isolation)
- `*original-*.jar` — shaded/relocation originals (duplicate bytecode)
- Maven transitive `.m2/` dependencies (`maven3.dependencies.scan: false`)

## What It Produces (Phase 2 graph state)

After scanning + migrations, Neo4j contains:

| Metric | Value |
|--------|-------|
| `:Maven:Artifact` nodes | 90 (89 reactor JARs + 1 directory) |
| `:Maven:Module` nodes | 265 reactor modules |
| `:Java:Type` nodes | 106,099 bytecode types |
| `DEPENDS_ON {layer:'jdeps'}` | 1,213 (JAR → JAR edges) |
| `DEPENDS_ON {layer:'jqa'}` | 1,275,080 (Type → Type bytecode edges) |
| Untagged `DEPENDS_ON` | 0 ✅ |

## Phase Status

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Docker image build, scan pipeline, Neo4j bolt wiring | ✅ Complete |
| Phase 2 | Scan scope filtering, graph cleanup, dual-layer edge tagging | ✅ Complete |
| Phase 3 | Architecture rules engine (`jqa-analyze`), violation reports | ⬜ Not started |

---

## Troubleshooting

### Cannot connect to Neo4j
```powershell
# Neo4j running?
docker ps | grep archim8-neo4j
# Network available?
docker network ls | grep archim8
```

### Scan completes but Neo4j shows no new nodes
- Run `make jqa-verify` — queries Neo4j directly for jQA node counts
- Check `config/jqassistant.yml` → `store.uri: bolt://neo4j:7687` (uses Docker network hostname)
- Confirm Neo4j container is on the same Docker network as the jQA container

### Out of memory during scan
- The default heap is set in `docker-compose.yml` (jqa service `JQASSISTANT_OPTS`)
- Increase to `-Xmx8G` or higher for large codebases

### Sources / test JARs still appearing after Phase 2
- Re-run migrations: `make neo4j-migrate`
- Migration `0002_phase2-jqa-scope-cleanup.cypher` is idempotent — safe to re-run

### Scan re-processes everything each run
- Expected behaviour — jQA in `reset: false` mode increments; check `jqassistant.yml` `scan.reset`

---

## References

- [jQAssistant Documentation](https://jqassistant.org/get-started/)
- [jQAssistant GitHub](https://github.com/jqassistant)
- [Archim8 Integration Notes](../../JQASSISTANT-INTEGRATION.md)
- [Schema Migrations](../../02_store/neo4j/config/schema/README.md)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)

