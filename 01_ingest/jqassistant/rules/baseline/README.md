# jQAssistant Baseline Rules

This directory contains Cypher-based rules for architecture validation and analysis.

## Rule Types

jQAssistant supports three types of rules:

1. **Concepts** - Extract derived information
2. **Constraints** - Enforce architecture rules (violations fail build if configured)
3. **Groups** - Organize rules into execution sets

## Example: Layering Constraint

```xml
<!-- concepts/layers.xml -->
<jqa:jqassistant-rules xmlns:jqa="http://www.buschmais.com/jqassistant/core/rule/schema/v1.8">
  
  <concept id="archim8:Package:Layer">
    <description>Labels packages by architectural layer</description>
    <cypher><![CDATA[
      MATCH (p:Package)
      WHERE p.fqn =~ '.*\\.controller.*'
      SET p:Controller
      RETURN p
      UNION
      MATCH (p:Package)
      WHERE p.fqn =~ '.*\\.service.*'
      SET p:Service
      RETURN p
      UNION
      MATCH (p:Package)
      WHERE p.fqn =~ '.*\\.repository.*'
      SET p:Repository
      RETURN p
    ]]></cypher>
  </concept>
  
  <constraint id="archim8:LayerDependency">
    <requiresConcept refId="archim8:Package:Layer"/>
    <description>Controllers must not directly depend on repositories</description>
    <cypher><![CDATA[
      MATCH (controller:Package:Controller)-[:DEPENDS_ON]->(repo:Package:Repository)
      RETURN controller.fqn as Violator, repo.fqn as IllegalDependency
    ]]></cypher>
  </constraint>
  
</jqa:jqassistant-rules>
```

## Example: Circular Dependencies

```xml
<!-- constraints/cycles.xml -->
<jqa:jqassistant-rules xmlns:jqa="http://www.buschmais.com/jqassistant/core/rule/schema/v1.8">
  
  <constraint id="archim8:NoCyclicPackageDependencies">
    <description>Packages must not have circular dependencies</description>
    <cypher><![CDATA[
      MATCH (p1:Package)-[:DEPENDS_ON]->(p2:Package),
            (p2)-[:DEPENDS_ON]->(p1)
      WHERE p1 <> p2
      RETURN p1.fqn as Package1, p2.fqn as Package2
    ]]></cypher>
  </constraint>
  
</jqa:jqassistant-rules>
```

## Baseline Rules (Planned)

Archim8 will include these baseline rule sets:

### 1. Structure Rules
- No orphaned classes
- All public methods have JavaDoc (warning)
- Consistent package naming

### 2. Dependency Rules
- No circular package dependencies
- Layer constraints (configurable)
- Module boundary enforcement

### 3. Quality Rules
- Maximum class complexity
- Maximum method length
- Dead code detection

### 4. Architecture Patterns
- Identify service boundaries
- Detect potential microservices
- Find aggregates/bounded contexts

## Usage

```bash
# Run with specific rule group
jqassistant analyze -concepts baseline

# Run all constraints
jqassistant analyze -constraints all

# Generate HTML report
jqassistant analyze -reportDirectory target/jqassistant/report
```

## References

- [jQAssistant Rules Documentation](https://jqassistant.org/get-started/#_rules)
- [Example Rules Repository](https://github.com/jqassistant-contrib)
