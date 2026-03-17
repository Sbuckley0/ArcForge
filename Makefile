# =============================================================================
# Archim8 Makefile
#
# Quickstart:
#   make docker-up          start Neo4j (volume paths from archim8.local.env)
#   make jdeps-pipeline     jdeps run -> Neo4j init -> load CSV -> export
#   make jqa-pipeline       jQAssistant scan -> analyze -> export  [Phase 1+]
#   make full-pipeline      jdeps-pipeline + jqa-pipeline
#   make help               all targets
#
# Override creds:  make neo4j-ingest NEO4J_PASSWORD=mypassword
# =============================================================================

# =============================================================================
# GLOBAL PARAMETERS
# =============================================================================

# Neo4j connection
NEO4J_USER      ?= neo4j
NEO4J_PASSWORD  ?= password
NEO4J_CONTAINER ?= archim8-neo4j

# Docker
COMPOSE_FILE     = 02_store/neo4j/docker/docker-compose.yml
LOCAL_ENV        = 00_orchestrate/config/archim8.local.env

# Pipeline directories
INGEST_DIR  = 05_deliver/input/01_ingest
QUERY_DIR   = 05_deliver/input/03_query

# jQAssistant
JQA_VERSION  = 2.9.1
JQA_IMAGE    = archim8-jqa:$(JQA_VERSION)
JQA_CONFIG   = 01_ingest/jqassistant/config/jqassistant.yml
JQA_RULES    = 01_ingest/jqassistant/rules

# Python executable (override if needed: make generate-views PYTHON=python3)
PYTHON ?= c:/python314/python.exe

# Generator scripts
GEN_VIEWS_SCRIPT    = 04_generate/generators/scripts/generate_views.py
GEN_PLANTUML_SCRIPT = 04_generate/generators/scripts/generate_plantuml.py

# MCP server script
MCP_SERVER = 06_agents/mcp_server.py

.PHONY: help \
        jdeps-pipeline jqa-pipeline full-pipeline ingest-pipeline generate-pipeline \
        jdeps jdeps-skip jdeps-filter \
        docker-up docker-down docker-restart docker-logs \
        neo4j-wait neo4j-init neo4j-migrate neo4j-ingest neo4j-setup neo4j-export neo4j-verify \
        jqa-install jqa-scan jqa-analyze jqa-violations-report jqa-export jqa-verify jqa-reset jqa-pipeline jqa-discover-layers jqa-generate-rules \
        generate-views generate-diagrams generate-all \
        mcp-start \
        setup test smoke clean \
        doctor status _check-doctor \
        stop teardown teardown-all

