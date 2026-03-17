# 05_deliver/input/03_query

Output from the `03_query` stage — analysis CSVs exported from Neo4j via APOC.

Produced by `make neo4j-export` — APOC exports from the `:Jar` graph populated by `make neo4j-ingest`.

## Files

| File | Columns | Description |
|------|---------|-------------|
| `jar-deps.csv` | fromJar, fromGroup, toJar, toGroup | Full directed edge list. Feedstock for PlantUML, Graphviz, Gephi, Excel. |
| `top-incoming.csv` | jar, group, incomingDeps | Top 20 most depended-on JARs (high fan-in = platform / shared libraries) |
| `top-outgoing.csv` | jar, group, outgoingDeps | Top 20 most coupled JARs (high fan-out = orchestration / entry points) |
| `cycles.csv` / `(empty)_cycles.csv` | jarA, jarB, cycleType | Direct mutual dependency cycles (architecture smell). Renamed to `(empty)_cycles.csv` when no cycles are found. |

`group` = first hyphen-segment of the JAR filename (e.g. `common-config.jar` → `common`).
Used for diagram clustering, PlantUML package boundaries, and Gephi partitioning.

All files except this README are gitignored.
