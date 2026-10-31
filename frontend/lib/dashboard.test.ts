// Run with `npm test` (Node's built-in runner; Node strips the TypeScript types).
import assert from "node:assert/strict";
import { test } from "node:test";

import type { Schemas } from "./api/client";
import {
  compareWithLive,
  dashboardHref,
  formatMs,
  formatRecall,
  labelReview,
  methodSummaries,
  parseDashboardState,
  reviewCounts,
  selectRun,
  selectSplit,
} from "./dashboard.ts";

type Manifest = Schemas["RunManifest"];

// Trimmed from results/runs/20261031T162301Z-dev-test-15b1f5a1/manifest.json.
function manifest(overrides: Partial<Manifest> = {}): Manifest {
  return {
    schema: "citehop-eval-v1",
    run_id: "run-a",
    created_at: "2026-10-31T16:23:01+00:00",
    splits: { dev: 10, test: 20 },
    corpus: { id: "corpus:2", version_id: 2 },
    chunk_configs: [{ embedding_config: "emb-1", chunk_config: "chunk-1", chunks: 1776 }],
    question_set: { label_review: { unreviewed: 30 } },
    config: { methods: { dev: ["keyword", "vector", "exact"], test: ["vector", "keyword"] }, embedding_config: "emb-1" },
    summary: {
      retrieval: {
        test: {
          keyword: { all_answerable: { n: 17, recall_at_5: 0.9588 }, unfiltered: { n: 12, recall_at_5: 0.9417 } },
          vector: { all_answerable: { n: 17, recall_at_5: 0.9765 } },
        },
      },
      latency: {
        test: {
          samples: { questions: 20, records: 54 },
          embedding_ms: { n: 54, unit: "ms", median: 12.851, p95: 18.602 },
          retrieval_ms_keyword: { n: 54, unit: "ms", median: 5.633, p95: 9.466 },
          retrieval_ms_vector: { n: 54, unit: "ms", median: 8.518, p95: 86.089 },
        },
      },
      unanswerable: { test: { keyword: { n: 3 } } },
    },
    ...overrides,
  };
}

function corpus(overrides: Partial<Schemas["CorpusStats"]> = {}): Schemas["CorpusStats"] {
  return {
    corpus_version: "corpus:2",
    articles: 100,
    smoke_articles: 10,
    distinct_categories: 456,
    category_memberships: 1101,
    article_links: 917,
    chunks: 1776,
    embedding_configs: [{ chunk_config: "chunk-1", embedding_config: "emb-1", chunks: 1776, articles_covered: 100, token_count_min: 51, token_count_max: 300 }],
    ...overrides,
  };
}

function answer(split: string, status: string, answerable: boolean, review: Schemas["RunAnswerReview"] | null): Schemas["RunAnswer"] {
  return {
    question_id: `${split}-${status}`, split, question: null, answerable, expected_answer: null, retrieval: null, status, text: null,
    citations: null, sources: [], reason: null, model: null, prompt_version: null, generation_ms: null, truncated: null, review,
  };
}

test("state round-trips through the URL and ignores blanks", () => {
  assert.deepEqual(parseDashboardState({ run: ["run-a", "run-b"], split: " " }), { run: "run-a", split: undefined });
  assert.equal(dashboardHref({ run: "run a", split: "dev" }), "/dashboard?run=run+a&split=dev");
  assert.equal(dashboardHref({}), "/dashboard");
});

test("unknown run falls back to the newest; unknown split to test", () => {
  const runs = [manifest({ run_id: "new" }), manifest({ run_id: "old" })];
  assert.equal(selectRun(runs, "old")?.run_id, "old");
  assert.equal(selectRun(runs, "missing")?.run_id, "new");
  assert.equal(selectRun([], "x"), null);
  assert.equal(selectSplit(runs[0], "dev"), "dev");
  assert.equal(selectSplit(runs[0], "train"), "test");
  assert.equal(selectSplit(manifest({ splits: { dev: 10 } })), "dev");
});

test("method summaries keep saved values and denominators and order methods", () => {
  const [keyword, vector] = methodSummaries(manifest(), "test");
  assert.equal(keyword.method, "keyword");
  assert.deepEqual(keyword.recall, { n: 17, value: 0.9588 });
  assert.deepEqual(keyword.recallUnfiltered, { n: 12, value: 0.9417 });
  assert.deepEqual(keyword.latency, { n: 54, median: 5.633, p95: 9.466, unit: "ms" });
  assert.equal(keyword.unanswerable, 3);
  assert.equal(vector.method, "vector");
  assert.equal(vector.latency.p95, 86.089);
});

test("missing or malformed summary values are null, never zero", () => {
  const broken = manifest({ summary: { retrieval: { test: { keyword: { all_answerable: { n: "17", recall_at_5: null } } } } } });
  const [keyword, vector] = methodSummaries(broken, "test");
  assert.deepEqual(keyword.recall, { n: null, value: null });
  assert.deepEqual(vector.latency, { n: null, median: null, p95: null, unit: null });
  assert.equal(vector.recallFiltered.value, null);
  assert.deepEqual(methodSummaries(manifest({ summary: null }), "dev").map((m) => m.recall.value), [null, null, null]);
  assert.equal(formatRecall(null), "Not measured");
  assert.equal(formatMs(null), "Not measured");
  assert.equal(formatMs(8.518), "8.5 ms");
  assert.equal(formatRecall(0.9765), "0.9765");
  assert.equal(formatRecall(1), "1.00");
});

test("a run on another corpus or embedding config is flagged, not silently compared", () => {
  assert.deepEqual(compareWithLive(manifest(), corpus()), { kind: "match" });
  assert.deepEqual(compareWithLive(manifest(), null), { kind: "unknown" });
  const changed = compareWithLive(manifest(), corpus({ corpus_version: "corpus:3", embedding_configs: [] }));
  assert.equal(changed.kind, "mismatch");
  assert.equal(changed.kind === "mismatch" && changed.reasons.length, 2);
});

test("review counts are per split with explicit denominators", () => {
  const answers = [
    answer("test", "answered", true, { status: null, grounded: null }),
    answer("test", "answered", true, { status: "approved", grounded: true, citations_support: true }),
    answer("test", "answered", true, { status: "needs_changes", grounded: false }),
    answer("test", "insufficient_evidence", false, { status: "approved", correct_abstention: true }),
    answer("test", "insufficient_evidence", false, null),
    answer("dev", "answered", true, { status: "approved", grounded: true }),
  ];
  const counts = reviewCounts(answers, "test");
  assert.equal(counts.prepared, 5);
  assert.equal(counts.answered, 3);
  assert.equal(counts.abstained, 2);
  assert.equal(counts.reviewed, 3);
  assert.equal(counts.approved, 2);
  assert.equal(counts.needsChanges, 1);
  assert.deepEqual(counts.grounded, { yes: 1, no: 1, denominator: 2 });
  assert.deepEqual(counts.abstentions, { correct: 1, incorrect: 0, denominator: 1 });
  assert.equal(reviewCounts(answers, "other").prepared, 0);
});

test("label review counts come from the manifest", () => {
  assert.deepEqual(labelReview(manifest()), { unreviewed: 30 });
  assert.equal(labelReview(manifest({ question_set: null })), null);
});
