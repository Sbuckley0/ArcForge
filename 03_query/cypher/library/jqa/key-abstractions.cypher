// view: key-abstractions
// scope: application-owned interfaces and abstract classes ranked by implementation/usage count
// description: Key architectural abstractions — the interfaces and abstract classes
//              that most of the codebase is built around. High implementation counts
//              indicate framework extension points or core contracts.
//
// Part 1 — interfaces most implemented (extension points)
MATCH (impl:Type)-[:IMPLEMENTS]->(iface:Type)
WHERE impl.fqn STARTS WITH 'com.avanade'
  AND iface.fqn STARTS WITH 'com.avanade'
  AND 'Interface' IN labels(iface)
WITH iface, count(impl) AS implCount
ORDER BY implCount DESC
LIMIT 30
MATCH (art:Artifact)-[:CONTAINS*1..3]->(iface)
WHERE art.fileName IS NOT NULL
RETURN
  'most-implemented-interface' AS kind,
  iface.fqn                   AS typeFqn,
  art.fileName                AS artifact,
  CASE
    WHEN art.fileName CONTAINS 'common-'          THEN 'common'
    WHEN art.fileName CONTAINS 'database-'        THEN 'database'
    WHEN art.fileName CONTAINS 'message-queue-'   THEN 'message-queue'
    WHEN art.fileName CONTAINS 'system-'          THEN 'system'
    WHEN art.fileName CONTAINS 'platform-'        THEN 'platform'
    WHEN art.fileName CONTAINS 'runtime-'         THEN 'runtime'
    WHEN art.fileName CONTAINS 'control-center-'  THEN 'control-center'
    ELSE 'unknown'
  END AS layer,
  implCount                   AS score
ORDER BY score DESC;