# =============================================================================
# HELP
# =============================================================================
help:
	@echo ""
	@echo "Archim8 - Architecture Extraction Engine"
	@echo ""
	@echo "--- PIPELINE COMMANDS ---"
	@echo "  jdeps-pipeline     docker-up -> jdeps scan -> schema + load -> export"
	@echo "  jqa-pipeline       docker-up -> jqa-install (idempotent) -> scan -> verify"
	@echo "  full-pipeline      jdeps-pipeline then jqa-pipeline (end-to-end)"
	@echo ""
	@echo "--- LAYER 0: INFRASTRUCTURE ---"
	@echo "  docker-up          Start Neo4j (guards against duplicate containers)"
	@echo "  stop               Suspend containers (keep registered + data safe)"
	@echo "  teardown           Remove containers, preserve data on disk"
	@echo "  teardown-all       DESTRUCTIVE: remove containers + delete all graph data"
	@echo "  docker-logs        Tail container logs"
	@echo "  neo4j-wait         Poll until Neo4j accepts connections"
	@echo ""
	@echo "--- LAYER 1a: INGEST / jdeps ---"
	@echo "  jdeps              Maven build + jdeps run + CSV extract"
	@echo "  jdeps-skip         jdeps run + CSV extract (skip Maven build)"
	@echo "  jdeps-filter       jdeps + CSV, skip build, strip JDK edges"
	@echo ""
	@echo "--- LAYER 1b: INGEST / jQAssistant  [Phase 1+] ---"
	@echo "  jqa-install        Build jQAssistant Docker image ($(JQA_IMAGE))"
	@echo "  jqa-scan           Scanner: bytecode + Maven POMs -> Neo4j"
	@echo "  jqa-analyze        Rules engine: concepts + constraints"
	@echo "  jqa-violations-report  Architecture health report from last jqa-analyze log"
	@echo "  jqa-discover-layers    Phase 7: introspect graph, propose layer ordering, write layers.yaml"
	@echo "  jqa-generate-rules     Phase 7: generate baseline XML + constraint-context.yaml from layers.yaml"
	@echo "  jqa-reset          Remove all jQA-owned nodes from Neo4j"
	@echo ""
	@echo "--- LAYER 2: STORE / NEO4J SCHEMA ---"
	@echo "  neo4j-init         Constraints + indexes + bootstrap node"
	@echo "  neo4j-migrate      Run schema migrations (tag layer='jdeps' on DEPENDS_ON)"
	@echo "  neo4j-ingest       LOAD CSV jdeps-jar-edges.csv -> :Jar + :DEPENDS_ON"
	@echo "  neo4j-setup        neo4j-init + neo4j-migrate + neo4j-ingest"
	@echo ""
	@echo "--- LAYER 3: QUERY / EXPORT ---"
	@echo "  neo4j-export       APOC jdeps exports -> 05_deliver/input/03_query/"
	@echo "  neo4j-verify       Print :Jar + :DEPENDS_ON counts"
	@echo "  jqa-export         jQA query exports -> 05_deliver/input/03_query/  [Phase 4+]"
	@echo "  jqa-verify         Print jQA node counts (MavenModule, Type, Package)"
	@echo ""
	@echo "--- LAYER 4: GENERATE / VIEWS  [Phase 4] ---"
	@echo "  generate-views     Run 8 Cypher queries -> 05_deliver/output/views/*.md"
	@echo "  generate-diagrams  Generate PlantUML C4 diagrams from graph"
	@echo "  generate-all       generate-views + generate-diagrams"
	@echo "  generate-pipeline  jqa-pipeline + generate-all  (full Phase 4 run)"
	@echo ""
	@echo "--- LAYER 5 / LAYER 7: MCP SERVER  [Phase 8] ---"
	@echo "  mcp-start          Start the Archim8 MCP server (for manual testing)"
	@echo "                     Note: VS Code starts it automatically via .vscode/mcp.json"
	@echo "                     Use Copilot Chat for all architecture queries"
	@echo ""
	@echo "--- DEV / TOOLING ---"
	@echo "  doctor             Full setup check: tools, versions, config, connectivity"
	@echo "  status             Session check: tools, services, graph data"
	@echo "  setup              pip install -r requirements.txt"
	@echo "  smoke              MCP server smoke test (no live deps required)"
	@echo "  test               pytest 14_tests/ (full suite)"
	@echo "  clean              Remove generated outputs"
	@echo ""

# =============================================================================
# PIPELINE COMMANDS
# High-level entry points — each composes lower-level layer targets
# =============================================================================

# jdeps end-to-end: infra up -> wait -> jdeps scan + CSV -> schema + load -> export
jdeps-pipeline: _check-doctor docker-up neo4j-wait jdeps-skip neo4j-setup neo4j-export
	@echo ""
	@echo "jdeps pipeline complete."
	@echo "  Outputs: $(QUERY_DIR)/jar-deps.csv, top-incoming.csv, top-outgoing.csv"
	@echo "  make neo4j-verify   -- confirm counts"

# jQA end-to-end: infra up -> build image (idempotent) -> scan -> analyze -> verify
jqa-pipeline: _check-doctor docker-up jqa-install jqa-scan jqa-analyze jqa-verify
	@echo ""
	@echo "jQAssistant pipeline complete."
	@echo "  make jqa-verify   -- confirm node counts"
	@echo "  Report: 05_deliver/input/01_ingest/jqa-report/"

