# Neo4j Schema

Graph schema definition for Archim8. Two layers coexist in the same Neo4j instance.
See **[jqa-labels.md](jqa-labels.md)** for the authoritative label and relationship reference.

---

## Layer 1a — jdeps (Archim8-owned)

Managed by Archim8 `init/` scripts and jdeps ingest pipeline.

| Label | Key Properties | Constraint |
|-------|---------------|------------|
| `:Jar` | `id`, `name`, `group`, `layer` | `jar_id` (unique) |
| `:Meta` | `id`, `version`, `initializedAt` | `meta_id` (unique) |

Relationship: `(:Jar)-[:DEPENDS_ON {layer:'jdeps'}]->(:Jar)`

## Layer 1b — jQAssistant (jQA-managed)

jQAssistant creates and manages its own schema during scan. Archim8 does not pre-create these.

| Labels | Represents |
|--------|------------|
| `:Maven:Project` | Root Maven project |
| `:Maven:Module` | Maven module |
| `:Maven:Artifact` | Produced artifact (JAR/WAR) |
| `:Java:Package` | Java package |
| `:Java:Type` | Any Java type (class/interface/enum) |
| `:Java:Method` | Method or constructor |
| `:Java:Field` | Class field |

Key relationships: `CONTAINS`, `DECLARES`, `DEPENDS_ON`, `IMPLEMENTS`, `EXTENDS`, `ANNOTATED_WITH`

See [jqa-labels.md](jqa-labels.md) for full property lists and relationship table.

---

## Files

| File | Purpose |
|------|---------|
| `jqa-labels.md` | **Authoritative** dual-layer label/relationship reference |
| `constraints.cypher` | Reference constraints (deployed copy in `../init/01-constraints.cypher`) |
| `indexes.cypher` | Reference indexes (deployed copy in `../init/02-index.cypher`) |
| `bootstrap.cypher` | Reference bootstrap (deployed copy in `../init/03-bootstrap.cypher`) |
| `migrations/` | Version-controlled schema changes |

## Migrations

| File | When to run | What it does |
|------|------------|-------------|
| `0001_layer-jdeps-tag.cypher` | Phase 1 kickoff (`make neo4j-migrate`) | Tags `:Jar`→`:Jar` DEPENDS_ON edges with `layer='jdeps'` (scoped to avoid memory pressure on 1.27M jQA edges) |
| `0002_phase2-jqa-scope-cleanup.cypher` | Phase 2 (`make neo4j-migrate`) | Removes 219 out-of-scope jQA artifacts (-sources, -tests, original- JARs) left from Phase 1 unfiltered scan |
| `0003_layer-jqa-tag.cypher` | Phase 2 (`make neo4j-migrate`) | Tags 1.27M jQA type-to-type DEPENDS_ON edges with `layer='jqa'` using batched transactions |

## Setup

Schema is applied automatically by `make neo4j-init` (runs `init/` scripts in order).
Do not run `schema/` reference files directly against a live database.


Run migrations in order.
