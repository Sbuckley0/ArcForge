# jQAssistant Integration — Archim8 Phase 2

> **This file is deleted when all phases are signed off as complete.**

Moving from JAR-level coupling (jdeps → `:Jar` graph) to a full structural code graph
that supports deterministic architecture documentation without LLM guessing.

---

## Phase Status

| Phase | Title | Status |
|-------|-------|--------|
| 0 | Graph model boundary & label strategy | ✅ Complete |
| 1 | jQAssistant runtime added to Archim8 | ✅ Complete |
| 2 | Scanning scope configured | ✅ Complete |
| 3 | Architecture rules pack | ✅ Complete |
| 4 | Semantic graph views & structured outputs | ✅ Complete |
| 5 | Agentic architecture — multi-agent supervisor | ✅ Complete |
| 6 | Tool forge — agent-managed tool creation | ⬜ Not started |
| 7 | Generic layer inference — codebase-agnostic rules | ⬜ Not started |
| 8 | MCP migration — replace LangGraph with Copilot MCP server | ✅ Complete |
| 9 | Architecture documentation framework | ✅ Complete |
| 10 | Framework abstraction — remove project-specific config | 🔄 Planned |
Status key: ⬜ Not started · 🔄 In progress · ✅ Complete · ⛔ Blocked · 🔄 Planned

---

## Phase 0 — Graph Model Boundary

**Goal:** Define label/relationship naming so jdeps and jQAssistant coexist in Neo4j without collision.

### Todos

- [x] Document the `:Jar` / `:DEPENDS_ON` boundary for jdeps (already live — do not touch)
- [x] Define Archim8 Layer 2 node labels:
  - `:MavenProject`, `:MavenModule`, `:Artifact`
  - `:Package`, `:Type`, `:Method`, `:Field`, `:Annotation`
- [x] Define Archim8 Layer 2 relationships:
  - `:CONTAINS` (module → package, package → type, type → method/field)
  - `:DECLARES` (type → method/field)
  - `:DEPENDS_ON` (type/package-level, tagged with `layer:'jqa-java'`/`layer:'jqa-maven'`)
  - `:ANNOTATED_WITH`, `:IMPLEMENTS`, `:EXTENDS`
- [x] Add disambiguation property `layer:'jdeps'` to existing `:DEPENDS_ON` edges during schema migration
- [x] Write and commit label strategy doc to `02_store/neo4j/config/schema/`

### Outputs Delivered

- ✅ `02_store/neo4j/config/schema/jqa-labels.md` — authoritative dual-layer label/relationship reference
- ✅ `02_store/neo4j/config/init/01-constraints.cypher` — cleaned; only Archim8-owned labels (`:Jar`, `:Meta`)
- ✅ `02_store/neo4j/config/init/02-index.cypher` — cleaned; added `jar_group` index
- ✅ `02_store/neo4j/config/schema/constraints.cypher` — rewritten to reflect jQA label taxonomy
- ✅ `02_store/neo4j/config/schema/indexes.cypher` — rewritten; jQA indexes documented as comments
- ✅ `02_store/neo4j/config/schema/README.md` — updated with dual-layer model
- ✅ `02_store/neo4j/config/schema/migrations/0001_layer-jdeps-tag.cypher` — tags `layer='jdeps'` on existing `:DEPENDS_ON` edges
- ✅ Makefile: added `neo4j-migrate` target

---

## Phase 1 — jQAssistant Runtime

**Goal:** Add a repeatable, idempotent jQA scan command inside Archim8.

### Todos

- [x] Decide runner approach: **CLI JAR distribution v2.9.1** (Neo4j v5 variant, downloaded via `make jqa-install`)
- [x] Add `jqa-install` Makefile target:
  - Downloads jQAssistant CLI distribution to `01_ingest/jqassistant/bin/` (gitignored)
  - Idempotent — skips if `jqassistant.cmd` already present
- [x] Create `01_ingest/jqassistant/scripts/jqa-install.ps1`
- [x] Create `01_ingest/jqassistant/scripts/jqa-scan.ps1`:
  - Accepts `-ScanPath` parameter (default: `$env:ARCHIM8_TARGET_REPO`)
  - Invokes jQA CLI with `-configurationLocations jqassistant.yml -f <ScanPath>`
  - Writes `jqa-scan.log` to `05_deliver/input/01_ingest/`
  - Writes `.jqa-scan-ok` marker on success (enables idempotency check)
- [x] Create `jqa-reset` Makefile target:
  - Deletes `:Maven` and `:Java` nodes (jQA-owned); preserves `:Jar` / `:Meta`
- [x] Wire `jqa-scan`, `jqa-verify`, `jqa-reset` Makefile targets (replaced Phase 1 stubs)
- [x] Update `01_ingest/jqassistant/config/jqassistant.yml` to jQA 2.x format
- [x] Add `01_ingest/jqassistant/bin/` and scan logs to `.gitignore` (already done in Phase 0)
- [x] Run `make jqa-install` — download CLI and verify `jqassistant.cmd` present
- [x] Run `make jqa-scan` against `C:\amt\libraries\amt-go-java\parent`
- [x] Verify scan log shows expected Maven module count matches known reactor

### Expected Outputs

- ✅ `01_ingest/jqassistant/scripts/jqa-install.ps1` (created)
- ✅ `01_ingest/jqassistant/scripts/jqa-scan.ps1` (created)
- ✅ `01_ingest/jqassistant/config/jqassistant.yml` (updated to jQA 2.x format)
- ✅ `01_ingest/jqassistant/bin/` (gitignored, populated by `make jqa-install`)
- ✅ `05_deliver/input/01_ingest/jqa-scan.log` (199 KB, 14,604 entries, ~40 min)
- ✅ `make jqa-scan` ran clean — scan verified, Neo4j populated:
  - **9,813** `:Maven` nodes
  - **3,915,294** `:Java` nodes
  - **1,276,293** `:DEPENDS_ON` edges (bytecode-level)
  - **1,213** `:DEPENDS_ON {layer:'jdeps'}` edges preserved ✅ (`scan.reset: false` worked)

### Phase 1 — Lessons Learned

Three silent bugs in jQA 2.x vs 1.x config that would not fail loudly:

1. **`store.remote.username/password`** — credentials must live under `store.remote`, not directly under `store`. Wrong location causes `AuthenticationException: scheme 'none'` at first Neo4j connection attempt.
2. **`scan.reset: true` is the default** — jQA 2.x resets the entire graph on every scan. Must explicitly set `scan.reset: false` to protect the existing `:Jar` / jdeps data.
3. **PowerShell `$ErrorActionPreference='Stop'` + `2>&1` pipe** — jQA writes INFO logs to stderr; piping stderr triggers `NativeCommandError`, killing the process before it scans anything. Must lower to `'Continue'` around the native CLI invocation.

---

## Phase 2 — Scanning Scope ✅

**Goal:** Configure exactly what jQA scans so the graph is focused and clean.

### Todos

- [x] Update `01_ingest/jqassistant/config/jqassistant.yml`:
  - Added `scan.properties.file.exclude: "*-sources.jar,*-tests.jar,*original-*.jar"`
  - Added `scan.properties.maven3.dependencies.scan: "false"` (no external Maven dep scanning)
  - `scan.reset: false` preserved, `continue-on-error: true` preserved