# Full pipeline: both ingest layers end-to-end
full-pipeline: jdeps-pipeline jqa-pipeline
	@echo ""
	@echo "Full Archim8 pipeline complete."

# Phase 4 pipeline: jQA + all view generation
generate-pipeline: jqa-pipeline generate-all
	@echo ""
	@echo "Phase 4 generate pipeline complete."
	@echo "  Views:    05_deliver/output/views/"
	@echo "  Diagrams: 05_deliver/output/arc-containers.puml"

# Alias for backward compatibility
ingest-pipeline: jdeps-pipeline

# =============================================================================
# LAYER 0: INFRASTRUCTURE
# Docker lifecycle + Neo4j readiness
# =============================================================================

# Start Neo4j — checks for existing container first to prevent duplicates.
# If already running: reports status and exits cleanly (no-op).
# If stopped/exited: restarts, reusing existing bind-mount data.
# If not found: creates fresh container.
docker-up:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/archim8-startup.ps1

# Suspend containers (keep them registered + all data safe — fastest resume)
stop:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/archim8-teardown.ps1 -Mode stop

# Remove containers, preserve graph data on disk (safe default teardown)
teardown:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/archim8-teardown.ps1 -Mode down

# DESTRUCTIVE — remove containers + permanently delete all Neo4j graph data.
# Requires typing 'delete-all' at the confirmation prompt.
teardown-all:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/archim8-teardown.ps1 -Mode all

# Backward-compatible alias (same as teardown)
docker-down: teardown

docker-restart: teardown docker-up

docker-logs:
	docker compose -f $(COMPOSE_FILE) logs -f

# Poll until cypher-shell connects (up to 2 min / 24 x 5s)
neo4j-wait:
	powershell -NoProfile -Command "Write-Host 'Waiting for Neo4j...'; for ($$i=1; $$i -le 24; $$i++) { docker exec $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) 'RETURN 1' 2>&1 | Out-Null; if ($$LASTEXITCODE -eq 0) { Write-Host 'Neo4j ready.'; exit 0 }; Start-Sleep 5 }; Write-Error 'Neo4j not ready after 120s'; exit 1"

# =============================================================================
# LAYER 1a: INGEST — jdeps
# Extracts JAR-level dependency edges from compiled bytecode
# =============================================================================

jdeps:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/pipelines/run-jdeps-pipeline.ps1

jdeps-skip:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/pipelines/run-jdeps-pipeline.ps1 -SkipBuild

jdeps-filter:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/pipelines/run-jdeps-pipeline.ps1 -SkipBuild -FilterJava

# =============================================================================
# LAYER 1b: INGEST — jQAssistant  [Phase 1+ — stubs until wired]
# Structural code graph: Maven modules, packages, types, methods
# Runs via Docker container (archim8-jqa) on the same compose network as Neo4j.
# See JQASSISTANT-INTEGRATION.md for implementation plan
# =============================================================================

# Build the archim8-jqa Docker image (idempotent — skips if image already exists)
jqa-install:
	powershell -NoProfile -ExecutionPolicy Bypass -File 01_ingest/jqassistant/scripts/jqa-install.ps1

# Run scanner: bytecode + Maven POMs -> Neo4j (via archim8-jqa container)
# Pass SCAN_PATH=<dir> to override ARCHIM8_TARGET_REPO for a single run
# Pass FORCE=1 to re-run even if .jqa-scan-ok marker exists
jqa-scan:
	powershell -NoProfile -ExecutionPolicy Bypass -File 01_ingest/jqassistant/scripts/jqa-scan.ps1 $(if $(SCAN_PATH),-ScanPath $(SCAN_PATH)) $(if $(FORCE),-Force)

# Run rules engine: concepts + constraints + metrics
jqa-analyze:
	powershell -NoProfile -ExecutionPolicy Bypass -File 01_ingest/jqassistant/scripts/jqa-analyze.ps1

