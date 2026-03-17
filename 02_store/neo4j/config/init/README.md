# Neo4j Init Scripts

These Cypher scripts run automatically when Neo4j starts with an **empty database**.
Docker mounts this folder to `/init` inside the container.

> **Neo4j does NOT automatically execute scripts on startup by default.**
> For Archim8, these scripts are provided as the canonical schema source of truth.
> Run them manually via the Neo4j Browser once the container is up:
>   1. Open http://localhost:7474
>   2. Paste each file in order and execute.

## Scripts (run in order)

| File | Purpose |
|------|---------|
| `01-constraints.cypher` | Unique constraints on all node labels |
| `02-index.cypher` | Performance indexes for common lookup patterns |
| `03-bootstrap.cypher` | Creates the `:Meta` node that records init timestamp |

## Idempotency

All statements use `IF NOT EXISTS` — safe to re-run against an existing database
without errors or duplicate data.

## When to re-run

- After wiping the Neo4j data volume (`ARCHIM8_NEO4J_DATA_DIR`)
- When setting up a new developer environment
- Never needed for normal iterative ingestion runs