- [x] Identify Maven modules in reactor: **265 `:Maven:Module` nodes** (from Phase 1 scan)
- [x] Cross-check: `:Java:Artifact` count dropped from **309 → 90** (89 main JARs + 1 directory)
- [x] Cross-check: jdeps `:Jar` nodes linkable to scanned `:Artifact` nodes:
  - **82 / 89** reactor JARs fully linked (100% of linkable JARs)
  - 7 unlinked: 6 JDK standard modules (`java.base` etc.), 1 excluded shaded JAR — all expected

### Migrations Applied

Two new Cypher migrations were added to clean up Phase 1 noise and establish the dual-layer tag:

| Migration | What it does | Result |
|-----------|--------------|--------|
| `0001` (patched) | Tags `:Jar`→`:Jar` DEPENDS_ON with `layer='jdeps'` | Scoped to `:Jar` nodes; avoids bulk memory error on 1.27M jQA edges |
| `0002_phase2-jqa-scope-cleanup` | Deletes 219 out-of-scope artifacts (-sources, -tests, original) | **219 artifacts removed** — `:Java:Artifact` count 309→90 |
| `0003_layer-jqa-tag` | Tags jQA type-to-type DEPENDS_ON with `layer='jqa'` (batched 10k/tx) | **1,275,080 edges tagged** |

### Final Graph State (post Phase 2)

| Metric | Value | Notes |
|--------|-------|-------|
| `:Java:Artifact` | 90 | 89 main JARs + 1 directory artifact |
| `:Jar` (pure jdeps) | 89 | External dependency JARs (not scanned by jQA) |
| `:Maven:Module` | 265 | Maven reactor modules from jQA POM scan |
| `:Java:Type` | 106,099 | Bytecode types from main JARs |
| `DEPENDS_ON {layer:'jdeps'}` | 1,213 | 613 Jar→Jar + 600 Module→Module (architecture model) |
| `DEPENDS_ON {layer:'jqa'}` | 1,275,080 | Class-to-class bytecode dependencies |
| `DEPENDS_ON` (untagged) | 0 | All edges now dual-layer labelled |

### Phase 2 — Lessons Learned

1. **`file.exclude` in jQA 2.x** is under `scan.properties`, not `scan.include/exclude`. Accepted wildcards `*` and `?` apply to the full path, so `*-sources.jar` matches any path ending in `-sources.jar`.
2. **`scan.reset: false` doesn't retroactively clean old data.** Migration was needed to remove the 219 Phase 1 artifacts. DETACH DELETE on excluded artifact nodes is safe; shared type nodes (sources JAR duplicates) are preserved via the main JAR's CONTAINS chain.
3. **Migration `0001` is unsafe on large graphs.** The original `MATCH ()-[r:DEPENDS_ON]->()` pattern attempted to tag 1.27M edges in a single transaction, exceeding Neo4j CE's `dbms.memory.transaction.total.max`. Fix: scope to `(:Jar)-[r]->(:Jar)` only; add a separate batched migration for jQA edges.
4. **JDK module nodes** (`java.base`, `java.sql`, etc.) appear in jdeps output but can never be linked to jQA artifacts. Filter them with `WHERE NOT j.name STARTS WITH 'java.'` in cross-link queries.

---

## Phase 3 — Architecture Rules Pack ✅ Complete

**Goal:** Enforce and measure architecture constraints. This is the primary value of jQAssistant.

**Completed:** 2026-03-04

### What Was Built

**Rule format:** jQA 2.9.1 uses XML rule format (schema `v1.8` with `v2.9` element names).
AsciiDoc was attempted first but `[[Namespace:Id]]` block IDs with colons are not parsed
correctly by Asciidoctorj in jQA 2.x. XML is reliable and preferred for tooling-generated rules.

**Layer model** (low → high — upward dependencies are ALLOWED):

| Layer | Modules | Label |
|-------|---------|-------|
| 1 | `common-*` | `:AMT_Common` |
| 2 | `database-*`, `message-queue-*` | `:AMT_Database`, `:AMT_MessageQueue` |
| 3 | `system-*`, `transaction-database-*` | `:AMT_System` |
| 4 | `platform-*` | `:AMT_Platform` |
| 5 | `runtime-cobol-*`, `runtime-easytrieve-*` | `:AMT_Runtime` |
| 6 | `control-center-*` | `:AMT_ControlCenter` |

### Deliverables

- [x] `01_ingest/jqassistant/rules/baseline/baseline.xml` — 7 concepts + 5 constraints + 1 group
- [x] `01_ingest/jqassistant/scripts/jqa-analyze.ps1` — analyze wrapper with violation summary
- [x] `jqassistant.yml` analyze block wired (absolute paths, `failOn: none`, `warn: true`)
- [x] `docker-compose.yml` rules volume added (`/jqassistant/rules`) + report volume
- [x] `make jqa-analyze` target wired and functional
- [x] Duplicate `rules/rules/` directory removed

### First Run Violations (2026-03-04)

`make jqa-analyze` executed against the live graph. Results:

| Constraint | Violations | Status |
|------------|-----------|--------|
| `AMT:CommonMustNotDependUpward` | **6** | ⚠️ Review required |
| `AMT:MessageQueueMustNotDependOnHigherLayers` | **1** | ⚠️ Review required |
| `AMT:DatabaseMustNotDependOnHigherLayers` | 0 | ✅ Clean |
| `AMT:PlatformMustNotDependOnRuntime` | 0 | ✅ Clean |
| `AMT:RuntimeMustNotDependOnControlCenter` | 0 | ✅ Clean |

**AMT:CommonMustNotDependUpward violations (6):**
- `common-config.jar` → `system-database-orm-hibernate.jar` (Layer3:System)
- `common-config.jar` → `system-database-repository-spring.jar` (Layer3:System)
- `common-config.jar` → `transaction-database-repository-spring.jar` (Layer3:System)
- `common-config.jar` → `platform-api-secure-storage.jar` (Layer4:Platform)
- `common-security.jar` → `system-database-orm-hibernate.jar` (Layer3:System)
- `common-security.jar` → `system-database-repository-spring.jar` (Layer3:System)

**AMT:MessageQueueMustNotDependOnHigherLayers violations (1):**
- `message-queue-base.jar` → `runtime-cobol-variables-base.jar` (Layer5:Runtime)

> **Engineering action required:** These violations indicate upward coupling in the `common-config`,
> `common-security`, and `message-queue-base` modules. Investigation and resolution of these
> 7 violations is tracked as a follow-up task.

### Architecture Configuration Notes

- Rule files: `01_ingest/jqassistant/rules/baseline/`
- Container mount: `/jqassistant/rules` (read-only)
- Rule group: `AMT:Default`
- `failOn: none` — violations warn, do not fail the pipeline (intentional for first-run baseline)
- To escalate violations to build failures: change `failOn: none` → `failOn: major`

---

## Phase 4 — Semantic Graph Views & Structured Outputs ✅ Complete

**Completed:** 2026-03-04

