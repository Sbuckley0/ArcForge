// view: pekko-http-api
// scope: modules that depend on platform-api-rest.jar or common-pekko-http.jar (HTTP/REST surface)
// description: REST/HTTP surface via Pekko HTTP. 
//              The app exposes HTTP routes via Pekko HTTP (not Spring MVC).
//              This query identifies which modules participate in the HTTP layer
//              via jdeps dependency edges.
//
// Columns: module, layer, httpDependency

MATCH (j1:Jar)-[:DEPENDS_ON {layer:'jdeps'}]->(j2:Jar)
WHERE j2.name IN ['platform-api-rest.jar', 'common-pekko-http.jar', 'platform-pekko-grpc-client.jar', 'platform-pekko-grpc-server.jar']
  AND NOT j1.name STARTS WITH 'java.'
RETURN
  j1.name  AS module,
  j1.group AS group,
  CASE
    WHEN j1.name STARTS WITH 'common-'          THEN 'common'
    WHEN j1.name STARTS WITH 'platform-'        THEN 'platform'
    WHEN j1.name STARTS WITH 'runtime-'         THEN 'runtime'
    WHEN j1.name STARTS WITH 'control-center-'  THEN 'control-center'
    ELSE 'other'
  END AS layer,
  j2.name  AS httpDependency
ORDER BY layer, module;
