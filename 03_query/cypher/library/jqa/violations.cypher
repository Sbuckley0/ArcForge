// view: violations
// scope: all jdeps DEPENDS_ON edges that cross layer boundaries upward
// description: Architecture rule violations — modules depending on higher layers.
//              Layer ordering (low to high): common < database/message-queue < system < platform < runtime < control-center
//              Upward dependencies (low→high) are violations.
//              This is the deterministic constraint view from the jdeps graph.
//
// Columns: fromModule, fromLayer, fromLayerRank, toModule, toLayer, toLayerRank, violationType

MATCH (j1:Jar)-[r:DEPENDS_ON {layer:'jdeps'}]->(j2:Jar)
WHERE NOT j1.name STARTS WITH 'java.'
  AND NOT j1.name STARTS WITH 'jdk.'
  AND NOT j2.name STARTS WITH 'java.'
  AND NOT j2.name STARTS WITH 'jdk.'
WITH j1, j2,
  CASE
    WHEN j1.name STARTS WITH 'common-'          THEN 1
    WHEN j1.name STARTS WITH 'database-'        THEN 2
    WHEN j1.name STARTS WITH 'message-queue-'   THEN 2
    WHEN j1.name STARTS WITH 'system-'          THEN 3
    WHEN j1.name STARTS WITH 'transaction-'     THEN 3
    WHEN j1.name STARTS WITH 'platform-'        THEN 4
    WHEN j1.name STARTS WITH 'runtime-'         THEN 5
    WHEN j1.name STARTS WITH 'control-center-'  THEN 6
    ELSE 0
  END AS fromRank,
  CASE
    WHEN j2.name STARTS WITH 'common-'          THEN 1
    WHEN j2.name STARTS WITH 'database-'        THEN 2
    WHEN j2.name STARTS WITH 'message-queue-'   THEN 2
    WHEN j2.name STARTS WITH 'system-'          THEN 3
    WHEN j2.name STARTS WITH 'transaction-'     THEN 3
    WHEN j2.name STARTS WITH 'platform-'        THEN 4
    WHEN j2.name STARTS WITH 'runtime-'         THEN 5
    WHEN j2.name STARTS WITH 'control-center-'  THEN 6
    ELSE 0
  END AS toRank
WHERE fromRank > 0 AND toRank > 0 AND fromRank < toRank
RETURN
  j1.name   AS fromModule,
  CASE fromRank
    WHEN 1 THEN 'common'
    WHEN 2 THEN CASE WHEN j1.name STARTS WITH 'database-' THEN 'database' ELSE 'message-queue' END
    WHEN 3 THEN 'system'
    WHEN 4 THEN 'platform'
    WHEN 5 THEN 'runtime'
    WHEN 6 THEN 'control-center'
  END AS fromLayer,
  fromRank  AS fromLayerRank,
  j2.name   AS toModule,
  CASE toRank
    WHEN 1 THEN 'common'
    WHEN 2 THEN CASE WHEN j2.name STARTS WITH 'database-' THEN 'database' ELSE 'message-queue' END
    WHEN 3 THEN 'system'
    WHEN 4 THEN 'platform'
    WHEN 5 THEN 'runtime'
    WHEN 6 THEN 'control-center'
  END AS toLayer,
  toRank    AS toLayerRank,
  'upward-coupling' AS violationType
ORDER BY fromRank, fromModule, toRank, toModule;
