# 06_agents — MCP Server (Layer 7)

The Archim8 MCP (Model Context Protocol) server. Exposes all Archim8 tools to GitHub Copilot Chat.

---

## Structure

```
06_agents/
├── mcp_server.py                 # MCP server — main entry point (auto-started by VS Code)
├── tools/
│   ├── graph_query.py              # run_cypher_query, apply_cypher_migration
│   ├── view_reader.py              # list_available_views, read_architecture_view
│   ├── diagram_gen.py              # generate_architecture_diagram
│   ├── shell_exec.py               # run_make_target, check_file_exists, read_log_file
│   ├── docker_health.py            # check_docker_health
│   └── __init__.py
└── (specialists/, orchestrator.py, config/ removed in Phase 8 — superseded by MCP)
```

---

## How it works

VS Code starts the MCP server automatically when you open this workspace (configured in
`.vscode/mcp.json`). The server loads credentials from
`00_orchestrate/config/archim8.local.env` and registers all tools with FastMCP.

In Copilot Chat (Claude), you can then ask architecture questions directly:

> "What are the highest fan-in modules in the Platform layer?"
> "Generate a Mermaid class diagram of the MessageQueue subsystem"
> "Run jqa-analyze and show me the violations summary"

Claude decides which tools to call; all tool calls are visible in the chat UI.

---

## Tools registered

| Tool | Category | What it does |
|------|---------|--------------|
| `archim8_run_cypher_query` | Read | Execute read-only Cypher against Neo4j |
| `archim8_list_available_views` | Read | List pre-generated views from manifest |
| `archim8_read_architecture_view` | Read | Read a named view file |
| `archim8_check_file_exists` | Read | Check if a file/dir exists in the workspace |
| `archim8_read_log_file` | Read | Read last N lines of a pipeline log |
| `archim8_check_docker_health` | Read | Check Archim8 Docker container status |
| `archim8_generate_architecture_diagram` | Write ⚠️ | Generate PlantUML C4 diagram to `05_deliver/output/` |
| `archim8_run_make_target` | Write ⚠️ | Run an allowlisted Makefile target |
| `archim8_apply_cypher_migration` | Write ⚠️ | Execute a schema migration `.cypher` file |

⚠️ Write-path tools always require explicit user confirmation — governed by the Human Anchor
rules in `.github/copilot-instructions.md`.

---

## Human Anchor

In the MCP model, Human Anchor is enforced by `.github/copilot-instructions.md`:
- Every write-path tool docstring contains a `⚠️` marker
- The instructions file explicitly names all write-path tools and requires explicit
  user confirmation ("yes" / "confirm" / "proceed") before any tool call that changes state
- Claude’s native reasoning respects these rules consistently

---

## Smoke test

```powershell
make smoke          # Runs 14_tests/test_mcp_server.py (no live Neo4j required)
```

Covers: `mcp` importable, `FastMCP` instantiable, all tools registered, write-path tools
have `⚠️` marker, query/migration error when driver not configured.

---

## Manual start (outside VS Code)

```powershell
make mcp-start
# or
python 06_agents/mcp_server.py
```


---

## Structure

```
06_agents/
├── orchestrator.py                 # LangGraph StateGraph supervisor — main entry point
├── archim8_agent.py               # Single-agent entry point (read-only; CI / scripting)
├── specialists/
│   ├── infra_agent.py              # Docker, Make, pre-flight checks, logs
│   ├── ingest_agent.py             # Scan triggers, coverage, ingestion health
│   ├── store_agent.py              # Neo4j schema, migration status, data quality
│   ├── query_agent.py              # Deep architecture analysis, novel Cypher
│   ├── generate_agent.py           # View/diagram generation, staleness checks
│   ├── deliver_agent.py            # Stakeholder-facing answers, view synthesis
│   └── __init__.py
├── tools/
│   ├── graph_query.py              # graph_query — execute Cypher against Neo4j
│   ├── view_reader.py              # read_architecture_view, list_available_views
│   ├── diagram_gen.py              # generate_architecture_diagram
│   ├── shell_exec.py               # run_make_target, check_file_exists, read_log_file
│   ├── docker_health.py            # check_docker_health
│   └── __init__.py
├── prompts/
│   ├── system.md                   # Shared system context injected to all agents
│   ├── orchestrator.md             # Routing instructions + governance rules
│   ├── infra.md
│   ├── ingest.md
│   ├── store.md
│   ├── query.md
│   ├── generate.md
│   └── deliver.md
└── config/
    ├── agent.yaml                  # Default config (Azure OpenAI)
    └── profiles/
        ├── github-models.yaml      # Free-tier GitHub Models endpoint
        ├── local.yaml              # Standard OpenAI
        ├── analyst.yaml            # Read-only; no shell/docker/migration
        ├── pipeline.yaml           # Full tool budget; migration off by default
        └── operator.yaml          # Full tool budget including migration ⚠️
```

---

## How to run

### Interactive (recommended)

```powershell
# GitHub Models (free)
python 06_agents/orchestrator.py --profile github-models
make orchestrate-github

# Azure OpenAI (default config)
python 06_agents/orchestrator.py
make orchestrate

# Standard OpenAI
python 06_agents/orchestrator.py --profile local
make orchestrate-local
```

Type your question at the prompt. Type `exit` to quit.

### Single question (scriptable)

```powershell
python 06_agents/orchestrator.py --profile github-models "What modules exist?"
make orchestrate-ask QUESTION="What are the main dependencies?"
```

### Single-agent (read-only, no governance overhead)

```powershell
python 06_agents/archim8_agent.py --profile github-models "What gRPC services exist?"
make agent-github
```

### Smoke tests (no live deps needed)

```powershell
make smoke                  # both tests
make smoke-orchestrator     # StateGraph compilation + safety guards (no live Neo4j/LLM)
make smoke-agent            # legacy single-agent import test
```

---

## Profiles

See the [README profile reference](../README.md#profile-reference) for the full table. Quick summary:

| Profile | Intent | Migration enabled? |
|---------|--------|-------------------|
| `github-models` | General use, GitHub free tier | No |
| `local` | Standard OpenAI | No |
| `analyst` | Read-only; no shell/docker | No |
| `pipeline` | CI/CD; shell + docker | No |
| `operator` | Full write path ⚠️ | **Yes** |

---

## Tool budget model

Each profile specifies which tools are available to agents. Agents can only call tools they've been given. The orchestrator enforces the Human Anchor gate — any routing to a write-path agent (store, infra when writing) pauses for human approval first.

| Tool | Purpose | Profiles with access |
|------|---------|---------------------|
| `graph_query` | Execute read Cypher | All |
| `view_reader` | Read Markdown views, list manifest | All |
| `diagram_gen` | Generate PlantUML diagrams | All except `analyst` |
| `shell_exec` | Run Make targets, read logs | `pipeline`, `operator` |
| `docker_health` | Check container status | `pipeline`, `operator` |
| `run_cypher_migration` | Execute schema migrations | `operator` only |

---

## Human Anchor

Every write operation pauses the LangGraph `StateGraph` at an `interrupt_before` checkpoint. The agent presents its proposed action; the human approves or cancels. The graph resumes (or terminates) based on that decision.

See [Key Agentic Principles](../README.md#-key-agentic-principles--the-human-anchor) in the main README.
