"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useTransition, type FormEvent } from "react";

import { Chip, EmptyState, ErrorState, Skeleton, buttonPrimary, buttonSecondary, inputClass } from "@/components/ui";
import { api, isApiError, type Schemas } from "@/lib/api/client";
import type { Example } from "@/lib/examples";
import {
  METHOD_LABEL,
  RESULT_COUNT,
  activeFilterCount,
  apiFilters,
  filterLabels,
  graphHrefFromSearch,
  parseFilters,
  searchHref,
  searchKey,
  type Filters,
  type Method,
  type SearchState,
} from "@/lib/search";

import { AnswerCard, type AnswerState } from "./AnswerCard";
import { answerFailure, searchFailure, type Failure, type Recovery } from "./errors";
import { PassageInspector, type Inspected } from "./PassageInspector";
import { SourceCard } from "./SourceCard";

type SearchResult =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; data: Schemas["SearchResponse"] }
  | { kind: "failed"; failure: Failure };

type FilterDraft = { category: string; min: string; max: string; from: string };

const toDraft = (f: Filters): FilterDraft => ({
  category: f.category ?? "",
  min: f.min?.toString() ?? "",
  max: f.max?.toString() ?? "",
  from: f.linkedFrom?.toString() ?? "",
});

function fromDraft(d: FilterDraft): { filters: Filters; error: string | null } {
  const filters = parseFilters((key) => d[key as keyof FilterDraft]);
  if (d.min.trim() && filters.min === undefined) return { filters, error: "Minimum length must be a whole number of characters." };
  if (d.max.trim() && filters.max === undefined) return { filters, error: "Maximum length must be a whole number of characters." };
  if (d.from.trim() && filters.linkedFrom === undefined) return { filters, error: "Linked from needs a numeric article ID." };
  if (filters.min !== undefined && filters.max !== undefined && filters.min > filters.max) {
    return { filters, error: "Minimum length cannot exceed maximum length." };
  }
  return { filters, error: null };
}

// Answers survive navigation (e.g. Search → Graph → back) without a second generation call. The
// key pins the corpus version, search, and exact chunk IDs, so a cached answer is only reused for
// the identical evidence.
const cacheKey = (search: Schemas["SearchResponse"], key: string, chunkIds: string[]) =>
  `citehop:answer:${JSON.stringify([search.corpus_version, key, chunkIds])}`;

function readCachedAnswer(id: string): Schemas["AnswerResponse"] | null {
  try {
    const raw = sessionStorage.getItem(id);
    return raw ? (JSON.parse(raw) as Schemas["AnswerResponse"]) : null;
  } catch {
    return null;
  }
}

