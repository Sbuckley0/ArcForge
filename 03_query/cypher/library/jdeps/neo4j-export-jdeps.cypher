// =============================================================================
// neo4j-export-jdeps.cypher
// APOC export pipeline — writes analysis CSVs to the Neo4j export directory.
//
// APOC writes to /import inside the container (= 05_deliver/input/01_ingest/).
// The Makefile neo4j-export target moves results to 05_deliver/input/03_query/.
//
// Output files:
//   jar-deps.csv          — full directed edge list with groups (versionable, reusable)
//   top-incoming.csv      — most depended-on JARs  (platform / high fan-in)
//   top-outgoing.csv      — most coupled JARs       (orchestration / high fan-out)
//   cycles.csv            — dependency cycles        (architecture smell report)
//
// Prerequisites:
//   1. APOC plugin installed (included in docker-compose.yml)
//   2. Neo4j running and jdeps data ingested (neo4j-ingest-jdeps.cypher)
//   3. Open Neo4j Browser: http://localhost:7474
//   4. Run each CALL block as a separate statement.
// =============================================================================


// ----------------------------------------------------------------------------
// Export 1 — Full edge list   →   jar-deps.csv
//
// Versionable record of all jar→jar dependencies.
// Includes fromGroup/toGroup for PlantUML package boundaries, Graphviz clusters,
// Gephi partitioning, and Excel pivot tables.
// ----------------------------------------------------------------------------
CALL apoc.export.csv.query(
  "MATCH (a:Jar)-[:DEPENDS_ON]->(b:Jar)
   RETURN a.name AS fromJar, a.group AS fromGroup, b.name AS toJar, b.group AS toGroup
   ORDER BY fromGroup, fromJar, toGroup, toJar",
  "jar-deps.csv",
  {}
) YIELD file, rows, time
RETURN file, rows, time;


// ----------------------------------------------------------------------------
// Export 2 — Top 20 most depended-on JARs   →   top-incoming.csv
//
// High fan-in = platform / shared libraries.
// "What are the core jars everything else relies on?"
// ----------------------------------------------------------------------------
CALL apoc.export.csv.query(
  "MATCH (j:Jar)<-[:DEPENDS_ON]-(src:Jar)
   RETURN j.name AS jar, j.group AS group, count(src) AS incomingDeps
   ORDER BY incomingDeps DESC
   LIMIT 20",
  "top-incoming.csv",
  {}
) YIELD file, rows, time
RETURN file, rows, time;


// ----------------------------------------------------------------------------
// Export 3 — Top 20 most coupled JARs   →   top-outgoing.csv
//
// High fan-out = orchestration / entry-point JARs.
// "What jars depend on the most other jars?"
// ----------------------------------------------------------------------------
CALL apoc.export.csv.query(
  "MATCH (j:Jar)-[:DEPENDS_ON]->(dep:Jar)
   RETURN j.name AS jar, j.group AS group, count(dep) AS outgoingDeps
   ORDER BY outgoingDeps DESC
   LIMIT 20",
  "top-outgoing.csv",
  {}
) YIELD file, rows, time
RETURN file, rows, time;


// ----------------------------------------------------------------------------
// Export 4 — Dependency cycles   →   cycles.csv
//
// Architecture smell: A depends on B and B (transitively) depends on A.
// Direct mutual pairs (depth 1):
// ----------------------------------------------------------------------------
CALL apoc.export.csv.query(
  "MATCH (a:Jar)-[:DEPENDS_ON]->(b:Jar)-[:DEPENDS_ON]->(a)
   WHERE a.id < b.id
   RETURN a.name AS jarA, b.name AS jarB, 'direct-mutual' AS cycleType
   ORDER BY jarA",
  "cycles.csv",
  {}
) YIELD file, rows, time
RETURN file, rows, time;

// Note: for deeper cycle detection (up to N hops), run this in Browser
// (not suitable for APOC export on large graphs without LIMIT):
//
// MATCH path = (a:Jar)-[:DEPENDS_ON*2..6]->(a)
// RETURN [n IN nodes(path) | n.name] AS cycle
// LIMIT 50;
