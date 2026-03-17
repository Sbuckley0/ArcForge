# C4 Model Diagram Guidelines for Archim8

Reference: https://c4model.com/

---

## Abstraction Hierarchy

```
Person → uses → Software System → contains → Container → contains → Component → implemented by → Code (Class/Interface)
```

| Level | Abstraction | Audience | Detail |
|-------|-------------|----------|--------|
| C1    | System Context | Everyone | The system + who/what it interacts with. No technology detail. |
| C2    | Container | Developers, architects | Deployable/runnable units (JARs, services, DBs, message queues). Technology choices visible. |
| C3    | Component | Developers | Major structural building blocks inside a single container. Interfaces and responsibilities. |
| C4    | Code        | Developers | Class/interface level. Only needed for the most complex or critical paths. |

---

## Diagram Level Rules

### C1 — System Context
- Show the **software system** as a single box in the centre.
- Surround with **People** (users, actors) and **External Software Systems** it interacts with.
- Label every relationship with *what* and *how* (e.g. "sends orders via", "reads from").
- No containers, no components, no code details.
- Minimum content: ≥1 Person or external system interacting with the focal system.

### C2 — Container
- Zoom into the software system from C1.
- Each box = one **deployable/runnable unit** (e.g. `common-messaging.jar`, REST API, database).
- Technology stack visible on each container (e.g. "Java", "Apache Kafka", "PostgreSQL").
- People and external systems from C1 can be shown at the edges for context.
- Minimum content: ≥3 containers with labelled relationships.

### C3 — Component
- Zoom into a **single container** from C2.
- Each box = one **component** (a module, a major class group, a library facade).
- Show the interfaces/APIs and key implementation classes.
- External containers from C2 may appear at diagram boundaries.
- Minimum content: ≥3 components with labelled dependencies.

### C4 — Code
- Zoom into a **single component** from C3.
- UML class diagram showing classes, interfaces, enumerations, annotations.
- Show key **fields** and **methods** (not every getter/setter — curated for clarity).
- Minimum content: stereotypes (`<<interface>>`, `<<enumeration>>`, `<<annotation>>`),
  visibility modifiers on members, relationship types (extends, implements, uses).

---

## Layout Rules (per level)

### C1 — System Context
- Focal software system in the **centre**
- People (users/actors) on the **left** or **top-left**
- External software systems on the **right** or **edges**
- Use generous whitespace — this is a business-audience diagram

### C2 — Container
- Top-down flow: entry points (users, external callers) at the **top**
- Containers in the **middle** in runtime/call order (left-to-right or top-to-bottom)
- External systems and data stores at the **bottom** or **edges**
- Technology labels visible on each container node

### C3 — Component
- The selected container's boundary is the focal wrapper
- Entry-point/facade components at the **top**
- Core implementation components in the **centre**
- Supporting/utility components (config, settings, enums) at the **bottom**
- External components from C2 appear at diagram edges, not centre

### C4 — Code
- Group by package / namespace / architectural responsibility
- **Abstractions** (interfaces, abstract classes) above or to the **left** of implementations
- Implementations **below or right** of the abstractions they fulfil
- Enumerations and value types near the classes that use them
- External callers at the **top**; configuration/settings at the **bottom**

---

## Relationship Language Rules (per level)

| Level | Language style | Examples |
|-------|---------------|---------|
| C1 | Business / system language | "submits orders via", "reads account data from", "sends notifications to" |
| C2 | Runtime / integration language | "makes API call to", "publishes event to", "reads from", "queries via JDBC" |
| C3 | Internal-component collaboration language | "delegates to", "uses", "wired by", "bootstraps", "configured by" |
| C4 | Code / UML language | `implements`, `extends`, `uses`, `maps`, `calls via CICS`, `reads config` |

Keep relationship labels:
- **Short** (2–4 words preferred)
- **Directional** (label describes what the *source* does to/with the *target*)
- **At the right abstraction level** — never use code-level terms in a C1 label or business terms in a C4 label

---

## Colour Legend (fixed — apply to ALL CX diagrams)

