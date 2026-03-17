# 04_generate — Generation & Transformation (Layer 5)

Consumes query results from the graph and produces human-readable architecture artifacts: structured Markdown views and PlantUML C4 diagrams. Also maintains the manifest index that the MCP tools use to find existing views.

---

## Structure

```
04_generate/
├── generators/                          # Diagram and document generators
│   ├── scripts/
│   │   ├── generate_views.py            # Runs Cypher queries → Markdown views
│   │   ├── generate_plantuml.py         # Generates PlantUML C4 diagrams from graph
│   │   └── manifest.py                  # Manifest index read/write helpers
│   └── templates/
│       ├── architecture-overview.md.j2  # Jinja2 template: Markdown architecture view
│       └── context.puml.j2              # Jinja2 template: PlantUML C4 context diagram
└── agents/                              # Future: LLM-assisted generation helpers
    ├── chunking/                        # (placeholder)
    ├── guardrails/                      # (placeholder)
    ├── indexing/                        # (placeholder)
    └── prompts/                         # (placeholder)
```

---

## How to run

```powershell
# From archim8/ root — prerequisites: Neo4j running with data ingested

make generate-views          # Run all Cypher queries → views/*.md + update manifest
make generate-views FORCE=1  # Regenerate all views even if already in manifest
make generate-views VIEW=<name>  # Regenerate a single named view

make generate-diagrams       # Generate PlantUML C4 diagrams from live graph
make generate-diagrams DIAGRAM=containers  # Specific diagram: containers|cobol|all
make generate-diagrams FORCE=1             # Force regeneration

make generate-all            # views + diagrams (full Phase 4 run)
make generate-pipeline       # jqa-pipeline + generate-all
```

Outputs go to `05_deliver/output/` (gitignored):

| Output | Path | Description |
|--------|------|-------------|
| Architecture views | `05_deliver/output/views/*.md` | One Markdown file per query |
| Container diagram | `05_deliver/output/arc-containers.puml` | C4 container diagram |
| COBOL diagram | `05_deliver/output/arc-cobol-emulation.puml` | COBOL subsystem C4 |
| Manifest | `05_deliver/output/manifest.json` | Index of all generated views + metadata |

---

## Manifest

`manifest.json` is the generation index. Before regenerating any view, `generate_views.py` checks the manifest — if the query hasn’t changed and the view is current, it skips regeneration. Use `FORCE=1` to override.

The MCP tools `archim8_list_available_views` and `archim8_read_architecture_view` consume this manifest at runtime. Adding a new view automatically makes it discoverable to the MCP tools on next run.

---

## Adding or customising output

**Add a new view**: drop a `.cypher` file in `03_query/cypher/library/<concern>/` and run `make generate-views`. No registration needed.

**Customise a Markdown view**: edit the Jinja2 template in `generators/templates/`. The template receives the full query result set as `rows`.

**Add a PlantUML diagram**: add a renderer in `generate_plantuml.py` and wire it to a `DIAGRAM=<name>` value in the Makefile.