# Generate architecture health Markdown report from the last jqa-analyze log
# Output: 05_deliver/input/01_ingest/jqa-violations-report.md (internal — not for external distribution)
jqa-violations-report:
	python 01_ingest/jqassistant/scripts/jqa_violations_report.py

# Phase 7: query the graph, cluster JARs by module family, propose layer order, write layers.yaml
# Run AFTER jqa-scan (Neo4j must be populated).  Output: 01_ingest/jqassistant/config/layers.yaml
jqa-discover-layers:
	$(PYTHON) 01_ingest/jqassistant/scripts/jqa_discover_layers.py

# Phase 7: read layers.yaml, generate:  rules/baseline/generated-constraints.xml
#           config/constraint-context.yaml  and update jqassistant.yml group name
# Run AFTER editing layers.yaml (set `order` for each layer).  Idempotent.
jqa-generate-rules:
	$(PYTHON) 01_ingest/jqassistant/scripts/jqa_generate_rules.py

# Remove all jQA-owned nodes from Neo4j (preserves :Jar / jdeps data)
# Labels removed: :Maven:* and :Java:* (all jQA-managed structural nodes)
jqa-reset:
	docker exec $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) "MATCH (n) WHERE (n:Maven OR n:Java) AND NOT n:Jar AND NOT n:Meta DETACH DELETE n RETURN count(n) AS nodesDeleted;"

# =============================================================================
# LAYER 2: STORE — Neo4j Schema
# Idempotent schema setup and data loading
# =============================================================================

# Constraints + indexes + bootstrap meta-node
neo4j-init:
	docker exec $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) --file /init/01-constraints.cypher
	docker exec $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) --file /init/02-index.cypher
	docker exec $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) --file /init/03-bootstrap.cypher

# Run schema migrations (idempotent — safe to re-run)
# 0001: tags existing :DEPENDS_ON edges with layer='jdeps' before jQA scan
neo4j-migrate:
	powershell -NoProfile -Command "Get-ChildItem 02_store/neo4j/config/schema/migrations/*.cypher | Sort-Object Name | ForEach-Object { Write-Host ('Applying migration: ' + $$_.Name); Get-Content -Raw $$_.FullName | docker exec -i $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) }"

# LOAD CSV jdeps-jar-edges.csv -> :Jar nodes + :DEPENDS_ON relationships
neo4j-ingest:
	powershell -NoProfile -Command "Get-Content -Raw 03_query/cypher/library/jdeps/neo4j-ingest-jdeps.cypher | docker exec -i $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD)"

neo4j-setup: neo4j-init neo4j-migrate neo4j-ingest

# =============================================================================
# LAYER 3: QUERY / EXPORT
# APOC-driven exports from the live graph -> pipeline deliver dirs
# APOC writes to /import (= INGEST_DIR); Makefile moves files to QUERY_DIR
# =============================================================================

# jdeps APOC exports: jar-deps, top-incoming, top-outgoing, cycles
neo4j-export:
	powershell -NoProfile -Command "Get-Content -Raw 03_query/cypher/library/jdeps/neo4j-export-jdeps.cypher | docker exec -i $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD)"
	powershell -NoProfile -Command "@('jar-deps.csv','top-incoming.csv','top-outgoing.csv','cycles.csv') | ForEach-Object { $$src = '$(INGEST_DIR)/' + $$_; $$dst = '$(QUERY_DIR)/' + $$_; if (Test-Path $$src) { Move-Item -Force $$src $$dst; Write-Host \"Moved $$_ -> $(QUERY_DIR)/\" } else { Write-Warning \"Not found: $$src\" } }; $$cyclesDst = '$(QUERY_DIR)/cycles.csv'; if (Test-Path $$cyclesDst) { $$lines = (Get-Content $$cyclesDst | Measure-Object -Line).Lines; if ($$lines -le 1) { $$emptyDst = '$(QUERY_DIR)/(empty)_cycles.csv'; Remove-Item '$(QUERY_DIR)/(empty)_cycles.csv' -Force -ErrorAction SilentlyContinue; Rename-Item -Path $$cyclesDst -NewName '(empty)_cycles.csv'; Write-Host 'cycles.csv has 0 smells -> renamed to (empty)_cycles.csv' } }"

