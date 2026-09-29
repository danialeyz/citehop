# Proposed presentation contract

search-view.schema.json describes the adapter output from docs/04-DATA-AND-INTEGRATION.md. It is not a raw dataset schema or an existing HTTP API. The example is fictional and deliberately uses an ID larger than JavaScript's safe integer range. Preserve it as a string.

Application validation must additionally ensure returned_count equals results.length, ranks are unique and ordered, graph_only agrees with candidate provenance, and path nodes/edges agree. JSON schema validation alone cannot establish those research semantics.
