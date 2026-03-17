// =============================================================================
// Archim8 Neo4j Constraints
// Deployed to /init/01-constraints.cypher in the Neo4j container.
//
// Layer 1a (jdeps) — Archim8-managed: :Jar, :Meta
// Layer 1b (jQAssistant) — jQA manages its own constraints at scan time.
//   See 02_store/neo4j/config/schema/jqa-labels.md for the full label model.
// =============================================================================

// ---------------------------------------------------------------------------
// Layer 1a — jdeps (Archim8-owned labels)
// ---------------------------------------------------------------------------

CREATE CONSTRAINT jar_id IF NOT EXISTS
FOR (j:Jar) REQUIRE j.id IS UNIQUE;

CREATE CONSTRAINT meta_id IF NOT EXISTS
FOR (m:Meta) REQUIRE m.id IS UNIQUE;
