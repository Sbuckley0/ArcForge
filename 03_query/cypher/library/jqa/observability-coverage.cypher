// view: observability-coverage
// scope: all Jar nodes; cross-referenced with types that use Micrometer/OpenTelemetry
// description: Observability coverage per module.
//              View 1: modules whose types directly reference Micrometer or OpenTelemetry classes (via jQA DEPENDS_ON).
//              View 2: all modules without any observability dependency (gap list).
//              Uses jQA type-level DEPENDS_ON edges (layer:'jqa').
//
// Part 1 — modules WITH observability type-level usage
MATCH (t1:Type)-[r:DEPENDS_ON {layer:'jqa'}]->(t2:Type)
WHERE t1.fqn STARTS WITH 'com.avanade'
  AND (
    t2.fqn STARTS WITH 'io.micrometer' OR
    t2.fqn STARTS WITH 'io.opentelemetry' OR
    t2.fqn STARTS WITH 'org.slf4j' OR
    t2.fqn STARTS WITH 'ch.qos.logback' OR
    t2.fqn STARTS WITH 'org.apache.logging'
  )
MATCH (art:Artifact)-[:CONTAINS*1..3]->(t1)
WHERE art.fileName IS NOT NULL
RETURN DISTINCT
  'covered'       AS status,
  art.fileName    AS artifact,
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
  t2.fqn          AS observabilityFramework
ORDER BY layer, artifact;
