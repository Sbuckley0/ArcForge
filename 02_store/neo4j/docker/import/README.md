# neo4j/import (default fallback)

This folder is the **default** Neo4j import directory when `ARCHIM8_NEO4J_IMPORT_DIR`
is not set in `archim8.local.env`. It is mounted as `/import` inside the container.

**Recommended setup:** point `ARCHIM8_NEO4J_IMPORT_DIR` to
`05_deliver/input/01_ingest/` (absolute path) so the pipeline output and
Neo4j's import folder are the same physical location.

Files placed here (or at the configured import dir) are accessible in Cypher:

```cypher
LOAD CSV FROM 'file:///filename.csv' AS row
```

## Files written by the jdeps pipeline (`make jdeps`)

| File | Produced by | Description |
|------|------------|-------------|
| `jdeps-output.txt` | `01_ingest/jdep/scripts/jdeps-run.ps1` | Raw jdeps text output |
| `jdeps-jar-edges.csv` | `01_ingest/jdep/scripts/jdeps-extract-edges.ps1` | Jar→jar dependency edges (no headers) |

All files in this folder except this README are gitignored.
Drop CSVs here freely — they will not be committed.
