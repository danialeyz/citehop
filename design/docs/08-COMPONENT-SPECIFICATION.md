# Component specification

All dimensions and colors come from the canonical CSS. Use named tokens rather than copying arbitrary values into individual views. Reuse components across screens.

| Component | Inputs | Output / interaction | Edge cases |
| --- | --- | --- | --- |
| AppShell | active view, context label | Main navigation and skip link | Narrow viewport, long context |
| QueryComposer | query, method, busy, error | Explicit submit; method selection | Blank input, max length, repeated submit |
| RetrievalBadge | kw / vec / cite / concept / author | Text and distinct signal color | Multiple labels, unknown label rejected |
| PaperResult | rank, paper, provenance | Open detail by corpusid | Long title, no abstract, missing authors |
| EvidencePanel | concept, kind, relation, quotation | Inspect supporting abstract text | Missing evidence, invalid quotation |
| ProvenancePanel | found_via, paths, score metadata | Explain retrieval route | Unknown contributions, partial search |
| GraphViewport | nodes, edges, seed, depth, truncated | Node selection and readable list | Empty, capped, disconnected, cyclic graph |
| NodeInspector | selected identity and connections | Inspect related record | Repeated labels with distinct IDs |
| MetricCard | value or null, unit, state, eligibility | Read measured result | Distinguish no run from zero |
| AblationTable | A–L definitions, split, run data | Compare against C | Pending definition, failed run, overflow |
| ParameterField | name, value, backend constraints | Development-only configuration edit | Invalid number, unresolved semantics |
| StateBanner | kind, message, recovery | Retry/refine/cancel as applicable | Preserve query and settings |

## Contract rules

Components receive presentation data. They do not query MariaDB. Result selection emits corpusid, not row index. Nodes emit prefixed stable IDs. The application layer owns current query, method and selected object. Do not duplicate server-derived metrics in local component state.

## Control semantics

Buttons perform actions; anchors navigate. Use native select, input, checkbox and button elements where possible. Inputs have visible labels. Method selection uses a single-selection group with an announced selected state. A disabled control includes an explanation nearby when its reason is not obvious.

## Graph details

The reference's spatial positions are illustrative and carry no similarity meaning. Radial guides are visual orientation aids. Every edge needs a type and a direction. Node type is conveyed by label and shape/icon, not only color. Add venue nodes using the documented schema when data is available.

Selected-node details must update without discarding the query. Provide a readable connection list as a first-class alternative. Production panning and zooming require reset and keyboard alternatives; they are not implemented by the reference fixture.

## Implementation fidelity

Each component above becomes one React component in web/src/components/. Match color, type hierarchy, spacing, content order and responsive intent first. React renders native HTML controls, so pixel parity with the prototype is the target. Document any visual deviation and compare it to the approved structure. Do not disguise framework constraints with screenshots masquerading as interactive controls.
