# Content and data display

## Naming

Use “Keyword” in the method selector and “MariaDB full-text” in explanations. Never rename the implementation BM25. Use “Meaning” for vector retrieval, “Fused” for fusion and “CiteHop” for the graph-enhanced path. Use “extraction confidence” only for stored concept-extraction confidence, never as a synonym for relevance.

## Missing, zero and pending

| Condition | Display |
| --- | --- |
| Null year | Year not available |
| Null abstract | Abstract not available |
| Empty author list | Authors not available |
| Unmeasured latency | Not measured |
| No experiment run | — and Not run |
| Measured zero | Numeric zero in the correct unit |
| Undefined configuration | Definition pending |
| Expected corpus size | Expected; do not imply loaded |
| Partial result | Explicit unavailable methods |

## Numeric formats

Recall: percent, one decimal. nDCG/MRR: 0–1 values, three decimals. Latency: milliseconds with p50/p95 stated. Counts: locale-appropriate thousands separators. Preserve raw values and metadata in exports. Display comparable intervals and deltas on the same scale. A retrieval score is not a probability.

## Evidence

Abstract excerpts come from the record, not a generated summary. Evidence quotes must match the stored abstract text. Keep concept relation and kind adjacent to the quote. If evidence is absent, say so and withhold the asserted extraction. Provenance may show several found_via values simultaneously.

## Error copy

Use a concrete failure and recovery action: “Search could not finish. Your question is preserved. Retry.” Avoid blaming the user, exposing SQL errors or implying a successful branch completed when it did not. A timeout is not a zero-result response.

## Prototype content

All paper titles, author names, citation edges and provenance examples are fictional. Keep this disclosure visible in prototype mode. Expected corpus sizes are source facts; they are not load verification. The application must obtain real records from approved backend adapters before dropping the fixture disclosure.
