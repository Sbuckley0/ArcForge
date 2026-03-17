# 05_deliver/input/01_ingest

Output from the `01_ingest` pipeline stage. This folder doubles as the
**Neo4j import directory** — files here are accessible inside the container as `file:///`.

Set `ARCHIM8_NEO4J_IMPORT_DIR` (in `00_orchestrate/config/archim8.local.env`) to the
absolute path of this folder so that both the ingest scripts and Neo4j
resolve to the same location.

## Files produced by `make jdeps`

| File | Produced by | Description |
|------|-------------|-------------|
| `jdeps-output.txt` | `01_ingest/jdep/scripts/jdeps-run.ps1` | Raw jdeps text output |
| `jdeps-jar-edges.csv` | `01_ingest/jdep/scripts/jdeps-extract-edges.ps1` | Jar→jar dependency edges (no headers) |

## Cypher ingestion

After running the pipeline, ingest the CSV into Neo4j:

```
03_query/cypher/library/jdeps/neo4j-ingest-jdeps.cypher
```

All files except this README are gitignored.
