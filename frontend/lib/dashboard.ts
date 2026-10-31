// Dashboard view model. Saved C08 manifests pass most fields through untyped, so every
// value is read defensively: anything absent or of the wrong type becomes null ("Not
// measured"), never 0. Pure functions only; unit-tested with `npm test`.
import type { Schemas } from "./api/client";

type Manifest = Schemas["RunManifest"];
type Stats = Schemas["Stats"];
type Answer = Schemas["RunAnswer"];

export type SearchParams = Record<string, string | string[] | undefined>;
export type DashboardState = { run?: string; split?: string };

// Display order and labels; methods a run did not evaluate are simply absent.
const METHOD_ORDER = ["keyword", "vector", "exact"];
export const METHOD_LABELS: Record<string, string> = {
  keyword: "Keyword (FULLTEXT)",
  vector: "Vector (HNSW)",
  exact: "Exact cosine scan",
};

function first(value: string | string[] | undefined): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  return v?.trim() || undefined;
}

export function parseDashboardState(params: SearchParams): DashboardState {
  return { run: first(params.run)?.slice(0, 100), split: first(params.split)?.slice(0, 40) };
}

export function dashboardHref(state: DashboardState): string {
  const query = new URLSearchParams();
  if (state.run) query.set("run", state.run);
  if (state.split) query.set("split", state.split);
  const qs = query.toString();
  return qs ? `/dashboard?${qs}` : "/dashboard";
}

/** Requested run if it exists, else the newest (the API lists newest first). */
export function selectRun(runs: Manifest[], requested?: string): Manifest | null {
  return runs.find((r) => r.run_id === requested) ?? runs[0] ?? null;
}

/** Requested split if the run has it; else "test" (the held-out split), else the first. */
export function selectSplit(manifest: Manifest, requested?: string): string {
  const splits = Object.keys(manifest.splits);
  if (requested && splits.includes(requested)) return requested;
  return splits.includes("test") ? "test" : splits[0];
}

// --- defensive readers -------------------------------------------------------------------

