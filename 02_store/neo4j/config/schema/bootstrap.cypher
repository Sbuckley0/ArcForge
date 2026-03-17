// Archim8 Neo4j Bootstrap — Reference
// (init/03-bootstrap.cypher is the deployed version; this is the schema reference)
//
// Run against a fresh database to set up the Archim8 schema.
// jQAssistant manages its own schema during scan — do not pre-create jQA labels.

MERGE (meta:Meta {id: 'archim8'})
SET meta.version = '0.2.0',
    meta.created = datetime(),
    meta.lastUpdated = datetime(),
    meta.schemaDoc = 'See schema/jqa-labels.md for the full dual-layer model';

});

// Verify setup
MATCH (n)
RETURN labels(n) as Label, count(*) as Count
ORDER BY Count DESC;