**What was built:**
- 8 Cypher queries in `03_query/cypher/library/jqa/` covering module-deps, gRPC, Pekko HTTP, Spring components, observability, violations, key-abstractions, COBOL subsystem
- 8 output views generated in `05_deliver/output/views/` with YAML frontmatter (view, scope, generated, cypher, covers)
- `manifest.json` tracking all 8 views with row counts and timestamps
- `arc-containers.puml`, `arc-cobol-emulation.puml` PlantUML diagrams
- Mermaid diagrams: `layer-map.mmd`, `observability-c1-context.mmd`, `observability-c2-containers.mmd`, `observability-c3-components.mmd`
- Makefile targets: `generate-views`, `generate-diagrams`, `generate-all`, `generate-pipeline`
- Generator scripts: `generate_views.py`, `generate_plantuml.py`, `manifest.py`

**View manifest (as at 2026-03-04):**

| View | Rows | Scope |
|------|------|-------|
| `module-deps` | 515 | All AMT Jar-to-Jar jdeps edges |
| `grpc-services` | 252 | `@PekkoGrpcGenerated` types |
| `pekko-http-api` | 27 | HTTP infrastructure edges |
| `spring-components` | 1,056 | Spring/JPA stereotype types |
| `observability-coverage` | 21 | Observability framework imports |
| `violations` | 8 | Upward-coupling violations |
| `key-abstractions` | 87 | Interfaces by implementation count |
| `cobol-subsystem` | 29 | `runtime-cobol-*` artifacts |

---

## Phase 5 — Agentic Architecture — Multi-Agent Supervisor ✅ Complete

**Goal:** A fully agentic, multi-specialist system that answers architecture questions by routing to the right agent, combining Neo4j graph queries with pre-generated views, and enforcing governance across the pipeline. The graph is the master — every factual claim is traceable to a graph node, edge, or query result.

### Architecture Pattern

**Supervisor pattern via LangGraph `StateGraph`.** The orchestrator is itself an LLM agent whose job is routing — not answering. Each specialist runs independently with a scoped tool set and dedicated system prompt. LangGraph `MessagesState` carries conversation context between agents. `MemorySaver` checkpointer enables mid-graph interrupts for the Human Anchor gate.

### Agent Roster

| Agent | File | Responsibility | Tools |
|-------|------|---------------|-------|
| **Orchestrator** | `orchestrator.py` | Routes to specialists; chains for multi-step flows; enforces Human Anchor gate | Routing LLM only |
| **Infra** | `specialists/infra_agent.py` | Pre-flight checks; Docker/Make health; pipeline scripts | `check_docker_health`, `run_make_target`, `read_log_file`, `check_file_exists` |
| **Ingest** | `specialists/ingest_agent.py` | Triggers jdeps/jQA scans; verifies artefacts | `run_make_target`, `check_file_exists`, `read_log_file`, `check_docker_health` |
| **Store** | `specialists/store_agent.py` | Neo4j health; schema migration (write-gated); diagnostics | `run_cypher_query`, `check_docker_health`, `check_file_exists`, `run_cypher_migration`* |
| **Query** | `specialists/query_agent.py` | Architecture analysis; novel Cypher; cross-layer reasoning | `run_cypher_query`, `check_file_exists` |
| **Generate** | `specialists/generate_agent.py` | Diagram/view generation; staleness checks | `generate_architecture_diagram`, `run_make_target`, `check_file_exists`, `list_available_views`, `read_architecture_view` |
| **Deliver** | `specialists/deliver_agent.py` | Stakeholder answers; presents views; narration layer | `list_available_views`, `read_architecture_view`, `check_file_exists` |

_* `run_cypher_migration` only available when `migration: true` in profile (operator profile)._

### Tools

| Tool | File | Description |
|------|------|-------------|
| `run_cypher_query` | `tools/graph_query.py` | Read-only Cypher; write keywords blocked by regex |
| `run_cypher_migration` | `tools/graph_query.py` | Write Cypher; path-gated to `02_store/neo4j/config/schema/` |
| `list_available_views` | `tools/view_reader.py` | Lists manifest entries |
| `read_architecture_view` | `tools/view_reader.py` | Reads view Markdown (12k char limit) |
| `generate_architecture_diagram` | `tools/diagram_gen.py` | Triggers PlantUML generator via subprocess |
| `run_make_target` | `tools/shell_exec.py` | Runs allowlisted Make targets only |
| `check_file_exists` | `tools/shell_exec.py` | Checks file/dir exists within workspace |
| `read_log_file` | `tools/shell_exec.py` | Reads last N lines of named log (allowlisted dirs) |
| `check_docker_health` | `tools/docker_health.py` | Inspects named containers (allowlisted set) |

### Profiles

| Profile | Shell/Docker | Migration | Intended for |
|---------|-------------|-----------|--------------|
| `local` | off | off | Developer — read-only Q&A via OpenAI |
| `github-models` | off | off | Developer — read-only Q&A via GitHub PAT (no separate API account needed) |
| `analyst` | off | off | Architect / tech lead — graph + views only |
| `pipeline` | on | off | Operator running ingestion or generation |
| `operator` | on | on | Schema manager — full write path, Human Anchor still enforced |

### Directory Structure

```
06_agents/
  orchestrator.py              ← LangGraph StateGraph supervisor (implemented)
  archim8_agent.py            ← legacy single-agent facade (retained)
  config/
    agent.yaml                 ← default config with all tool toggles
    profiles/
      local.yaml               ← OpenAI, read-only
      analyst.yaml             ← read-only, no generation
      pipeline.yaml            ← shell + docker enabled
      operator.yaml            ← full stack including migration
  specialists/
    __init__.py
    infra_agent.py
    ingest_agent.py
    store_agent.py
    query_agent.py
    generate_agent.py
    deliver_agent.py
  tools/
    __init__.py
    graph_query.py             ← read-only + migration (write-gated)
    view_reader.py
    diagram_gen.py
    shell_exec.py              ← run_make_target, check_file_exists, read_log_file
    docker_health.py           ← check_docker_health
  prompts/
    system.md                  ← legacy base prompt
    orchestrator.md
    infra.md
    ingest.md
    store.md
    query.md
    generate.md
    deliver.md
```

### Implementation Todos

- [x] Implement `shell_exec.py` tools (`run_make_target`, `check_file_exists`, `read_log_file`)
- [x] Implement `docker_health.py` tool (`check_docker_health`)
- [x] Add `run_cypher_migration` to `graph_query.py` (write-gated, migration files only)
- [x] Implement 6 specialist agents with scoped system prompts
- [x] Implement `orchestrator.py` as LangGraph `StateGraph` supervisor
- [x] Write system prompts for all 7 agents
- [x] Wire `archim8_agent.py` with new tools (shell_exec, docker_health toggles)
- [x] Add `__init__.py` to `tools/` and `specialists/`
- [x] Create analyst, pipeline, operator profiles
- [x] Add orchestrator Makefile targets (`orchestrate`, `orchestrate-local`, `orchestrate-ask`)
- [x] Fix `requirements.txt` (remove `langgraph-prebuilt`, correct version pins)
- [x] Restructure: move `05_deliver/agents/` → `06_agents/` (top-level)
- [ ] Run `smoke_test_orchestrator.py` and confirm all sections pass
- [ ] Run `make orchestrate-local` against live Neo4j (requires LLM key + running stack)
- [ ] Validate Human Anchor interrupt: confirm write-path agents pause for approval
- [ ] Validate routing: supervisor sends graph queries to `query`, pipeline ops to `infra`/`ingest`

