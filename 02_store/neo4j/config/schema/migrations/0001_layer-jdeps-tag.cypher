// Migration 0001 — Tag jdeps DEPENDS_ON edges with layer='jdeps'
//
// Run this ONCE after Phase 0 is deployed and before jQAssistant scan (Phase 1).
// Safe to re-run — only touches edges where layer IS NULL.
//
// SCOPE: Only matches DEPENDS_ON between :Jar nodes (the jdeps-created edges).
// This avoids processing the 1.27M jQA type-to-type DEPENDS_ON edges, which
// would exceed Neo4j Community Edition's transaction memory limit.
// jQA edges are tagged separately by migration 0003.
//
// Applied by: make neo4j-migrate (Phase 1 Makefile target)
// See: JQASSISTANT-INTEGRATION.md Phase 0

MATCH (:Jar)-[r:DEPENDS_ON]->(:Jar)
WHERE r.layer IS NULL
SET r.layer = 'jdeps'
RETURN count(r) AS edgesTagged;