# Sanity check: :Jar node + :DEPENDS_ON relationship counts
neo4j-verify:
	docker exec $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) "MATCH (j:Jar) RETURN count(j) AS jars; MATCH ()-[r:DEPENDS_ON]->() RETURN count(r) AS edges;"

# jQAssistant query exports — alias for generate-views (Phase 4)
jqa-export: generate-views

# jQAssistant node count sanity check
jqa-verify:
	docker exec $(NEO4J_CONTAINER) cypher-shell -u $(NEO4J_USER) -p $(NEO4J_PASSWORD) "MATCH (n:Maven) RETURN 'Maven' AS label, count(n) AS count UNION MATCH (n:Java) RETURN 'Java' AS label, count(n) AS count UNION MATCH (n:Jar) RETURN 'Jar' AS label, count(n) AS count;"

# =============================================================================
# LAYER 4: GENERATE / VIEWS  [Phase 4]
# Runs Cypher queries against live Neo4j and produces structured Markdown views
# and PlantUML C4 diagrams.
# =============================================================================

# Run all 8 semantic view queries -> 05_deliver/output/views/*.md
# Use FORCE=1 to regenerate views already in manifest:
#   make generate-views FORCE=1
generate-views:
	$(PYTHON) $(GEN_VIEWS_SCRIPT) $(if $(FORCE),--force) $(if $(VIEW),--view $(VIEW))

# Generate PlantUML C4 diagrams from the live graph
# Use DIAGRAM=containers|cobol|all and FORCE=1 as needed
generate-diagrams:
	$(PYTHON) $(GEN_PLANTUML_SCRIPT) --diagram $(or $(DIAGRAM),all) $(if $(FORCE),--force)

# Both views and diagrams
generate-all: generate-views generate-diagrams
	@echo ""
	@echo "Phase 4 outputs complete."
	@echo "  Views:    05_deliver/output/views/  (8 Markdown files)"
	@echo "  Diagrams: 05_deliver/output/arc-containers.puml"
	@echo "             05_deliver/output/arc-cobol-emulation.puml"
	@echo "  Manifest: 05_deliver/output/manifest.json"

# =============================================================================
# LAYER 5: AGENT  [Phase 5]
# LangGraph ReAct agent — queries Neo4j at runtime, reads views from manifest
# =============================================================================
# LAYER 7: MCP SERVER
# Archim8 tools exposed to GitHub Copilot Chat via Model Context Protocol
# VS Code starts this automatically via .vscode/mcp.json
# =============================================================================

# Manual start (for debugging or testing outside VS Code)
mcp-start:
	$(PYTHON) $(MCP_SERVER)

# =============================================================================
# DEV / TOOLING
# =============================================================================

setup:
	$(PYTHON) -m pip install -r requirements.txt

# Run all tests via pytest
test:
	pytest 14_tests/

# MCP server smoke test (no live deps required)
smoke:
	$(PYTHON) 14_tests/test_mcp_server.py

clean:
	rm -rf output/ generated/ exports/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Internal: advisory banner when pipelines are run without a prior 'make doctor'
_check-doctor:
	@powershell -NoProfile -Command "if (-not (Test-Path '.archim8-doctor-ok')) { Write-Host ''; Write-Host '[!] First-time setup not verified. Run: make doctor for an environment check.' -ForegroundColor Yellow; Write-Host '' }"

# First-time full setup verification: runtime tools, Python env, config, connectivity
# Writes .archim8-doctor-ok on success (0 errors).
doctor:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/archim8-doctor.ps1

# Per-session health check: quick tool audit + service health + graph data (no network)
status:
	powershell -NoProfile -ExecutionPolicy Bypass -File 00_orchestrate/scripts/archim8-status.ps1
