# Experiments

Stub. Filled in M5 and M7 from CITEHOP_BOOTSTRAP.md 5.6.

It will hold:

- The A to L config table, plus config P (the prototype S01 recipe on LitSearch). One row each: config, what it adds, the question it answers.
- Metrics, one line each: Recall@5 (specific questions), Recall@20 (broad questions), nDCG@10, MRR, found-only-via-graph, p50/p95 latency.
- Split rules: tune on dev only, report on test only.
- Significance: paired bootstrap, 1,000 resamples, 95% interval vs config C.
- Published LitSearch baselines to cite.

The prototype experiments S01 to S03 are documented in [RETRIEVAL.md](RETRIEVAL.md), [GRAPH_RETRIEVAL.md](GRAPH_RETRIEVAL.md) and [CHUNKING_EXPERIMENT.md](CHUNKING_EXPERIMENT.md).
