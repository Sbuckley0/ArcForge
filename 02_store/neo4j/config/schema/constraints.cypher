// =============================================================================
// Archim8 Neo4j Constraints — Reference / Schema Documentation
// (Canonical source — init/01-constraints.cypher is the deployed version)
//
// See jqa-labels.md for the full dual-layer model.
// =============================================================================

// ---------------------------------------------------------------------------
// Layer 1a — jdeps  (Archim8-owned)
// ---------------------------------------------------------------------------

CREATE CONSTRAINT jar_id IF NOT EXISTS
FOR (j:Jar) REQUIRE j.id IS UNIQUE;

CREATE CONSTRAINT meta_id IF NOT EXISTS
FOR (m:Meta) REQUIRE m.id IS UNIQUE;

// ---------------------------------------------------------------------------
// Layer 1b — jQAssistant  (jQA manages its own; listed here for reference)
// jQA creates these automatically during scan — do NOT run against a live
// Neo4j that already has jQA data or constraints will conflict.
// ---------------------------------------------------------------------------

// Maven domain
// CREATE CONSTRAINT maven_project_fqn IF NOT EXISTS
//   FOR (p:Maven:Project) REQUIRE p.fqn IS UNIQUE;

// CREATE CONSTRAINT maven_artifact_id IF NOT EXISTS
//   FOR (a:Maven:Artifact) REQUIRE a.id IS UNIQUE;

// Java domain
// CREATE CONSTRAINT java_type_fqn IF NOT EXISTS
//   FOR (t:Java:Type) REQUIRE t.fqn IS UNIQUE;

// CREATE CONSTRAINT java_package_fqn IF NOT EXISTS
//   FOR (p:Java:Package) REQUIRE p.fqn IS UNIQUE;
