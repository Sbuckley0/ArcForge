# 05_deliver/input/04_generate

Input feedstock for the `04_generate` stage — CSVs and structured data consumed
by diagram generators and documentation renderers.

Populated by `make jqa-export` (Phase 4) and `make neo4j-export` (jdeps layer, live now).

> **Current status:** jdeps exports are live in `03_query/`. jQA exports land here in Phase 4.

## Expected Files (Phase 4+)

| File | Source query | Used by |
|------|-------------|---------|
| `module-deps-maven.csv` | `jqa/module-deps-maven.cypher` | C4 container diagram generator |
| `package-deps.csv` | `jqa/package-deps.cypher` | C4 component diagram generator |
| `api-surface.csv` | `jqa/api-surface.cypher` | API surface report |
| `key-abstractions.csv` | `jqa/key-abstractions.cypher` | Core interfaces report |
| `cobol-subsystem.csv` | `jqa/cobol-subsystem.cypher` | Cobol emulation subsystem diagram |

All files in this folder are gitignored (pipeline outputs — regenerated on each run).

## Diagram Outputs

Generated files land in `05_deliver/output/`:

| Output | Generator | Description |
|--------|-----------|-------------|
| `arc-containers.puml` | `04_generate/generators/scripts/` | C4 container diagram (Maven modules) |
| `arc-components-{module}.puml` | same | C4 component diagram per module |
| `arc-cobol-emulation.puml` | same | Cobol emulation subsystem |

Run `make generate-diagrams` (Phase 4) to produce all outputs.

All files except this README are gitignored.
