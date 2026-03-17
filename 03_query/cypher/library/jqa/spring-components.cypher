// view: spring-components
// scope: all types annotated with Spring stereotype annotations (@Service, @Repository, @Component, @Configuration)
//        and JPA annotations (@Entity)
// description: Spring component inventory per artifact/module.
//              Shows the Spring programming model usage: service classes,
//              repository interfaces, JPA entities, and configuration classes.
//
// Columns: artifact, layer, annotation, typeFqn, typeKind

MATCH (t:Type)-[:ANNOTATED_BY]->(av:Value:Annotation)-[:OF_TYPE]->(at:Type)
WHERE t.fqn STARTS WITH 'com.avanade'
  AND at.fqn IN [
    'org.springframework.stereotype.Service',
    'org.springframework.stereotype.Repository',
    'org.springframework.stereotype.Component',
    'org.springframework.context.annotation.Configuration',
    'jakarta.persistence.Entity'
  ]
MATCH (art:Artifact)-[:CONTAINS*1..3]->(t)
WHERE art.fileName IS NOT NULL
RETURN
  art.fileName   AS artifact,
  CASE
    WHEN art.fileName CONTAINS 'common-'          THEN 'common'
    WHEN art.fileName CONTAINS 'database-'        THEN 'database'
    WHEN art.fileName CONTAINS 'message-queue-'   THEN 'message-queue'
    WHEN art.fileName CONTAINS 'system-'          THEN 'system'
    WHEN art.fileName CONTAINS 'transaction-'     THEN 'system'
    WHEN art.fileName CONTAINS 'platform-'        THEN 'platform'
    WHEN art.fileName CONTAINS 'runtime-'         THEN 'runtime'
    WHEN art.fileName CONTAINS 'control-center-'  THEN 'control-center'
    ELSE 'unknown'
  END AS layer,
  at.fqn         AS annotation,
  t.fqn          AS typeFqn,
  CASE
    WHEN 'Interface' IN labels(t) THEN 'interface'
    WHEN 'Class'     IN labels(t) THEN 'class'
    WHEN 'Enum'      IN labels(t) THEN 'enum'
    ELSE 'type'
  END AS typeKind
ORDER BY layer, artifact, annotation, typeFqn;