### Governance Rules (enforced by Orchestrator)

- Infra agent must confirm Docker is healthy before any scan or generate operation
- Generate agent must check manifest staleness before writing any output
- Store agent must verify migration state before any write-gated Cypher
- Deliver agent never calls `run_cypher_query` directly — always reads from views
- Write-path agents (`infra`, `ingest`, `store`) are declared as `interrupt_before` nodes — LangGraph pauses and awaits human approval before execution

### Known Limitations (by design)

- The system cannot answer "why" an architectural decision was made — only "what" exists
- Request/response body schema for REST/gRPC requires OpenAPI spec ingestion (deferred)
- Runtime behaviour (actual call patterns, load, errors) is outside static analysis scope

---

## Phase 5 — Testing Plan

**Scope and intent:** Structured validation that each agent works correctly in isolation
before testing the supervisor graph end-to-end. Each sub-phase below maps to a verifiable
human checkpoint. Do not proceed to the next sub-phase until you are satisfied with the
current one.

---

### 5-T0 — Smoke tests (no live deps required)

**What:** Automated unit-level checks. No Neo4j, no LLM, no Docker required.
**How:** Run from the archim8 root directory.
**Pass criteria:** Both scripts exit 0 and print `ALL ... PASSED`.

```powershell
# Legacy single-agent smoke test
cd archim8
python 14_tests/smoke_test_agent.py

# New orchestrator smoke test
python 14_tests/smoke_test_orchestrator.py
```

**Sections covered by `smoke_test_orchestrator.py`:**
1. All tool modules import cleanly
2. Cypher safety guard (safe queries allowed, write keywords blocked)
3. `shell_exec` allowlist (unlisted targets rejected, path traversal caught)
4. All four profiles load and have correct tool flags
5. All six `build_agent()` functions callable with a mock LLM
6. `build_orchestrator()` compiles the StateGraph without error
7. Human Anchor `interrupt_before` contains exactly `{infra, ingest, store}`

Todos:
- [x] Run `smoke_test_agent.py` — confirm passes after `05_deliver/agents` → `06_agents` move
- [x] Run `smoke_test_orchestrator.py` — confirm all 6 sections pass

---

### 5-T1 — Query agent (analyst profile, live Neo4j, no pipeline ops)

**What:** Test the `query_agent` standalone with a live graph.
**Profile:** `analyst` (read-only, no shell/docker/generation)
**Pre-condition:** Neo4j running with populated graph (`make docker-up`)
**How:** Run the legacy facade with the analyst profile (easiest isolated path).

```powershell
make agent-local  # or:
python 06_agents/archim8_agent.py --profile analyst "What modules are in the COBOL subsystem?"
python 06_agents/archim8_agent.py --profile analyst "Show me the top 5 modules by incoming dependencies"
python 06_agents/archim8_agent.py --profile analyst "Are there any circular dependencies?"
```

**Human checkpoint — accept if:**
- Results reference real module names from your graph (not hallucinated)
- Cypher is visible in verbose mode and correct
- No tool errors in output
- Answers are concise, structured, and reference graph row counts

---

### 5-T2 — Deliver agent (analyst profile, live Neo4j + manifest)

**What:** Test view listing and reading from the manifest.
**Profile:** `analyst`
**Pre-condition:** Neo4j running, `05_deliver/output/manifest.json` exists, views populated

```powershell
python 06_agents/archim8_agent.py --profile analyst "What architecture views are available?"
python 06_agents/archim8_agent.py --profile analyst "Show me the violations view"
python 06_agents/archim8_agent.py --profile analyst "Summarise the grpc-services view"
```

**Human checkpoint — accept if:**
- Agent correctly lists views from manifest without hallucinating extra ones
- View content is accurately quoted, not paraphrased incorrectly
- Large views are truncated gracefully with a note

---

### 5-T3 — Generate agent (pipeline profile, live Neo4j)

**What:** Test diagram and view generation.
**Profile:** `pipeline`
**Pre-condition:** Neo4j running with data

```powershell
python 06_agents/archim8_agent.py --profile pipeline "Regenerate the containers diagram"
python 06_agents/archim8_agent.py --profile pipeline "Regenerate all architecture views"
```

**Human checkpoint — accept if:**
- Output `.puml` / `.md` files have updated timestamps
- Agent confirms file paths after generation
- Agent does not regenerate if already up to date (manifest check)

---

### 5-T4 — Infra agent (pipeline profile, live Docker)

**What:** Test Docker health checking and Make target execution.
**Profile:** `pipeline`
**Pre-condition:** Docker running

```powershell
python 06_agents/orchestrator.py --profile pipeline "Check if Neo4j is healthy"
# When prompted for Human Anchor approval, type 'yes' to proceed
python 06_agents/orchestrator.py --profile pipeline "Start the Docker stack"
```

**Human checkpoint — accept if:**
- Health check returns correct container status
- Make targets that are triggered are on the allowlist (verify via verbose output)
- Human Anchor prompt appears before any Make target is executed
- Cancelling (typing 'no') prevents the action and reports correctly

---

### 5-T5 — Full orchestrator routing (analyst profile, live Neo4j)

**What:** Test that the supervisor routes correctly to the right specialist.
**Profile:** `analyst` (safe — no write-path specialists will be invoked)
**Pre-condition:** Neo4j running, manifest exists

```powershell
python 06_agents/orchestrator.py --profile analyst "What COBOL modules exist?"
python 06_agents/orchestrator.py --profile analyst "List the available views and summarise the violations one"
python 06_agents/orchestrator.py --profile analyst "Show me modules with more than 10 incoming dependencies"
```

**Human checkpoint — accept if:**
- Supervisor routes single-specialist questions to the correct agent (check verbose output)
- Multi-step questions are decomposed and routed sequentially
- FINISH is triggered correctly when the answer is complete
- No hallucinations — all answers traceable to graph data or view content

---

### 5-T6 — Human Anchor gate (pipeline profile, write-path)

**What:** Full end-to-end test of the interrupt mechanism.
**Profile:** `pipeline`
**Pre-condition:** Docker + Neo4j running

```powershell
python 06_agents/orchestrator.py --profile pipeline "Run the jdeps pipeline"
# - Supervisor should route to infra (health check) then ingest
# - Graph should pause before infra node
# - Type 'no' — confirm action is cancelled
# - Re-run and type 'yes' — confirm pipeline executes
```

**Human checkpoint — accept if:**
- Interrupt fires before infra/ingest execution (not after)
- Cancelling with 'no' results in zero side effects
- Approving with 'yes' triggers the correct Make target
- Post-pipeline, agent confirms artefact existence

---

### Phase 5 testing — exit criteria

All six sub-phases must be accepted before Phase 5 is marked ✅ Complete:

- [x] 5-T0 smoke tests pass ✅
- [x] 5-T1 query agent accepted ✅
- [x] 5-T2 deliver agent accepted ✅
- [x] 5-T3 generate agent accepted ✅
- [x] 5-T4 infra agent accepted ✅
- [x] 5-T5 orchestrator routing accepted ✅
- [x] 5-T6 Human Anchor gate accepted ✅

