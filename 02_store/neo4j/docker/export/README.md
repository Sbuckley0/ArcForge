# neo4j/export

This folder is mounted as `/export` inside the `archim8-neo4j` container.

Files written here from Cypher `EXPORT` queries or `apoc.export.*` calls are
accessible on the host at this path.

## Usage

Example Cypher to export query results (paste into Neo4j Browser):

```cypher
// Export top dependency hubs to CSV — requires APOC
CALL apoc.export.csv.query(
  "MATCH (m:Module)-[:DEPENDS_ON]->(dep) RETURN m.name AS module, count(dep) AS deps ORDER BY deps DESC LIMIT 50",
  "top-hubs.csv",
  {}
)
```

Then find the file at `archim8/02_docker/neo4j/export/top-hubs.csv`.

## Gitignore note

All files in this folder **except this README** are gitignored.