export function obj(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

export function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function str(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function path(root: unknown, ...keys: string[]): unknown {
  let node = root;
  for (const key of keys) node = obj(node)?.[key];
  return node;
}

// --- retrieval comparison ----------------------------------------------------------------

export type Recall = { n: number | null; value: number | null };
export type Latency = { n: number | null; median: number | null; p95: number | null; unit: string | null };
export type MethodSummary = {
  method: string;
  label: string;
  recall: Recall; // answerable questions only
  recallUnfiltered: Recall;
  recallFiltered: Recall;
  latency: Latency; // retrieval_ms over every timed call (repetitions included)
  latencyUnfiltered: Latency;
  latencyFiltered: Latency;
  unanswerable: number | null;
};

function recall(node: unknown): Recall {
  return { n: num(path(node, "n")), value: num(path(node, "recall_at_5")) };
}

function latency(node: unknown): Latency {
  return { n: num(path(node, "n")), median: num(path(node, "median")), p95: num(path(node, "p95")), unit: str(path(node, "unit")) };
}

/** Methods evaluated on this split (from the saved config, else the summary keys). */
export function splitMethods(manifest: Manifest, split: string): string[] {
  const configured = path(manifest, "config", "methods", split);
  const names = Array.isArray(configured)
    ? configured.filter((m): m is string => typeof m === "string")
    : Object.keys(obj(path(manifest.summary, "retrieval", split)) ?? {});
  const rank = (m: string) => (METHOD_ORDER.includes(m) ? METHOD_ORDER.indexOf(m) : METHOD_ORDER.length);
  return [...new Set(names)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

export function methodSummaries(manifest: Manifest, split: string): MethodSummary[] {
  const retrieval = path(manifest.summary, "retrieval", split);
  const timing = path(manifest.summary, "latency", split);
  return splitMethods(manifest, split).map((method) => ({
    method,
    label: METHOD_LABELS[method] ?? method,
    recall: recall(path(retrieval, method, "all_answerable")),
    recallUnfiltered: recall(path(retrieval, method, "unfiltered")),
    recallFiltered: recall(path(retrieval, method, "filtered")),
    latency: latency(path(timing, `retrieval_ms_${method}`)),
    latencyUnfiltered: latency(path(timing, `retrieval_ms_${method}_unfiltered`)),
    latencyFiltered: latency(path(timing, `retrieval_ms_${method}_filtered`)),
    unanswerable: num(path(manifest.summary, "unanswerable", split, method, "n")),
  }));
}

/** Query embedding is timed once per record and shared by vector methods; kept separate. */
export function embeddingLatency(manifest: Manifest, split: string): Latency {
  return latency(path(manifest.summary, "latency", split, "embedding_ms"));
}

export function generationLatency(manifest: Manifest): Latency {
  return latency(path(manifest.summary, "generation", "generation_ms"));
}

export function latencySamples(manifest: Manifest, split: string): { questions: number | null; records: number | null } {
  const samples = path(manifest.summary, "latency", split, "samples");
  return { questions: num(path(samples, "questions")), records: num(path(samples, "records")) };
}

// --- grounding review ---------------------------------------------------------------------

export type ReviewCounts = {
  prepared: number; // answers saved for this split
  answered: number;
  abstained: number;
  otherStatus: number;
  reviewed: number;
  approved: number;
  needsChanges: number;
  grounded: { yes: number; no: number; denominator: number }; // reviewed answered cases
  abstentions: { correct: number; incorrect: number; denominator: number }; // reviewed unanswerable
};

const REVIEWED = (a: Answer) => {
  const status = a.review?.status;
  return status != null && status !== "unreviewed";
};

export function reviewCounts(answers: Answer[], split: string): ReviewCounts {
  const own = answers.filter((a) => a.split === split);
  const reviewed = own.filter(REVIEWED);
  const groundedCases = reviewed.filter((a) => a.status === "answered" && typeof a.review?.grounded === "boolean");
  const abstainCases = reviewed.filter((a) => a.answerable === false && typeof a.review?.correct_abstention === "boolean");
  return {
    prepared: own.length,
    answered: own.filter((a) => a.status === "answered").length,
    abstained: own.filter((a) => a.status === "insufficient_evidence").length,
    otherStatus: own.filter((a) => a.status !== "answered" && a.status !== "insufficient_evidence").length,
    reviewed: reviewed.length,
    approved: reviewed.filter((a) => a.review?.status === "approved").length,
    needsChanges: reviewed.filter((a) => a.review?.status === "needs_changes").length,
    grounded: {
      yes: groundedCases.filter((a) => a.review?.grounded === true).length,
      no: groundedCases.filter((a) => a.review?.grounded === false).length,
      denominator: groundedCases.length,
    },
    abstentions: {
      correct: abstainCases.filter((a) => a.review?.correct_abstention === true).length,
      incorrect: abstainCases.filter((a) => a.review?.correct_abstention === false).length,
      denominator: abstainCases.length,
    },
  };
}

/** Question-label review counts from the manifest, e.g. {unreviewed: 30}. */
export function labelReview(manifest: Manifest): Record<string, number> | null {
  const counts = obj(path(manifest, "question_set", "label_review"));
  if (!counts) return null;
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(counts)) {
    const n = num(value);
    if (n !== null) out[key] = n;
  }
  return out;
}

// --- saved run vs live snapshot ----------------------------------------------------------

export type Compatibility =
  | { kind: "unknown" } // live counts unavailable
  | { kind: "match" }
  | { kind: "mismatch"; reasons: string[] };

function runEmbeddingConfigs(manifest: Manifest): string[] {
  const chunkConfigs = manifest.chunk_configs;
  const fromChunks = Array.isArray(chunkConfigs) ? chunkConfigs.map((c) => str(path(c, "embedding_config"))) : [];
  const configured = str(path(manifest, "config", "embedding_config"));
  return [...new Set([...fromChunks, configured].filter((c): c is string => c !== null))];
}

/** Whether a saved run describes the corpus and embeddings that are loaded right now. */
export function compareWithLive(manifest: Manifest, corpus: Stats["corpus"] | null): Compatibility {
  if (!corpus) return { kind: "unknown" };
  const reasons: string[] = [];
  if (manifest.corpus.id !== corpus.corpus_version) {
    reasons.push(`The run measured ${manifest.corpus.id}; MariaDB now holds ${corpus.corpus_version}.`);
  }
  const live = new Set(corpus.embedding_configs.map((c) => c.embedding_config));
  const missing = runEmbeddingConfigs(manifest).filter((c) => !live.has(c));
  if (missing.length) {
    reasons.push(`The run's embedding configuration ${missing.map(shortHash).join(", ")} is no longer stored.`);
  }
  return reasons.length ? { kind: "mismatch", reasons } : { kind: "match" };
}

// --- formatting ------------------------------------------------------------------------

export const NOT_MEASURED = "Not measured";

export function shortHash(value: string): string {
  return value.length > 14 ? `${value.slice(0, 12)}…` : value;
}

export function formatRecall(value: number | null): string {
  // Saved precision (4 places), so the page matches the manifest without re-rounding.
  return value === null ? NOT_MEASURED : value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

export function formatMs(value: number | null): string {
  if (value === null) return NOT_MEASURED;
  return `${value.toLocaleString("en-US", { maximumFractionDigits: value >= 100 ? 0 : 1 })} ms`;
}

export function formatCount(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not reported" : value.toLocaleString("en-US");
}

export function percent(part: number, whole: number): string {
  return `${((part / whole) * 100).toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
}

export function formatUtc(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}