---

## Phase 6 — Tool Forge ⬜ Not Started

> **Phase 5 is ✅ complete. Phase 6 is unblocked.**

### What is the Tool Forge?

The Tool Forge is a pattern where a specialist agent can **propose, draft, and register
a new `@tool` function** within its own domain — without a developer writing it manually.
The agent generates the tool stub, writes it to a staging area, and the human reviews
and approves the merge.

This is genuinely agentic tooling: the system can grow its own capabilities, bounded
by the Human Anchor principle.

### Why not now?

Phase 5 establishes the fixed capability boundary: every tool is hand-written, reviewed,
and has clear safety properties. The orchestrator routes to specialists that use these
fixed tools. This is intentional — you need to know exactly what the system can do before
you let it extend itself.

Adding self-extension before the base is solid means:
- You cannot distinguish a routing bug from a generated-tool bug
- Generated tools can introduce security surface (arbitrary code, broader subprocess call)
- You have no empirical basis for what tools are actually missing
- The review gate (Human Anchor) has no context for what "good" looks like yet

**Phase 5 must be fully complete and in active use before Phase 6 begins.**

### How it will work (design, not implementation)

The tool forge has three boundaries:

**1. Scope boundary — what a specialist can propose**

Each specialist may only propose tools within its own domain directory:

| Specialist | Permitted staging path |
|------------|------------------------|
| infra | `06_agents/tools/forge/infra/` |
| ingest | `06_agents/tools/forge/ingest/` |
| store | `06_agents/tools/forge/store/` |
| query | `06_agents/tools/forge/query/` |
| generate | `06_agents/tools/forge/generate/` |
| deliver | `06_agents/tools/forge/deliver/` |

No specialist may propose a tool that alters another specialist's domain or modifies
shared infrastructure (`orchestrator.py`, `config/`, existing `tools/*.py`).

**2. Safety boundary — what a proposed tool may do**

A tool forge proposal must:
- Use only Python stdlib + already-approved packages (LangChain, Neo4j driver, etc.)
- Import only from `tools/` and Python stdlib
- Declare a `@tool` decorated function returning `str`
- Not call `subprocess` directly (use `run_make_target` or `check_docker_health` wrappers)
- Not write files outside the specialist's own output directory
- Not make network calls outside `_driver` (Neo4j) or the LLM (via LangChain)

**3. Human Anchor — the review gate**

All proposed tools go through:
1. **Staging:** Agent writes draft to `tools/forge/<specialist>/proposed_<name>.py`
2. **Diff surface:** Human reviews the file (shown inline in the conversation)
3. **Approval:** Human explicitly says "approve" or "reject" — never auto-merged
4. **Registration:** On approval, tool is moved to `tools/<name>.py` and added to
   the relevant specialist's tool list in `orchestrator.py`
5. **Smoke test extension:** The proposing specialist generates a test case that is
   added to `smoke_test_orchestrator.py` before the tool is considered live

### Phase 6 prerequisites (exit criteria from Phase 5)

Before Phase 6 can start:
- [ ] All Phase 5 testing sub-phases accepted (5-T0 through 5-T6)
- [ ] Orchestrator has been running in regular use for at least two weeks
- [ ] At least one specialist has been observed to be "reaching" for a capability
      it doesn't have (evidence of a real gap, not a hypothetical one)
- [ ] A code-review workflow for `tools/forge/` is established

### Phase 6 todos (not started — listed for planning only)

- [ ] Design `propose_tool` meta-tool (takes: specialist name, tool intent description, example input/output)
- [ ] Implement staging directory structure (`tools/forge/<specialist>/`)
- [ ] Implement diff-surface display in the conversation
- [ ] Implement Human Anchor approval gate for proposed tools
- [ ] Implement `register_tool` function (moves from staging, updates orchestrator tool lists)
- [ ] Add generated tool smoke test template
- [ ] Document forge safety constraints in each specialist's system prompt

---

## Phase 7 — Generic Layer Inference

**Goal:** Remove all AMT-specific hardcoding from Archim8's architecture rule engine.
After Phase 7, pointing Archim8 at any Java monorepo produces working constraint XML and
a contextualised violations report — no manual XML editing required.

**Pre-condition:** Phase 5 fully in active use. Real-world evidence that the violations
reporter is trusted before we change the layer model underneath it.

---

### The problem Phase 7 solves

Right now the architecture rule engine has two hardcoded seams:

1. **`01_ingest/jqassistant/rules/baseline/`** — XML concepts and constraints are written
   by hand for the AMT module hierarchy. Every new project needs completely new XML.

2. **`jqa_violations_report.py` — `CONSTRAINT_CONTEXT` dict** — architectural explanation
   and practical impact text are also hardcoded per AMT constraint ID. New project = rewrite.

The fix is a two-step pipeline: *discover* what layers exist from the JAR graph, then
*generate* both the XML and the reporter context from a single source-of-truth YAML file
that a human can read and adjust in minutes.

---

### Deliverables

#### Script 1 — `jqa_discover_layers.py`
Location: `01_ingest/jqassistant/scripts/`

Queries Neo4j post-scan (requires live graph). Clusters `:Jar` nodes by name prefix using
the `group` property already written during ingest. Writes a draft `layers.yaml` to
`01_ingest/jqassistant/config/` (gitignored — it is project-specific input, not repo output).

**What this script cannot do alone:** establish the ordering of layers (which layer is
"higher" in the hierarchy). See the *Human Decision* section below — this is intentional.

**What this script does emit:** a heuristic confidence score per module family to help
the human decide ordering (`fan_in` = depended-upon by many = likely foundation;
`fan_out` = depends on many = likely orchestration/management layer).

#### `layers.yaml` schema

```yaml
# Archim8 layer model — edit `order` to reflect your architectural intent.
# Lower number = foundation (depended-upon). Higher number = management (depends on many).
# Heuristic: fan_in high → low order. fan_out high → high order.
# Run `make jqa-generate-rules` after any edit.

layers:
  - id: platform
    order: 1                 # <-- human sets this
    prefix: amt-platform
    maven_group: com.amt.platform
    description: "Core infrastructure — lowest layer, depended-upon by all others"
    heuristic_fan_in: 28     # discovered: 28 other modules depend on this family
    heuristic_fan_out: 2     # discovered: this family depends on 2 others
    heuristic_confidence: high

  - id: runtime
    order: 2
    prefix: amt-runtime
    maven_group: com.amt.runtime
    description: "Runtime lifecycle — depends on platform, depended-upon by services"
    heuristic_fan_in: 14
    heuristic_fan_out: 5
    heuristic_confidence: medium

  # ... one entry per discovered module family ...

constraints:
  # Pairs of (lower, higher) that must not have upward dependencies.
  # Auto-populated from layers list; human can delete any pair that is intentionally relaxed.
  - from: runtime      # runtime must not depend on something above it
    to: services
  - from: platform
    to: runtime
```

The only field a human must set is `order:`. Everything else is discovered or generated.

#### Script 2 — `jqa_generate_rules.py`
Location: `01_ingest/jqassistant/scripts/`

Reads `layers.yaml`. Produces:

