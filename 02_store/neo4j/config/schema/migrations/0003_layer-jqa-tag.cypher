// Migration 0003 — Tag jQA DEPENDS_ON edges with layer='jqa'
//
// Phase 1 (jQA scan) produced ~1.27M DEPENDS_ON edges between :Java:Type nodes.
// These represent bytecode-level class-to-class dependencies resolved by jQA.
// Migration 0001 only tags :Jar→:Jar edges (jdeps layer); this migration
// handles the remaining untagged edges from jQA.
//
// Uses CALL {} IN TRANSACTIONS to process in 10,000-row batches,
// preventing Neo4j Community Edition memory limit exhaustion.
//
// Safe to re-run — only touches edges where layer IS NULL.
// Applied by: make neo4j-migrate
// See: JQASSISTANT-INTEGRATION.md Phase 2

MATCH ()-[r:DEPENDS_ON]->()
WHERE r.layer IS NULL
CALL {
  WITH r
  SET r.layer = 'jqa'
} IN TRANSACTIONS OF 10000 ROWS

RETURN count(*) AS edgesTagged;
