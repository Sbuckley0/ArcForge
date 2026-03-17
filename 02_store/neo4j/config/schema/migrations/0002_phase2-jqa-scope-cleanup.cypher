// Migration 0002 — Remove out-of-scope jQA artifacts from Phase 1 scan
//
// Phase 1 ran jQA with no file filters, which scanned:
//   - *-sources.jar   (86 JARs)  — source-attachment archives, no bytecode value
//   - *-tests.jar    (132 JARs)  — test-class archives, pollutes dependency graph
//   - original-*.jar   (1 JAR)   — shaded/fat-JAR intermediate, misleading deps
//
// Phase 2 adds file.exclude filters to jqassistant.yml so future scans skip these.
// This migration retroactively removes the already-imported artifact nodes.
//
// After this migration :Java:Artifact count drops ~309 → ~90, matching jdeps.
// Note: Java:Type nodes that were exclusively in test/sources JARs are orphaned
// (no longer reachable via CONTAINS from any artifact). This is acceptable
// technical debt — Phase 3 queries should always start from :Java:Artifact.
//
// Safe to re-run — MATCH returns 0 rows if artifacts are already removed.
// Applied by: make neo4j-migrate
// See: JQASSISTANT-INTEGRATION.md Phase 2

MATCH (a:Java:Artifact)
WHERE a.fileName ENDS WITH '-sources.jar'
   OR a.fileName ENDS WITH '-tests.jar'
   OR a.fileName CONTAINS '/original-'

WITH count(a) AS removedCount, collect(a) AS toDelete

CALL {
  WITH toDelete
  UNWIND toDelete AS a
  DETACH DELETE a
} IN TRANSACTIONS OF 100 ROWS

RETURN removedCount AS RemovedArtifacts;