- `01_ingest/jqassistant/rules/baseline/generated-constraints.xml` — jQA Cypher-based
  concepts (one `Concept` per layer, matching by prefix) and constraints
  (one `Constraint` per `constraints:` pair in YAML, enforcing no upward dependency).
  Committed to repo to show architectural intent; regenerated whenever `layers.yaml` changes.

- `01_ingest/jqassistant/config/constraint-context.yaml` — machine-readable context
  (architectural reason + practical impact) for each constraint ID, loaded by
  `jqa_violations_report.py` instead of the hardcoded `CONSTRAINT_CONTEXT` dict.

#### Reporter update — `jqa_violations_report.py`
Replace the hardcoded `CONSTRAINT_CONTEXT` dict with a YAML loader:

```python
context_path = config_dir / "constraint-context.yaml"
if context_path.exists():
    CONSTRAINT_CONTEXT = yaml.safe_load(context_path.read_text())
else:
    CONSTRAINT_CONTEXT = {}   # graceful fallback — report still runs, context rows empty
```

The report format, violation tables, and pass/fail summary are unchanged. Only the
"Why this matters" and "Practical impact" columns source from YAML instead of code.

#### Make targets

```makefile
jqa-discover-layers:    ## Discover module families from graph, write draft layers.yaml
    python 01_ingest/jqassistant/scripts/jqa_discover_layers.py

jqa-generate-rules:     ## Generate baseline XML + constraint-context.yaml from layers.yaml
    python 01_ingest/jqassistant/scripts/jqa_generate_rules.py
```

Both targets require Neo4j to be running (`make docker-up` first).
`jqa-generate-rules` can run offline if `layers.yaml` already exists.

---

### The human decision — layer ordering

> **This is the one thing that cannot be automated, and should not be.**

Layer ordering (`order:` in `layers.yaml`) is *architectural intent*. It answers the
question "which layer is allowed to depend on which?" No amount of bytecode analysis can
answer that — it requires domain knowledge of the system's purpose.

**Why we cannot infer it from the graph:**
The dependency graph shows *what depends on what* today. But architecture rules describe
*what is allowed to depend on what by design*. These are different: the violations report
may show that runtime currently depends on services (a violation), which means the graph
tells us the current ordering is wrong — but it cannot tell us which direction is correct.

**How we support the human in making this decision:**

**1. Heuristics in `layers.yaml` (Phase 7 built-in)**

Every layer entry carries `heuristic_fan_in`, `heuristic_fan_out`, and
`heuristic_confidence` populated by `jqa_discover_layers.py`. The pattern:

| Signal | Likely role | Example |
|--------|-------------|---------|
| High fan-in (many depend on it), low fan-out | Foundation layer — set `order: 1` or `2` | `amt-platform` |
| High fan-out (depends on many), low fan-in | Orchestration / management — set high `order` | `amt-messaging` |
| Balanced | Middle tier — place between the two extremes | `amt-runtime` |

The comment block in the generated YAML explains this pattern and gives example `order`
values pre-filled from the heuristic. The human validates or adjusts numbers; they do not
start from scratch.

**2. Ordering contradiction check in `jqa_generate_rules.py`**

Before generating XML, the script checks for bi-directional dependencies between any two
layer families in the current graph. If layer A and layer B have edges in both directions,
it warns:

```
WARNING: amt-runtime ↔ amt-services have dependencies in BOTH directions.
         This means any ordering you choose will produce violations.
         Review these specific JARs before finalising layers.yaml:
           amt-runtime-core → amt-services-api (3 dependency edges)
           amt-services-base → amt-runtime-lifecycle (1 dependency edge)
         Suggestion: consider splitting one family, or marking one direction as intentional.
```

This surfaces the hard cases immediately, before the human commits to an ordering.

**3. Agent-assisted confirmation path (long-term, Phase 7+ stretch)**

The query specialist already has access to the graph. An optional
`jqa-confirm-ordering` Make target would invoke the agent with a prompt like:

```
Given these module families and their dependency counts, suggest a layered ordering
and explain the rationale for each position. Flag any families where you are uncertain.
```

The agent's output is advisory only — it writes a `layers.yaml` candidate with a
`# suggested by agent — review before use` header, never overwrites a human-edited file.
The human reads the suggestion, edits `order:` values, then runs `jqa-generate-rules`.

**4. YAML comment template**

Every generated `layers.yaml` includes an inline decision guide:

```yaml
# HOW TO SET ORDER:
# 1. Start with heuristic_fan_in / heuristic_fan_out above.
# 2. Assign order: 1 to the layer everything else depends on.
# 3. Work outward: each layer that depends on layer N gets order N+1.
# 4. Run `make jqa-generate-rules` — if you see contradiction warnings,
#    you have a cycle or a misclassified JAR. Fix the YAML, not the code.
# 5. Run `make jqa-analyze` — violations should now describe real problems,
#    not artefacts of a wrong ordering.
```

---

### What stays the same

- Report format and section structure in `jqa-violations-report.md`
- Violation table columns (violatingJar, forbiddenDependency, forbiddenLayer)
- The `--[ Constraint Violation ]---` detection logic in the reporter
- jQA analyze container invocation (no changes to `jqa-analyze.ps1`)
- All existing `make jqa-*` targets (new targets are additive)

The only user-visible difference: `jqa_violations_report.py` sources context from YAML
instead of the Python file. If `constraint-context.yaml` is absent (e.g., fresh clone),
the report runs with empty context columns rather than failing.

---

### Phase 7 todos (completed 2026-03-13)

- [x] Write `jqa_discover_layers.py` (Neo4j → `layers.yaml` with heuristics)
- [x] Define `layers.yaml` schema (id, order, prefix, maven_group, description, heuristic_*)
- [x] Write `jqa_generate_rules.py` (YAML → baseline XML + constraint-context.yaml)
- [x] Update `jqa_violations_report.py` to load from `constraint-context.yaml` with fallback
- [x] Add `jqa-discover-layers` and `jqa-generate-rules` Make targets
- [x] Write contradiction checker in `jqa_generate_rules.py`
- [x] Document ordering decision guide in `layers.yaml` comment template
- [x] Gitignore `layers.yaml` and `constraint-context.yaml` (project-specific, not repo outputs)
- [x] `baseline.xml` replaced with generic placeholder — rules generated by `make jqa-generate-rules`
- [ ] (Stretch) `jqa-confirm-ordering` agent-assisted suggestion target

### Phase 7 prerequisites (exit criteria from Phase 5)

Before Phase 7 can start:
- [ ] All Phase 5 testing sub-phases accepted (5-T0 through 5-T6)
- [ ] Violations reporter (`jqa_violations_report.py`) has been used on at least one real analysis run and its output is trusted
- [ ] `layers.yaml` schema has been reviewed against at least two different target projects (to validate the prefix-clustering heuristic is general enough)

---

