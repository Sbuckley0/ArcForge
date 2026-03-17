// =============================================================================
// Archim8 Neo4j Indexes — Reference / Schema Documentation
// (Canonical source — init/02-index.cypher is the deployed version)
//
// See jqa-labels.md for the full dual-layer model.
// =============================================================================

// ---------------------------------------------------------------------------
// Layer 1a — jdeps  (Archim8-owned, deployed via init/)
// ---------------------------------------------------------------------------

CREATE INDEX jar_name IF NOT EXISTS
FOR (n:Jar) ON (n.name);

CREATE INDEX jar_group IF NOT EXISTS
FOR (n:Jar) ON (n.group);

// ---------------------------------------------------------------------------
// Layer 1b — jQAssistant  (jQA creates these at scan time — reference only)
// ---------------------------------------------------------------------------

// Maven domain
// CREATE INDEX maven_module_artifactid IF NOT EXISTS
//   FOR (m:Maven:Module) ON (m.artifactId);

// Java domain
// CREATE TEXT INDEX java_type_name IF NOT EXISTS
//   FOR (t:Java:Type) ON (t.name);

// CREATE TEXT INDEX java_package_fqn IF NOT EXISTS
//   FOR (p:Java:Package) ON (p.fqn);

// CREATE RANGE INDEX java_type_visibility IF NOT EXISTS
//   FOR (t:Java:Type) ON (t.visibility);

// CREATE RANGE INDEX java_method_static IF NOT EXISTS
//   FOR (m:Java:Method) ON (m.static);

ON EACH [n.name, n.javadoc, n.source];

// Relationship indexes
CREATE INDEX calls_relationship IF NOT EXISTS
FOR ()-[r:CALLS]-() ON (r.lineNumber);

CREATE INDEX depends_on_relationship IF NOT EXISTS
FOR ()-[r:DEPENDS_ON]-() ON (r.type);
