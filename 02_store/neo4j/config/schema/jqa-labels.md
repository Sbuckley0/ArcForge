# Archim8 Graph Model — Label & Relationship Strategy

This document is the authoritative reference for all Neo4j node labels and relationship types
used in Archim8. It defines ownership, naming conventions, and coexistence rules between
the two ingestion layers.

---

## Layer Ownership

| Layer | Owner | Label prefix | Ingest command |
|-------|-------|-------------|----------------|
| **Layer 1a — jdeps** | Archim8 | (no prefix — `:Jar`) | `make neo4j-ingest` |
| **Layer 1b — jQAssistant** | jQAssistant scanner | `:Java:*`, `:Maven:*` | `make jqa-scan` (Phase 1+) |

Both layers share the same Neo4j instance. They are coexistent and complementary.
The `layer` property on `:DEPENDS_ON` relationships disambiguates where needed.

---

## Layer 1a — jdeps Nodes (Archim8-owned)

### `:Jar`

Represents a JAR file detected on the Maven reactor classpath.

| Property | Type | Description |
|----------|------|-------------|
| `id` | String | Unique — JAR filename (e.g. `common-config.jar`) |
| `name` | String | JAR filename |
| `group` | String | First hyphen-segment of name (e.g. `common`) |
| `layer` | String | Always `'jdeps'` |

### `:Meta`

Archim8 metadata node (one per database).

| Property | Type | Description |
|----------|------|-------------|
| `id` | String | Always `'archim8'` |
| `version` | String | Schema version |
| `initializedAt` | DateTime | First init timestamp |

---

## Layer 1a — jdeps Relationships

### `(:Jar)-[:DEPENDS_ON {layer:'jdeps'}]->(:Jar)`

A bytecode-level JAR-to-JAR dependency extracted by jdeps.

| Property | Type | Description |
|----------|------|-------------|
| `layer` | String | Always `'jdeps'` — disambiguates from jQA-level DEPENDS_ON |

---

## Layer 1b — jQAssistant Node Labels

jQAssistant uses **compound labels** (label stacking). Each node carries multiple labels.
The first label is always the scanner domain; the second is the specific type.

### Maven Domain

| Labels | Represents | Key Properties |
|--------|-----------|----------------|
| `:Maven:Project` | Root Maven project (top-level pom.xml) | `name`, `groupId`, `artifactId`, `version` |
| `:Maven:Module` | Maven module within reactor | `name`, `artifactId`, `packaging` |
| `:Maven:Artifact` | Produced artifact (JAR/WAR) | `name`, `type`, `group` |
| `:Maven:Dependency` | Declared dependency entry | `scope`, `optional` |

### Java Domain

| Labels | Represents | Key Properties |
|--------|-----------|----------------|
| `:Java:Package` | Java package | `fqn` (fully-qualified name) |
| `:Java:Type` | Any Java type | `fqn`, `name`, `visibility`, `abstract` |
| `:Java:Type:Class` | Concrete class | + `final`, `static` |
| `:Java:Type:Interface` | Interface | (same as Type) |
| `:Java:Type:Enum` | Enum type | (same as Type) |
| `:Java:Type:Annotation` | Annotation type | (same as Type) |
| `:Java:Method` | Method or constructor | `name`, `signature`, `visibility`, `static` |
| `:Java:Field` | Class field | `name`, `signature`, `visibility`, `static` |
| `:Java:Value` | Literal/annotation value | `value` |

> **Querying tip:** Use `:Java:Type` to match all Java types regardless of subtype. Use `:Java:Type:Class` to narrow to concrete classes only.

---

## Layer 1b — jQAssistant Relationships

### Maven-level

| Relationship | From → To | Meaning |
|-------------|-----------|---------|
| `CONTAINS` | `Maven:Module` → `Maven:Module` | Parent/child module nesting |
| `CREATES` | `Maven:Module` → `Maven:Artifact` | Module produces this artifact |
| `DEPENDS_ON` | `Maven:Module` → `Maven:Artifact` | Declared Maven dependency |
| `CONTAINS` | `Maven:Module` → `Java:Package` | Module owns this package |

### Java-level

| Relationship | From → To | Meaning |
|-------------|-----------|---------|
| `CONTAINS` | `Java:Package` → `Java:Type` | Package contains type |
| `DECLARES` | `Java:Type` → `Java:Method` | Type declares method |
| `DECLARES` | `Java:Type` → `Java:Field` | Type declares field |
| `DEPENDS_ON` | `Java:Type` → `Java:Type` | Bytecode-level type dependency |
| `IMPLEMENTS` | `Java:Type` → `Java:Type` | Implements interface |
| `EXTENDS` | `Java:Type` → `Java:Type` | Extends class |
| `ANNOTATED_WITH` | `Java:Type/Method/Field` → `Java:Type:Annotation` | Annotation usage |
| `RETURNS` | `Java:Method` → `Java:Type` | Method return type |
| `HAS` | `Java:Method` → `Java:Value` | Parameter/annotation value |

---

## Disambiguation: `:DEPENDS_ON` Across Layers

Three distinct uses of `:DEPENDS_ON` exist at different granularities:

| Context | From → To | `layer` property | Granularity |
|---------|-----------|-----------------|-------------|
| jdeps | `:Jar` → `:Jar` | `'jdeps'` | JAR-level |
| jQA Maven | `:Maven:Module` → `:Maven:Artifact` | `'jqa-maven'` | Module-level (declared) |
| jQA Java | `:Java:Type` → `:Java:Type` | `'jqa-java'` | Type-level (bytecode) |

Use `layer` to filter by granularity in queries:
```cypher
// JAR-level only
MATCH (a:Jar)-[r:DEPENDS_ON {layer:'jdeps'}]->(b:Jar)

// Maven module declared deps only
MATCH (a:Maven)-[r:DEPENDS_ON {layer:'jqa-maven'}]->(b)

// Type-level bytecode deps only
MATCH (a:Java:Type)-[r:DEPENDS_ON {layer:'jqa-java'}]->(b:Java:Type)
```

---

## Cross-Layer Linking

jdeps `:Jar` nodes and jQA `:Maven:Artifact` nodes represent the same physical artifact.
They can be cross-joined by name:

```cypher
MATCH (j:Jar), (a:Maven:Artifact)
WHERE j.name = a.name
RETURN j, a
```

This enables queries like "show the Maven module ownership of the top-coupled JARs from jdeps".

---

## Archim8 `group` Property Convention

Both layers share the `group` property for clustering and diagram generation:

- **`:Jar`.`group`** — first hyphen-segment of JAR filename (set by jdeps ingest)
- **`:Maven:Module`.`group`** — first hyphen-segment of `artifactId` (set by Archim8 concept rule in Phase 3)

This ensures consistent grouping across both graph layers.