export function SearchWorkspace({ initial, examples }: { initial: SearchState; examples: Example[] | null }) {
  // The parent keys this component by the committed search, so it is fixed for this instance.
  const [committed] = useState(initial);
  const router = useRouter();
  const [navigating, startTransition] = useTransition();
  const committedKey = searchKey(committed);

  const [query, setQuery] = useState(committed.q);
  const [method, setMethod] = useState<Method>(committed.method);
  const [filterDraft, setFilterDraft] = useState<FilterDraft>(toDraft(committed.filters));
  const [formError, setFormError] = useState<string | null>(null);

  const [result, setResult] = useState<SearchResult>(committed.q ? { kind: "loading" } : { kind: "idle" });
  const [attempt, setAttempt] = useState(0);
  const [answer, setAnswer] = useState<AnswerState>({ kind: "idle" });
  const [inspected, setInspected] = useState<Inspected | null>(null);
  // Bumped whenever the current answer becomes invalid; responses carrying an older token are dropped.
  const answerToken = useRef(0);
  const generating = useRef(false);

  const parsed = fromDraft(filterDraft);
  const draftKey = searchKey({ q: query.trim(), method, filters: parsed.filters });
  const dirty = draftKey !== committedKey;

  // Retrieval only. The component is keyed by the committed search, so a new search remounts it;
  // aborting on cleanup means an older response can never replace a newer one.
  useEffect(() => {
    if (!committed.q) return;
    const controller = new AbortController();
    (async () => {
      try {
        const { data, error, response } = await api.POST("/api/v1/search", {
          body: { query: committed.q, method: committed.method, filters: apiFilters(committed.filters), k: RESULT_COUNT },
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!data) return setResult({ kind: "failed", failure: searchFailure(response.status, isApiError(error) ? error : null) });
        setResult({ kind: "ok", data });
        const cached = readCachedAnswer(cacheKey(data, committedKey, data.hits.map((h) => h.chunk_id)));
        if (cached) setAnswer({ kind: "done", data: cached });
      } catch {
        if (!controller.signal.aborted) setResult({ kind: "failed", failure: searchFailure(null, null) });
      }
    })();
    return () => controller.abort();
  }, [committed, committedKey, attempt]);

  const invalidateAnswer = useCallback(() => {
    answerToken.current += 1;
    generating.current = false;
    setAnswer((a) => (a.kind === "idle" ? a : { kind: "idle" }));
    setInspected(null);
  }, []);

  function go(next: SearchState) {
    invalidateAnswer();
    if (searchKey(next) === committedKey) {
      // Same search again (retry): reuse this instance; the effect re-runs on `attempt`.
      setResult({ kind: "loading" });
      setAttempt((n) => n + 1);
    } else startTransition(() => router.push(searchHref(next), { scroll: false }));
  }

  function submit(event?: FormEvent, override?: Partial<SearchState>) {
    event?.preventDefault();
    const q = (override?.q ?? query).trim();
    if (!q) return setFormError("Type a question to search.");
    if (parsed.error) return setFormError(parsed.error);
    setFormError(null);
    go({ q, method: override?.method ?? method, filters: override?.filters ?? parsed.filters });
  }

  function chooseMethod(next: Method) {
    setMethod(next);
    invalidateAnswer();
    if (query.trim() && !parsed.error) submit(undefined, { method: next });
  }

  function editFilter(key: keyof FilterDraft, value: string) {
    setFilterDraft((d) => ({ ...d, [key]: value }));
    invalidateAnswer();
  }

  /** Reruns the committed search with another method, ignoring unsearched form edits. */
  function switchMethod(next: Method) {
    setMethod(next);
    setFormError(null);
    go({ ...committed, method: next });
  }

  function recover(action: Recovery) {
    if (action === "keyword") {
      switchMethod("keyword");
    } else if (action === "clear-filters") {
      setFilterDraft(toDraft({}));
      go({ ...committed, filters: {} });
    } else {
      go(committed);
    }
  }

  function runExample(example: Example) {
    setQuery(example.question);
    setFilterDraft(toDraft(example.filters));
    setFormError(null);
    go({ q: example.question, method, filters: example.filters });
  }

  const hits = result.kind === "ok" ? result.data.hits : [];
  const answerData = answer.kind === "done" ? answer.data : null;

  async function generate() {
    if (result.kind !== "ok" || !hits.length || dirty || generating.current) return;
    generating.current = true;
    const token = ++answerToken.current;
    const search = result.data;
    const chunkIds = hits.slice(0, RESULT_COUNT).map((h) => h.chunk_id);
    setAnswer({ kind: "pending" });
    let next: AnswerState;
    try {
      const { data, error, response } = await api.POST("/api/v1/answer", {
        body: { question: committed.q, chunk_ids: chunkIds, corpus_version: search.corpus_version },
      });
      next = data ? { kind: "done", data } : { kind: "failed", failure: answerFailure(response.status, isApiError(error) ? error : null) };
      if (data && (data.status === "answered" || data.status === "insufficient_evidence")) {
        try {
          sessionStorage.setItem(cacheKey(search, committedKey, chunkIds), JSON.stringify(data));
        } catch {
          // Storage full or disabled: the answer still shows, it just is not restored later.
        }
      }
    } catch {
      next = { kind: "failed", failure: answerFailure(null, null) };
    }
    // The provider call is not cancelled by edits; its late result is simply not shown.
    if (token !== answerToken.current) return;
    generating.current = false;
    setAnswer(next);
  }

  const citedLabel = new Map(Object.entries(answerData?.citation_map ?? {}).map(([label, chunkId]) => [chunkId, label]));
  const graphHref = (articleId: number) => graphHrefFromSearch(articleId, committed, hits.map((h) => h.article_id));

  function inspectCitation(label: string) {
    const source = answerData?.sources.find((s) => s.label === label);
    if (!source) return;
    setInspected({ chunkId: source.chunk_id, articleId: source.article_id, title: source.title, sourceUrl: source.source_url, passage: source.passage, rank: source.rank, label });
  }

  const filterCount = activeFilterCount(parsed.filters);
  const busy = navigating || result.kind === "loading";

  return (
    <>
      <form onSubmit={submit} role="search" aria-label="Search the corpus" className="rounded-[var(--radius-card)] border border-line bg-panel p-4 sm:p-5">
        <label htmlFor="q" className="sr-only">Question</label>
        <div className="flex flex-col gap-3 lg:flex-row">
          <input
            id="q"
            name="q"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              invalidateAnswer();
            }}
            maxLength={1000}
            autoComplete="off"
            placeholder="e.g. Who coined the term machine learning?"
            className={`${inputClass} !py-3 !text-lg`}
          />
          <button type="submit" disabled={busy} className={`${buttonPrimary} shrink-0 whitespace-nowrap !px-6 !py-3 !text-base`}>
            {busy ? "Searching…" : "Find sources"}
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-3">
          <fieldset className="flex items-center gap-2">
            <legend className="sr-only">Search method</legend>
            <span aria-hidden className="text-sm text-muted">Match by</span>
            <div className="inline-flex rounded-[var(--radius-control)] border border-line bg-page p-1">
              {(["keyword", "vector"] as const).map((m) => (
                <label key={m} className="cursor-pointer">
                  <input type="radio" name="method" value={m} checked={method === m} onChange={() => chooseMethod(m)} className="peer sr-only" />
                  <span className="block rounded-[7px] px-3 py-1.5 text-sm text-muted peer-checked:bg-accent-tint peer-checked:font-medium peer-checked:text-accent-soft peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-accent-soft">
                    {METHOD_LABEL[m]}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <p className="text-sm text-muted">
            {method === "keyword" ? "Exact words, MariaDB FULLTEXT." : "Similar meaning, MariaDB native vectors."}
          </p>
        </div>

        {/* Initial state only: `committed` is fixed for this instance, so React never toggles the
            attribute while the user edits filters. */}
        <details open={activeFilterCount(committed.filters) > 0 || undefined} className="group mt-4 border-t border-line pt-3">
          <summary className="cursor-pointer list-none text-sm text-muted hover:text-ink [&::-webkit-details-marker]:hidden">
            <span aria-hidden className="mr-1 inline-block transition-transform group-open:rotate-90">▸</span>
            Filters{filterCount > 0 && <span className="ml-1 text-accent">({filterCount} active)</span>}
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="flex flex-col gap-1 text-sm text-muted">
              Category (exact name)
              <input value={filterDraft.category} onChange={(e) => editFilter("category", e.target.value)} maxLength={255} placeholder="e.g. Cluster analysis algorithms" className={inputClass} />
            </label>
            <label className="flex flex-col gap-1 text-sm text-muted">
              Article length at least (chars)
              <input value={filterDraft.min} onChange={(e) => editFilter("min", e.target.value)} inputMode="numeric" placeholder="e.g. 20000" className={inputClass} />
            </label>
            <label className="flex flex-col gap-1 text-sm text-muted">
              Article length at most (chars)
              <input value={filterDraft.max} onChange={(e) => editFilter("max", e.target.value)} inputMode="numeric" placeholder="e.g. 6000" className={inputClass} />
            </label>
            <label className="flex flex-col gap-1 text-sm text-muted">
              Linked from article ID
              <input value={filterDraft.from} onChange={(e) => editFilter("from", e.target.value)} inputMode="numeric" placeholder="ID from the Library" className={inputClass} />
            </label>
          </div>
          <p className="mt-2 text-xs text-muted">Filters run in SQL before ranking. “Linked from” keeps only articles that the given article links to.</p>
        </details>

        {formError && <p role="alert" className="mt-3 text-sm text-danger">{formError}</p>}
      </form>

      {examples && examples.length > 0 && (
        <details open={!committed.q || undefined} className="mt-4">
          <summary className="cursor-pointer text-sm text-muted hover:text-ink">Sample questions from the dev set</summary>
          <ul className="mt-3 grid gap-2 md:grid-cols-2">
            {examples.map((ex) => (
              <li key={ex.id}>
                <button
                  type="button"
                  onClick={() => runExample(ex)}
                  className="flex h-full w-full flex-col items-start gap-2 rounded-xl border border-line bg-strip p-3 text-left text-[15px] text-ink hover:border-accent"
                >
                  <span className="[overflow-wrap:anywhere]">{ex.question}</span>
                  <span className="flex flex-wrap gap-1.5">
                    <Chip tone={ex.reviewStatus === "approved" ? "accent" : "neutral"}>
                      {ex.reviewStatus === "approved" ? "Reviewed" : "Draft · not yet human-reviewed"}
                    </Chip>
                    {filterLabels(ex.filters).map((l) => <Chip key={l}>{l}</Chip>)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">Clicking a sample retrieves sources only. Some dev questions are deliberately unanswerable from this corpus.</p>
        </details>
      )}

      <div className="mt-8" aria-live="polite" aria-busy={busy}>
        {result.kind === "loading" && <ResultsSkeleton />}

        {result.kind === "failed" && (
          <ErrorState
            title={result.failure.title}
            action={result.failure.recovery.map((r) => (
              <button key={r} type="button" onClick={() => recover(r)} className={buttonSecondary}>
                {{ retry: "Try again", keyword: "Search by keyword instead", "clear-filters": "Clear filters", "search-again": "Search again", wait: "Try again" }[r]}
              </button>
            ))}
          >
            <p>{result.failure.message}</p>
          </ErrorState>
        )}

        {result.kind === "ok" && hits.length === 0 && (
          <EmptyState
            icon="∅"
            title="No passages matched"
            action={
              <>
                {activeFilterCount(committed.filters) > 0 && (
                  <button type="button" onClick={() => recover("clear-filters")} className={buttonSecondary}>Clear filters</button>
                )}
                <button type="button" onClick={() => switchMethod(committed.method === "keyword" ? "vector" : "keyword")} className={buttonSecondary}>
                  Try {METHOD_LABEL[committed.method === "keyword" ? "vector" : "keyword"]} search
                </button>
              </>
            }
          >
            <p>
              {committed.method === "keyword"
                ? "No stored passage contains these words"
                : "No stored passage passed the filters"}
              {activeFilterCount(committed.filters) > 0 ? " with the current filters." : "."} There is nothing to answer from.
            </p>
          </EmptyState>
        )}

        {result.kind === "ok" && hits.length > 0 && (
          <div className="flex flex-col gap-6">
            {dirty && (
              <p role="status" className="rounded-xl border border-amber/30 bg-amber-tint px-4 py-3 text-sm text-amber">
                Showing sources for “{committed.q}”. Your edits are not searched yet: choose Find sources to update them.
              </p>
            )}
            <AnswerCard
              state={answer}
              sourceCount={Math.min(hits.length, RESULT_COUNT)}
              blockedReason={dirty ? "Find sources for your edited search before generating." : null}
              onGenerate={generate}
              onCite={inspectCitation}
              onSearchAgain={() => recover("search-again")}
            />
            <section aria-labelledby="sources-title">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="sources-title" className="text-[17px] font-medium">
                  {hits.length} ranked {hits.length === 1 ? "source" : "sources"}
                  <span className="ml-2 text-sm font-normal text-muted">{METHOD_LABEL[committed.method]} search</span>
                </h2>
                <div className="flex flex-wrap gap-1.5">{filterLabels(committedFilters(result.data.filters)).map((l) => <Chip key={l}>{l}</Chip>)}</div>
              </div>
              <ol className="flex flex-col gap-3">
                {hits.map((hit) => (
                  <SourceCard
                    key={hit.chunk_id}
                    hit={hit}
                    label={citedLabel.get(hit.chunk_id)}
                    graphHref={graphHref(hit.article_id)}
                    onInspect={() => setInspected({ chunkId: hit.chunk_id, articleId: hit.article_id, title: hit.title, sourceUrl: hit.source_url, passage: hit.passage, rank: hit.rank })}
                  />
                ))}
              </ol>
            </section>
            <details className="text-sm text-muted">
              <summary className="cursor-pointer hover:text-ink">Search details</summary>
              <dl className="mt-2 grid gap-x-6 gap-y-1 font-mono text-xs sm:grid-cols-[auto_1fr]">
                <dt>Corpus</dt><dd>{result.data.corpus_version}</dd>
                <dt>Embedding config</dt><dd className="[overflow-wrap:anywhere]">{result.data.embedding_config ?? "none (keyword search)"}</dd>
                <dt>Query embedding</dt><dd>{result.data.timings.embedding_ms === null ? "not used" : `${result.data.timings.embedding_ms.toFixed(1)} ms`}</dd>
                <dt>Retrieval</dt><dd>{result.data.timings.retrieval_ms.toFixed(1)} ms</dd>
                <dt>Total (server)</dt><dd>{result.data.timings.total_ms.toFixed(1)} ms</dd>
              </dl>
            </details>
          </div>
        )}
      </div>

      <PassageInspector item={inspected} graphHref={graphHref} onClose={() => setInspected(null)} />
    </>
  );
}

function committedFilters(f: Schemas["SearchFilters"]): Filters {
  return {
    category: f.category ?? undefined,
    min: f.min_length_chars ?? undefined,
    max: f.max_length_chars ?? undefined,
    linkedFrom: f.linked_from ?? undefined,
  };
}

function ResultsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-label="Loading sources">
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-[var(--radius-card)] border border-line bg-card p-5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="mt-3 h-5 w-2/3" />
          <Skeleton className="mt-3 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-5/6" />
        </div>
      ))}
    </div>
  );
}
