// =============================================================================
// neo4j-ingest-jdeps.cypher
// Browser-friendly ingestion query for jar→jar dependency edges.
//
// Prerequisites:
//   1. jdeps-jar-edges.csv is in:  05_deliver/input/01_ingest/
//      (= ARCHIM8_NEO4J_IMPORT_DIR, mounted as /import in the container)
//   2. Neo4j is running:  make docker-up
//   3. Open Neo4j Browser: http://localhost:7474
//   4. Paste this entire file and run each statement.
//
// CSV format (NO HEADERS, two columns):
//   source_jar_filename,target_jar_filename
//
// Idempotent: uses MERGE — safe to re-run.
// Node label :Jar (not :Module) to avoid label collision with jqAssistant.
// Does NOT use CALL IN TRANSACTIONS or USING PERIODIC COMMIT (browser-safe).
// =============================================================================

// ----------------------------------------------------------------------------
// Step 1 — Ensure constraint exists (idempotent)
// ----------------------------------------------------------------------------
CREATE CONSTRAINT jar_id IF NOT EXISTS
FOR (j:Jar) REQUIRE j.id IS UNIQUE;

// ----------------------------------------------------------------------------
// Step 2 — Ingest edges
// Run this in a separate browser statement after Step 1 completes.
// ----------------------------------------------------------------------------
// group = first hyphen-segment of the bare filename (strips 'original-' prefix and '.jar').
// e.g. common-config.jar -> 'common', platform-pekko-cluster.jar -> 'platform'
// Used later for diagram grouping and PlantUML package boundaries.
LOAD CSV FROM 'file:///jdeps-jar-edges.csv' AS row
WITH row[0] AS src, row[1] AS tgt
WHERE src IS NOT NULL AND tgt IS NOT NULL
  AND src <> '' AND tgt <> ''
WITH src, tgt,
     split(replace(replace(src, 'original-', ''), '.jar', ''), '-')[0] AS srcGroup,
     split(replace(replace(tgt, 'original-', ''), '.jar', ''), '-')[0] AS tgtGroup
MERGE (s:Jar {id: src})
  ON CREATE SET s.name = src, s.group = srcGroup, s.type = 'jar', s.source = 'jdeps'
  ON MATCH  SET s.group = srcGroup
MERGE (t:Jar {id: tgt})
  ON CREATE SET t.name = tgt, t.group = tgtGroup, t.type = 'jar', t.source = 'jdeps'
  ON MATCH  SET t.group = tgtGroup
MERGE (s)-[:DEPENDS_ON]->(t);