## Architecture Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-03 | Keep jdeps `:Jar`/`:DEPENDS_ON` layer separate from jQA layer | Avoid retooling working pipeline; layers complement each other |
| 2026-03-03 | Use jQA CLI JAR (not Maven plugin) | Archim8 is language-agnostic tooling; no Maven coupling desired |
| 2026-03-03 | APOC writes to `/import`; Makefile moves to `03_query` | Docker volume constraint; Makefile handles post-processing |
| 2026-03-03 | `group` = first hyphen-segment of JAR name | Consistent with target repo naming; enables clustering |
| 2026-03-03 | jQA CLI downloaded via `make jqa-install` (~100MB), gitignored | Keeps binary out of repo; repeatable setup |
| 2026-03-03 | Exclude test classes entirely from jQA scan | Architecture view should be clean production code only |
| 2026-03-03 | Exclude third-party `.m2/` dependencies from scan | Scope to target project only; external deps deferred |
| 2026-03-03 | Architecture constraints start as warnings, harden after first clean run | Avoid blocking pipeline on first scan; tighten once violations are reviewed |
| 2026-03-03 | Cycle whitelisting deferred to Phase 3 runtime | Run cycle detection first, inspect findings, then whitelist any intentional cycles explicitly |
| 2026-03-04 | Phase 4 redesigned as semantic graph views, not scripted CSV exports | Original plan (CSV → PlantUML templates) was too rigid; views with frontmatter headers enable Phase 5 manifest-driven querying |
| 2026-03-04 | Phase 5 redesigned as agentic facade, not RAG pipeline | Original RAG design put agent on top of scripts that inferred structure — graph already proves structure deterministically; agent should query graph directly |
| 2026-03-04 | Manifest pattern adopted to prevent agent regeneration | Agent checks manifest.json before any write; answers from existing views first, goes to graph only for novel/stale scope |
| 2026-03-04 | jQA confirmed fully Dockerized (archim8-jqa:2.9.1, 549MB) | Image built, container starts, Neo4j healthcheck passes; run-once pattern (not persistent service) is correct for scan workloads |
| 2026-03-09 | Phase 5 redesigned as multi-agent supervisor system | Single-agent-with-profiles is not genuinely agentic; LangGraph StateGraph enables real routing, chaining, and governance between independent specialist agents |
| 2026-03-09 | LangGraph `StateGraph` chosen over DIY supervisor loop | LangGraph already a dependency; StateGraph provides checkpointing, streaming, and conditional routing for free; no reason to rebuild it |
| 2026-03-09 | LlamaIndex explicitly excluded | Graph proves structure deterministically; RAG over unstructured documents is out of scope for Archim8 |
| 2026-03-10 | `.jqa-scan-lock` guard added to `jqa-scan.ps1` | Concurrent `make full-pipeline` invocations during 5-T3 started two jqa containers simultaneously, corrupting Neo4j data; lock file prevents re-entry |
| 2026-03-10 | `query.md` system prompt corrected to real graph schema | Prompt described `:Jar {name, layer}` — actual nodes are `:Jar {name, group, type, source, id}` with AMT layer encoded as a node label; caused agent to hallucinate `:COBOL` labels and return 0-row queries |
| 2026-03-10 | `archim8_agent.py` vs `orchestrator.py` role distinction documented | `archim8_agent.py` is lightweight single-agent for scripted/CI use (no supervisor, no Human Anchor); `orchestrator.py` is the primary interface for interactive sessions and write-path operations |
| 2026-03-10 | jqa re-scan completed successfully after corruption fix (17:46 → ~18:20) | Full clean scan restored graph integrity; `.jqa-scan-ok` marker written; COBOL and all other modules verified in graph |
| 2026-03-10 | `jqa_violations_report.py` added as auto-invoked post-analyze reporter | jQA XML violations output is machine-readable but not human-readable; structured MD with per-constraint arch context surfaces violations to developers without log parsing |
| 2026-03-10 | Reporter always exits 0; jqa-analyze always exits 0 | Violation presence is informational, not a pipeline failure gate at this stage; constraints set to `severity: warn`; hardening to `error` deferred to post-first-clean-run milestone |
| 2026-03-10 | `Tee-Object` log stays UTF-16 LE; Python reporter uses BOM detection | `Tee-Object -Encoding UTF8` not supported in PS5; BOM check (`raw_bytes[:2] in (b'\xff\xfe', b'\xfe\xff')`) is more robust than encoding parameter across PS5/PS7 |
| 2026-03-10 | Reporter context (`CONSTRAINT_CONTEXT`) hardcoded for AMT; Phase 7 will genericise | Acceptable for current scope; Phase 7 moves this to `constraint-context.yaml` generated from `layers.yaml` |
| 2026-03-10 | Layer ordering (`order:`) designated as the sole required human input in Phase 7 | Bytecode analysis can cluster modules by prefix and score heuristically by fan-in/fan-out; it cannot resolve architectural intent — which layer is *allowed* to depend on which is a design decision, not an observation |

---

## Post-Phase-5 Housekeeping (2026-03-10)

Completed before Phase 6 begins:

- [x] Concurrent jqa scan bug fixed (`jqa-scan.ps1` lock guard)
- [x] Corrupt graph repaired via full re-scan (completed ~18:20)
- [x] `query.md` system prompt corrected with real schema (`:Jar {name, group, type, source, id}`, AMT layer labels, correct COBOL matching)
- [x] `archim8_agent.py` role documented (scripted/CI use vs `orchestrator.py` for interactive)
- [x] README restructure proposal written (`README-PROPOSAL.md`) — pending user approval before overwriting `README.md`
- [x] Confirmed Neo4j data is **not** lost on `docker compose down` — bind mounts to `02_store/neo4j/docker/data/` persist on disk; only `docker compose down -v` would destroy data (never run that)

---

## Next session — resume checklist

Pick up from here at next login:

### Immediate (before any agent work)
- [ ] `make docker-up` — bring Neo4j back up (data will be intact; ~30 s to healthy)
- [ ] Verify graph: `python -c "import sys; sys.path.insert(0,'06_agents'); import tools.graph_query as g; g.init_driver('bolt://localhost:7687','neo4j','password'); print(g.run_cypher_query.func('MATCH (j:Jar) RETURN count(j)')); g.close_driver()"`

### Phase 7 — first real run
- [ ] `make jqa-discover-layers` against live graph — produces `layers.yaml`
- [ ] Review `layers.yaml`, set `order:` values to reflect architectural intent
- [ ] `make jqa-generate-rules` — produces `generated-constraints.xml` + `constraint-context.yaml`
- [ ] `make jqa-analyze` — violations reporter should now use YAML context
- [ ] Test against a second Java project (`ARCHIM8_TARGET_REPO` → different repo) — Phase 10 gate check

### README decision
- [ ] Review `README-PROPOSAL.md` — if happy with the structure, say the word and Copilot will replace `README.md`
- [ ] Once README is accepted, delete `README-PROPOSAL.md`

### Phase 10 gate check items (in progress)
- [ ] Point `ARCHIM8_TARGET_REPO` at a second Java project and run `make full-pipeline && make generate-all`
- [ ] Verify no manual config edits needed — all layer labels inferred from graph
- [ ] Update Phase 10 acceptance criteria checkboxes once validated

---

## Phase 8 — MCP Migration ✅ Complete

**Completed:** 2026-05-26

**Goal:** Replace the LangGraph Python orchestrator with a GitHub Copilot MCP server.
Claude in Copilot Enterprise becomes the reasoning model; Archim8 exposes tools via MCP.

**Why:** GitHub Models `gpt-4o` has an 8192-token hard cap making multi-tool sessions
unusable. Claude in Copilot Enterprise has a 200k token window, is already in the IDE,
requires no separate credentials, and produces higher-quality reasoning.

