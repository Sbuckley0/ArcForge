// =============================================================================
// neo4j-queries-jdeps.cypher
// Browser exploration queries for the jdeps jar→jar dependency graph.
//
// Node label: :Jar   Relationship: :DEPENDS_ON
//
// For APOC CSV exports (module-deps.csv, top-incoming.csv, etc.) see:
//   neo4j-export-jdeps.cypher
// =============================================================================


// ----------------------------------------------------------------------------
// Query 1 — Quick count: how many JARs and relationships were loaded?
// ----------------------------------------------------------------------------
MATCH (j:Jar)
RETURN count(j) AS totalJars;

MATCH ()-[r:DEPENDS_ON]->()
RETURN count(r) AS totalEdges;


// ----------------------------------------------------------------------------
// Query 2 — Top 20 most depended-on JARs (highest in-degree / platform JARs)
// ----------------------------------------------------------------------------
MATCH (dep:Jar)<-[:DEPENDS_ON]-(src:Jar)
RETURN dep.name          AS jar,
       count(src)         AS incomingDeps
ORDER BY incomingDeps DESC
LIMIT 20;


// ----------------------------------------------------------------------------
// Query 3 — Top 20 JARs with most outgoing dependencies (orchestration JARs)
// ----------------------------------------------------------------------------
MATCH (src:Jar)-[:DEPENDS_ON]->(dep:Jar)
RETURN src.name          AS jar,
       count(dep)         AS outgoingDeps
ORDER BY outgoingDeps DESC
LIMIT 20;


// ----------------------------------------------------------------------------
// Query 4 — Shortest dependency path between two JARs
// Replace names with real values from your graph.
// ----------------------------------------------------------------------------
MATCH path = shortestPath(
  (a:Jar {name: 'module-a.jar'})-[:DEPENDS_ON*1..10]->(z:Jar {name: 'module-z.jar'})
)
RETURN path;


// ----------------------------------------------------------------------------
// Query 5 — Leaf JARs (no outgoing dependencies)
// ----------------------------------------------------------------------------
MATCH (j:Jar)
WHERE NOT (j)-[:DEPENDS_ON]->()
RETURN j.name AS leafJar
ORDER BY leafJar;


// ----------------------------------------------------------------------------
// Query 6 — Blast radius: all JARs reachable from a given JAR (up to N hops)
// Replace 'your-jar.jar' with a real name.
// ----------------------------------------------------------------------------
MATCH path = (start:Jar {name: 'your-jar.jar'})-[:DEPENDS_ON*1..5]->(dep:Jar)
RETURN DISTINCT dep.name AS reachableJar
ORDER BY reachableJar;


// ----------------------------------------------------------------------------
// Query 7 — Focused subgraph: 2-hop neighbourhood around a JAR (visual)
// ----------------------------------------------------------------------------
MATCH path = (start:Jar {name: 'your-jar.jar'})-[:DEPENDS_ON*1..2]-(neighbour:Jar)
RETURN path;


// ----------------------------------------------------------------------------
// Query 8 — Mutual / direct cycles (architecture smell)
// ----------------------------------------------------------------------------
MATCH (a:Jar)-[:DEPENDS_ON]->(b:Jar)-[:DEPENDS_ON]->(a)
WHERE a.id < b.id
RETURN a.name AS jarA, b.name AS jarB
ORDER BY jarA;
