// =============================================================================
// Archim8 Neo4j Indexes
// Deployed to /init/02-index.cypher in the Neo4j container.
//
// Layer 1a (jdeps) — Archim8-managed indexes only.
// Layer 1b (jQAssistant) — jQA creates its own indexes at scan time.
//   See 02_store/neo4j/config/schema/jqa-labels.md for the full index model.
// =============================================================================

// ---------------------------------------------------------------------------
// Layer 1a — jdeps (Archim8-owned labels)
// ---------------------------------------------------------------------------

CREATE INDEX jar_name IF NOT EXISTS
FOR (n:Jar) ON (n.name);

// Supports group-based clustering queries and diagram generation
CREATE INDEX jar_group IF NOT EXISTS
FOR (n:Jar) ON (n.group);