| Element              | Fill       | Stroke     | Hex Pair                  |
|----------------------|------------|------------|---------------------------|
| Person               | Dark navy  | —          | `#1E4074` / `#122448`     |
| Software System      | Med blue   | —          | `#3162AF` / `#1e3d6a`     |
| Container            | Sky blue   | Med blue   | `#52A2D8` / `#2d6f9c`     |
| Component            | Lt blue    | Med blue   | `#7DBEF2` / `#5B9BD5`     |
| External Person      | Dk grey    | —          | `#6B6477` / `#4a4056`     |
| External System      | Med grey   | Dk grey    | `#8B8496` / `#5e5a68`     |
| Violation (special)  | Dark red   | Red        | `#8B0000` / `#ff4444`     |

All diagrams use a **white background** (`#ffffff`) with **white text** inside coloured boxes.

---

## Hard Separation Rule: C1–C3 vs C4 Diagrams

**C1–C3 architecture views** and **C4 code/class views** use different Mermaid diagram types and
init blocks. **Do not blend the two styles.**

### C1–C3 — shape-based architecture view (`flowchart TB`)
- Diagram type: `flowchart TB` (or `flowchart LR` for violations)
- Solid-fill rectangles via `classDef` — `classDef fill` controls the **entire** node box
- `subgraph` blocks for group wrappers (not `namespace`)
- Plain labeled rectangle legend via `_c4_legend_flowchart()`
- No UML compartments, no method lists, no stereotype notation
- Colors carry semantic meaning (blue = internal, grey = external)

```
%%{init: {'theme': 'base', 'themeVariables': {
  'background':          '#ffffff',
  'primaryColor':        '#ffffff',      ← default node fill (overridden by classDef on all typed nodes)
  'primaryTextColor':    '#555555',      ← subgraph title labels and edge label text
  'lineColor':           '#666666',
  'secondaryColor':      '#f0f0f0',      ← subgraph fill
  'tertiaryColor':       '#f0f0f0',
  'edgeLabelBackground': '#ffffff'
}}}%%
```

Relationship arrows: `A -->|"label"| B` (flowchart pipe syntax), `A -.->|"implements"| B` for dashed.
Legend: `subgraph Legend["Legend"] direction LR … end` with plain `NodeId["Label"]:::cls` entries.

### C4 — UML code view (`classDiagram`)
- Diagram type: `classDiagram`
- `primaryColor` fills **only the header bar** of every class node — set to `#7DBEF2` so
  framework class header + body unify as solid blue. `classDef fill` colors the body section only.
- `primaryTextColor: '#333333'` — **dark** so edge/relationship labels are readable on white.
  Class-box text stays white via `color:#ffffff` in each `classDef` (independent of `primaryTextColor`).
- `namespace` blocks for grouping (not `subgraph`)
- Full UML: stereotypes, fields, methods, visibility modifiers
- External elements: `:::external` classDef + `<<external>>` stereotype (text-first signaling)
- Color supports structure, not semantic tier distinction

```
%%{init: {'theme': 'base', 'themeVariables': {
  'background':          '#ffffff',
  'primaryColor':        '#7DBEF2',      ← class header bars: framework blue, unifies with body for internal classes
  'primaryTextColor':    '#333333',      ← edge label text: dark grey, readable — NOT white
  'primaryBorderColor':  '#5B9BD5',      ← class border: medium blue
  'lineColor':           '#666666',
  'secondaryColor':      '#ffffff',
  'tertiaryColor':       '#ffffff',
  'edgeLabelBackground': '#f8f8f8'       ← subtle background behind edge labels to prevent bleedthrough
}}}%%
```

> **Why `primaryColor: #7DBEF2` for classDiagram?** Mermaid classDiagram renders class nodes as
> two sections: a header bar (name row) filled by `primaryColor`, and a body section (members)
> filled by `classDef fill`. Empty-body classes have no body section — the entire box is the header
> — so `classDef fill` is invisible. Setting `primaryColor` to the framework blue makes all headers
> match the `classDef framework` body fill, giving a unified solid-blue appearance. External classes
> keep their grey body via `classDef external` and are marked with `<<external>>` stereotype.

---

## Mermaid `classDef` snippets (used in both diagram types)

