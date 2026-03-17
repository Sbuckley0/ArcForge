// Find potential application entrypoints (main methods, Spring controllers, etc.)

MATCH (m:Method)
WHERE 
  // Standard Java main methods
  (m.name = 'main' AND m.isStatic = true AND m.visibility = 'public')
  OR
  // Spring Boot application main
  (m)-[:ANNOTATED_WITH]->(:Annotation {name: 'SpringBootApplication'})
  OR
  // REST endpoints
  (m)-[:ANNOTATED_WITH]->(:Annotation {name: 'RequestMapping'})
  OR
  (m)-[:ANNOTATED_WITH]->(:Annotation {name: 'GetMapping'})
  OR
  (m)-[:ANNOTATED_WITH]->(:Annotation {name: 'PostMapping'})

WITH m, 
  CASE 
    WHEN m.name = 'main' THEN 'Main Method'
    WHEN (m)-[:ANNOTATED_WITH]->(:Annotation {name: 'SpringBootApplication'}) THEN 'Spring Boot Application'
    ELSE 'REST Endpoint'
  END as entrypointType

MATCH (c:Class)-[:CONTAINS]->(m)

RETURN 
  entrypointType,
  c.fqn as className,
  m.name as methodName,
  m.signature as signature,
  m.filePath as file,
  m.lineNumber as line
ORDER BY entrypointType, className;
