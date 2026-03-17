// Find all top-level modules (packages) in the codebase

MATCH (p:Package)
WHERE NOT (p)<-[:CONTAINS]-(:Package)
WITH p
OPTIONAL MATCH (p)-[:CONTAINS*]->(c:Class)
WITH p, count(DISTINCT c) as classCount
OPTIONAL MATCH (p)-[:CONTAINS*]->(m:Method)
WITH p, classCount, count(DISTINCT m) as methodCount
RETURN 
  p.fqn as module,
  p.name as name,
  classCount as classes,
  methodCount as methods
ORDER BY classCount DESC;