### Deliverables

- [x] `MCP-MIGRATION-AUDIT.md` — full audit of all file changes, credential approach, design decisions
- [x] `06_agents/mcp_server.py` — FastMCP server; all tools registered
- [x] `.vscode/mcp.json` — VS Code MCP server registration (auto-start on workspace open)
- [x] `.github/copilot-instructions.md` — grounding contract; Human Anchor rules; tool contracts
- [x] `06_agents/tools/*.py` — `@tool` (LangChain) decorators removed; plain functions
- [x] `requirements.txt` — LangChain/LangGraph/OpenAI removed; `mcp` + `python-dotenv` added
- [x] `14_tests/test_mcp_server.py` — MCP smoke test (T0–T6)
- [x] Removed: `orchestrator.py`, `archim8_agent.py`, `specialists/`, `config/profiles/`
- [x] Removed: `14_tests/smoke_test_agent.py`, `smoke_test_orchestrator.py`, `test_5t6_human_anchor.py`
- [x] Removed: LLM env variables from `archim8.local.env` and template
- [x] Removed: `agent*` / `orchestrate*` Makefile targets
- [x] Updated: `make smoke` → runs `test_mcp_server.py`
- [x] Updated: all READMEs referencing LangGraph/agents
- [x] `04_generate/agents/guardrails/` — populate with Cypher constraint validation schemas
- [x] `04_generate/agents/prompts/` — populate with Mermaid/PlantUML template files
- [x] `04_generate/agents/config/` — populate with generate tool configuration
- [ ] `04_generate/agents/chunking/` — DELETE (RAG concept, out of scope) — deferred
- [ ] `04_generate/agents/indexing/` — DELETE (RAG concept, out of scope) — deferred
- [x] `generate_mermaid_diagram` tool — queries graph, writes `.mmd` to `05_deliver/output/diagrams/`
- [x] `ARCHIM8-TRACKER.md` Phase 8 — mark complete when all items done
- [ ] `git commit -m "feat: Phase 8 — replace LangGraph orchestrator with MCP server"`

### Phase 8 gate check
- [x] `make smoke` passes (T0–T6)
- [x] MCP server starts and tools appear in Copilot Chat tool list
- [x] At least one graph query succeeds from Copilot Chat
- [x] Write-path Human Anchor fires (confirmation prompt shown before `run_make_target`)
- [x] `generate_mermaid_diagram` writes to disk (file exists after call)

---

## Phase 9 — Architecture Documentation Framework ✅ Complete

**Completed:** 2026-05-26

**Goal:** Establish a repeatable, graph-grounded documentation pipeline. Every claim in the
architecture document traces to a graph node, an edge in a view, or static analysis evidence.
No LLM hallucination in the output artefact.

### Deliverables

- [x] `06_agents/prompts/documentor.md` — Documentor specialist prompt; Pattern A (full section) and Pattern B (additional diagram) templates; heading mandate `### C{level} - {Name}` before every diagram embed
- [x] `.github/prompts/archim8_agent.prompt.md` — VS Code Copilot Chat agent mode prompt; activate with `@archim8_agent` in Chat
- [x] `05_deliver/output/AMT-GO_Architecture.md` — Concrete architecture document produced by the pipeline; v0.4; §1 Context, §2 Platform Architecture, §3 Observability (logging stack), §4 Engineering References — Observability, §5 Batch Program Invocation, §6 Database Management, §7 AuthN/AuthZ
- [x] `05_deliver/output/diagrams/` — SVG rendering pipeline established; `.mmd` = source of truth; `.svg` = rendered output; `mmdc` v11 via npx
- [x] `05_deliver/output/diagrams/overview/` — C2-Architecture.mmd + .svg
- [x] `05_deliver/output/diagrams/actors/` — C3-Actor-Pattern.mmd + .svg, C4-Transaction-Manager.mmd + .svg, C4-Job-Manager.mmd + .svg, C4-File-Manager.mmd + .svg
- [x] `05_deliver/output/diagrams/observability/` — C2-Observability.mmd + .svg, C3-MDC-Propagation.mmd + .svg, C4-Logging-Stack.mmd + .svg
- [x] `MCP-MIGRATION-AUDIT.md` — deleted; added to `.gitignore`

### Conventions established

- All diagram embeds in architecture docs use `### C{level} - {Name}` heading immediately before the `![]()` image link
- `.mmd` files are source of truth; `.svg` files are regenerated via `npx @mermaid-js/mermaid-cli`
- Flowchart node labels use ` · ` as separator (not `\n` — not rendered by mmdc)
- All `classDiagram` files (C4-level) use member-per-line syntax — no `\n` needed
- Document versioning: Document Control table at top of each architecture doc; increment on each section addition

### Phase 9 gate check
- [x] `documentor.md` has Pattern A and Pattern B with heading mandate
- [x] At least one complete architecture section written (§1, §2, §3 all complete)
- [x] All diagram embeds link to `.svg` files (not `.mmd`)
- [x] All `.mmd` files render cleanly to SVG via `mmdc` (no literal `\n` in labels)


---

## Phase 10 — Framework Abstraction 🔄 Planned

**Goal:** Remove all target-specific content from Archim8 (layer labels, module names, rule assumptions) so the tool works generically against any Java project. The user workflow becomes: point `ARCHIM8_TARGET_REPO` at a project → pipeline infers structure automatically → no manual configuration of layer names or module patterns required.

This is not just a refactor — it is a correctness improvement. Hardcoded module names and layer labels are assumptions that break the moment the tool is pointed at a different codebase. The framework abstraction phase makes those assumptions explicit, externalises them to per-project config, and eventually eliminates even those through inference.

### Key questions to resolve before implementation

- **Layer label strategy**: Should layers be auto-inferred from package naming conventions, or supplied by the user in a config file? Both models have different failure modes (inference can be wrong; config requires upfront knowledge).
- **jQA rules**: Should violation rules be data-driven (a config file listing `from_layer → to_layer: FORBIDDEN`) rather than hardcoded Cypher? This makes rules portable across projects.
- **Diagram templates**: Should templates be re-parameterised (replacing hardcoded module names with query results) or regenerated fresh per project? Fresh generation is more correct; re-parameterisation is faster.
- **Cypher query library**: Most queries in `03_query/cypher/library/` are already generic — they operate on graph labels, not project-specific node properties. Audit required to confirm.

### Acceptance criteria

- [ ] `ARCHIM8_TARGET_REPO` can be pointed at any Java project with Maven/Gradle build
- [ ] Full pipeline (`make full-pipeline && make generate-all`) completes without project-specific config
- [ ] All layer labels and module names are read from project metadata or config — none hardcoded in scripts or queries
- [ ] `jqassistant.yml` violation rules are parameterised from a data file, not inline Cypher strings
- [ ] `05_deliver/output/` contains a valid architecture view and at least one diagram for the new target project
- [ ] README documents the per-project config options

### Phase 10 gate check

- [ ] No hardcoded project-specific strings in `03_query/`, `04_generate/`, or `01_ingest/`
- [ ] New target project completes full pipeline with no manual intervention
- [ ] Per-project config documented and validated by `make doctor`
