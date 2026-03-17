# Neo4j — Archim8 Graph Database

Structural truth store for code nodes and relationships.
Run via Docker Compose — no changes to the target application required.

---

## First-time setup

```powershell
# 1. Create your local .env from the template (one-time per developer)
Copy-Item docker/.env.template docker/.env

# 2. Edit .env — only NEO4J_AUTH is required; data/logs default to ./data and ./logs
#    relative to docker-compose.yml (created automatically on first run).
notepad docker/.env

# 3. Start the container
docker compose -f docker/docker-compose.yml up -d

# 4. Open the browser
start http://localhost:7474
```

---

## Daily usage

```powershell
docker compose up -d        # start
docker compose down         # stop (data persists)
docker compose logs -f      # tail logs
docker compose ps           # check health
```

---

## Access

| | |
|-|-|
| **Browser UI** | http://localhost:7474 |
| **Bolt** | bolt://localhost:7687 |
| **Default login** | neo4j / password |

---

## Schema initialisation (first time or after a data wipe)

Paste each file into Neo4j Browser **in order** — all statements are idempotent (`IF NOT EXISTS`):

| Order | File | Purpose |
|-------|------|---------|
| 1 | [`init/01-constraints.cypher`](init/01-constraints.cypher) | Unique constraints on all node labels |
| 2 | [`init/02-index.cypher`](init/02-index.cypher) | Performance indexes |
| 3 | [`init/03-bootstrap.cypher`](init/03-bootstrap.cypher) | `:Meta` node with init timestamp |

See [`init/README.md`](init/README.md) for details.

---

## Graph model — dual-layer coexistence

Two ingestion layers share the same Neo4j instance and own distinct node labels.
Each layer tags its edges with a `layer` property for clean cross-layer queries.

| Layer | Labels | DEPENDS_ON tag | Populated by |
|-------|--------|----------------|--------------|
| **Layer 1a — jdeps** | `:Jar` | `layer:'jdeps'` | `make jdeps-pipeline` |
| **Layer 1b — jQAssistant** | `:Maven:Module`, `:Java:Type`, `:Java:Package`, … | `layer:'jqa'` | `make jqa-pipeline` |

Layers are linkable via shared artifact name properties for cross-layer queries.

### Schema migrations

Schema changes (including edge tagging) are version-controlled migration files:

| Migration | What it does |
|-----------|-------------|
| `0001_layer-jdeps-tag.cypher` | Tags `:Jar`→`:Jar` DEPENDS_ON edges with `layer='jdeps'` |
| `0002_phase2-jqa-scope-cleanup.cypher` | Removes 219 out-of-scope jQA artifacts (-sources, -tests, original-) |
| `0003_layer-jqa-tag.cypher` | Tags 1.27M jQA DEPENDS_ON edges with `layer='jqa'` |

Run all migrations: `make neo4j-migrate`  
See [`config/schema/README.md`](config/schema/README.md) for full migration table and details.

---

## jdeps ingestion — jar dependency graph

This is the primary ingestion workflow. It builds a jar→jar dependency graph
from a Maven project using `jdeps` — **zero changes to the target app**.

### Run the pipeline (or use make)

```powershell
# From repo root — full pipeline (build → jdeps → CSV)
make jdeps

# Skip Maven build (use existing target/ artifacts)
make jdeps-skip

# Skip build + filter JDK edges
make jdeps-filter
```

Output lands in `05_deliver/input/01_ingest/` (configured via `ARCHIM8_NEO4J_IMPORT_DIR`).

The pipeline runs these steps internally:

| Step | Script | Output |
|------|--------|--------|
| Load config | `00_orchestrate/scripts/load-env.ps1` | env vars in session |
| Build + jdeps | `01_ingest/jdep/scripts/jdeps-run.ps1` | `05_deliver/input/01_ingest/jdeps-output.txt` |
| Extract edges | `01_ingest/jdep/scripts/jdeps-extract-edges.ps1` | `05_deliver/input/01_ingest/jdeps-jar-edges.csv` |

### Ingest into Neo4j (Neo4j Browser)

After the pipeline completes, open http://localhost:7474 and paste
[`../../03_query/cypher/library/jdeps/neo4j-ingest-jdeps.cypher`](../../03_query/cypher/library/jdeps/neo4j-ingest-jdeps.cypher).

Run the two statements in order:

**Statement 1 — constraint (once):**
```cypher
CREATE CONSTRAINT jar_id IF NOT EXISTS
FOR (j:Jar) REQUIRE j.id IS UNIQUE;
```

**Statement 2 — load edges:**
```cypher
LOAD CSV FROM 'file:///jdeps-jar-edges.csv' AS row
WITH row[0] AS src, row[1] AS tgt
WHERE src IS NOT NULL AND tgt IS NOT NULL
  AND src <> '' AND tgt <> ''
MERGE (s:Jar {id: src})
  ON CREATE SET s.name = src, s.type = 'jar', s.source = 'jdeps'
MERGE (t:Jar {id: tgt})
  ON CREATE SET t.name = tgt, t.type = 'jar', t.source = 'jdeps'
MERGE (s)-[:DEPENDS_ON]->(t);
```

### Explore the graph (Neo4j Browser)

Full query set: [`../../03_query/cypher/library/jdeps/neo4j-export-sample.cypher`](../../03_query/cypher/library/jdeps/neo4j-export-sample.cypher)

Quick starters:

```cypher
// How many JARs and edges?
MATCH (j:Jar) RETURN count(j) AS jars;
MATCH ()-[r:DEPENDS_ON]->() RETURN count(r) AS edges;
```

```cypher
// Top 20 most depended-on JARs (platform / shared libs)
MATCH (dep:Jar)<-[:DEPENDS_ON]-(src)
RETURN dep.name AS jar, count(src) AS incomingDeps
ORDER BY incomingDeps DESC LIMIT 20;
```

```cypher
// Top 20 most coupled JARs (most outgoing deps)
MATCH (src:Module)-[:DEPENDS_ON]->(dep)
RETURN src.name AS jar, count(dep) AS outgoingDeps
ORDER BY outgoingDeps DESC LIMIT 20;
```

```cypher
// Shortest dependency path between two JARs
MATCH path = shortestPath(
  (a:Module {name: 'module-a.jar'})-[:DEPENDS_ON*1..10]->(z:Module {name: 'module-z.jar'})
)
RETURN path;
```

```cypher
// Leaf JARs (not depending on anything)
MATCH (m:Module)
WHERE NOT (m)-[:DEPENDS_ON]->()
RETURN m.name AS leafJar ORDER BY leafJar;
```

---

## Folder structure

```
02_store/neo4j/
├── README.md
├── config/
│   └── schema/              Cypher schema definitions
├── docker/
│   ├── docker-compose.yml   main compose file
│   ├── .env.template        tracked — copy to .env and fill in auth
│   ├── .env                 NOT tracked — your real auth / path overrides
│   ├── data/                NOT tracked — Neo4j database files (Docker volume)
│   ├── logs/                NOT tracked — Neo4j runtime logs (Docker volume)
│   ├── import/              files here are accessible as file:/// in Cypher
│   │   └── jdeps-jar-edges.csv  (generated — gitignored)
│   └── export/              APOC export destination
└── scripts/
```
