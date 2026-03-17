// view: module-deps
// scope: all Jar-to-Jar dependencies (jdeps layer)
// description: Module dependency graph grouped by architecture layer.
//              Each row is a directed edge from one module to another.
//              Includes the layer label for both source and target.
//
// Columns: fromModule, fromLayer, toModule, toLayer, fromGroup, toGroup

MATCH (j1:Jar)-[r:DEPENDS_ON {layer:'jdeps'}]->(j2:Jar)
WHERE NOT j1.name STARTS WITH 'java.'
  AND NOT j1.name STARTS WITH 'jdk.'
  AND NOT j2.name STARTS WITH 'java.'
  AND NOT j2.name STARTS WITH 'jdk.'
OPTIONAL MATCH (j1)-[:IS_ARTIFACT]->(ma1:Maven:Artifact)
OPTIONAL MATCH (j2)-[:IS_ARTIFACT]->(ma2:Maven:Artifact)
RETURN
  j1.name        AS fromModule,
  j1.group       AS fromGroup,
  CASE
    WHEN j1.name STARTS WITH 'common-'          THEN 'common'
    WHEN j1.name STARTS WITH 'database-'        THEN 'database'
    WHEN j1.name STARTS WITH 'message-queue-'   THEN 'message-queue'
    WHEN j1.name STARTS WITH 'system-'          THEN 'system'
    WHEN j1.name STARTS WITH 'transaction-'     THEN 'system'
    WHEN j1.name STARTS WITH 'platform-'        THEN 'platform'
    WHEN j1.name STARTS WITH 'runtime-'         THEN 'runtime'
    WHEN j1.name STARTS WITH 'control-center-'  THEN 'control-center'
    ELSE 'unknown'
  END AS fromLayer,
  j2.name        AS toModule,
  j2.group       AS toGroup,
  CASE
    WHEN j2.name STARTS WITH 'common-'          THEN 'common'
    WHEN j2.name STARTS WITH 'database-'        THEN 'database'
    WHEN j2.name STARTS WITH 'message-queue-'   THEN 'message-queue'
    WHEN j2.name STARTS WITH 'system-'          THEN 'system'
    WHEN j2.name STARTS WITH 'transaction-'     THEN 'system'
    WHEN j2.name STARTS WITH 'platform-'        THEN 'platform'
    WHEN j2.name STARTS WITH 'runtime-'         THEN 'runtime'
    WHEN j2.name STARTS WITH 'control-center-'  THEN 'control-center'
    ELSE 'unknown'
  END AS toLayer
ORDER BY fromLayer, fromModule, toLayer, toModule;
