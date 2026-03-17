// view: cobol-subsystem
// scope: runtime-cobol-* modules and their dependencies
// description: COBOL emulation subsystem — all modules in the runtime-cobol-* group,
//              their internal structure (packages, type counts), and their external
//              dependencies into other architecture layers.
//
// Part 1 — COBOL module type inventory
MATCH (art:Artifact)
WHERE art.fileName CONTAINS 'runtime-cobol'
OPTIONAL MATCH (art)-[:CONTAINS*1..3]->(t:Type)
WHERE t.fqn STARTS WITH 'com.avanade'
RETURN
  'cobol-module'  AS kind,
  art.fileName    AS artifact,
  count(t)        AS typeCount
ORDER BY typeCount DESC;