Strokes are a slightly darker shade of the fill:
```
classDef c4person      fill:#1E4074,stroke:#122448,color:#ffffff,font-weight:bold
classDef c4system      fill:#3162AF,stroke:#1e3d6a,color:#ffffff,font-weight:bold
classDef c4container   fill:#52A2D8,stroke:#2d6f9c,color:#ffffff,font-weight:bold
classDef framework     fill:#7DBEF2,stroke:#5B9BD5,color:#ffffff,font-weight:bold
classDef c4extperson   fill:#6B6477,stroke:#4a4056,color:#ffffff,font-style:italic
classDef external      fill:#8B8496,stroke:#5e5a68,color:#ffffff,font-style:italic
classDef violation     fill:#8B0000,stroke:#ff4444,color:#ffffff,font-weight:bold
```

> **Mermaid classDiagram limitation:** Namespaces cannot be nested. There is no outer "system
> boundary" wrapper. For diagrams requiring nested ownership boundaries (System → Container layer),
> use C4Component with `Container_Boundary(...)` blocks (see `C2-Messaging.mmd`).

---

## Notation Rules

### External elements
Always tag external actors/systems with `<<external>>` stereotype so consumers vs providers are
instantly visible. In Mermaid classDiagram this is the class body stereotype:
```
class SomeExternalClass["SomeExternalClass"]:::external {
    <<external>>
}
```

### Naming convention for output files
```
05_deliver/output/diagrams/{subject-folder}/CX-{Descriptive-Name}.mmd
```

Examples:
- `diagrams/messaging/C2-Messaging.mmd`          — Container diagram of messaging subsystem
- `diagrams/messaging/C3-Messaging-Classes.mmd`  — Component/class diagram of messaging types
- `diagrams/overview/C1-Layer-Overview.mmd`      — System context / layer topology
- `diagrams/overview/Violations.mmd`             — Architecture violation report

### Boundaries / namespaces
Group related elements to clarify ownership:
- **C1–C3 flowchart**: use `subgraph Name["Name"] … end` blocks, **PascalCase** names
  (e.g. `CoreQueue`, `BootstrapExt`); external groups suffixed `Ext`
- **C4 classDiagram**: use `namespace Name { … }` blocks, same naming convention
- Framework / internal types → one wrapper per JAR or logical role
- External consumers → one wrapper per consumer group, **suffixed `Ext`**
- Always append a legend at the end of every generated diagram

### Legend format
- **C1–C3 flowchart**: `subgraph Legend["Legend"] direction LR … end` with plain `NodeId["Label"]:::cls` nodes (no compartments)
- **C4 classDiagram**: `namespace Legend { … }` with `class _Ln_["Label"]:::cls { <<#hexcode>> }` — the stereotype body forces a body section so the `classDef fill` color is visible

---

## Class Diagram (C4) Quality Checklist

- [ ] Every class/interface has the correct stereotype (`<<interface>>`, `<<enumeration>>`, `<<annotation>>`, `<<abstract>>`)
- [ ] Key public fields listed (max ~3-4, skip generated boilerplate)
- [ ] Key public methods listed (max ~4-6, skip `equals`/`hashCode`/`toString`)
- [ ] Visibility prefix on every member (`+` public, `-` private, `#` protected)
- [ ] No "islands" — every node has ≥1 incoming or outgoing edge
- [ ] External callers shown in grey (`:::external`) with `<<external>>` stereotype
- [ ] IMPLEMENTS shown as `..|>`, EXTENDS as `--|>`, USES/DEPENDS as `-->`
- [ ] Relationship label describes the semantic (e.g. `implements`, `bootstraps`, `maps`, `configured by`)

---

## Generating Diagrams

Use the `archim8_generate_mermaid_diagram` tool:

| `diagram_type`      | Output path                                     | C Level | Format        |
|---------------------|-------------------------------------------------|---------|---------------|
| `messaging`         | `diagrams/messaging/C2-Messaging.mmd`           | C2      | C4Component   |
| `messaging-classes` | `diagrams/messaging/C3-Messaging-Classes.mmd`   | C3      | flowchart TB  |
| `layer-overview`    | `diagrams/overview/C1-Layer-Overview.mmd`       | C1      | flowchart TB  |
| `violations`        | `diagrams/overview/Violations.mmd`              | —       | flowchart LR  |
| `all`               | all of the above                                | —       | —             |

The **C4 class view** (`C4-Messaging-Classes.mmd`) is hand-authored in `classDiagram` format
and is not regenerated by the tool — it captures curated UML detail that does not change often.

Open any `.mmd` file in VS Code → **Ctrl+Shift+P → Mermaid: Open Preview to the Side**.
