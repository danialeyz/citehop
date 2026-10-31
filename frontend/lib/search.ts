// Search state lives in the URL, so reloads, back/forward, and returning from Graph restore the
// same query, method, and filters. Only retrieval re-runs from the URL; generation never does.
import type { Schemas } from "@/lib/api/client";
import type { SearchParams } from "@/lib/library";

export type Method = "keyword" | "vector";
export type Filters = { category?: string; min?: number; max?: number; linkedFrom?: number };
export type SearchState = { q: string; method: Method; filters: Filters };

export const METHOD_LABEL: Record<Method, string> = { keyword: "Keyword", vector: "Meaning" };
export const RESULT_COUNT = 5; // The answer route accepts at most five passages.
const MAX_QUERY = 1000;
const MAX_CATEGORY = 255;
const MAX_ARTICLE_ID = 4_294_967_295;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function count(value: string | undefined, max = Number.MAX_SAFE_INTEGER, min = 0): number | undefined {
  if (!value?.trim()) return undefined;
  const n = Number(value);
  return Number.isInteger(n) && n >= min && n <= max ? n : undefined;
}

export function parseFilters(get: (key: string) => string | undefined): Filters {
  const category = get("category")?.trim().slice(0, MAX_CATEGORY) || undefined;
  return { category, min: count(get("min")), max: count(get("max")), linkedFrom: count(get("from"), MAX_ARTICLE_ID, 1) };
}

export function parseSearchState(params: SearchParams): SearchState {
  const get = (key: string) => first(params[key]);
  return {
    q: (get("q") ?? "").trim().slice(0, MAX_QUERY),
    method: get("method") === "keyword" ? "keyword" : "vector",
    filters: parseFilters(get),
  };
}

/** Query string for a search; the default method and empty filters are omitted. */
export function searchQuery(state: SearchState): string {
  const query = new URLSearchParams();
  if (state.q) query.set("q", state.q);
  if (state.method !== "vector") query.set("method", state.method);
  const { category, min, max, linkedFrom } = state.filters;
  if (category) query.set("category", category);
  if (min !== undefined) query.set("min", String(min));
  if (max !== undefined) query.set("max", String(max));
  if (linkedFrom !== undefined) query.set("from", String(linkedFrom));
  return query.toString();
}

export function searchHref(state: SearchState): string {
  const query = searchQuery(state);
  return query ? `/?${query}` : "/";
}

/** Stable identity of a committed search; any change invalidates its answer. */
export function searchKey(state: SearchState): string {
  return searchQuery(state);
}

export function activeFilterCount(filters: Filters): number {
  return Object.values(filters).filter((v) => v !== undefined).length;
}

export function apiFilters(filters: Filters): Schemas["SearchFilters"] {
  return {
    category: filters.category ?? null,
    min_length_chars: filters.min ?? null,
    max_length_chars: filters.max ?? null,
    linked_from: filters.linkedFrom ?? null,
  };
}

export function filterLabels(filters: Filters): string[] {
  const labels: string[] = [];
  if (filters.category) labels.push(`Category: ${filters.category}`);
  if (filters.min !== undefined) labels.push(`≥ ${filters.min.toLocaleString("en")} chars`);
  if (filters.max !== undefined) labels.push(`≤ ${filters.max.toLocaleString("en")} chars`);
  if (filters.linkedFrom !== undefined) labels.push(`Linked from article ${filters.linkedFrom}`);
  return labels;
}

/**
 * Graph deep link: the seed article, the search to return to (whitelisted keys only, re-parsed
 * on arrival), and the retrieved article IDs for highlighting. Never credentials or queries.
 */
export function graphHrefFromSearch(articleId: number, state: SearchState, sourceIds: number[]): string {
  const query = new URLSearchParams({ article: String(articleId) });
  const back = searchQuery(state);
  if (back) query.set("search", back);
  const sources = [...new Set(sourceIds)].slice(0, RESULT_COUNT);
  if (sources.length) query.set("sources", sources.join(","));
  return `/graph?${query}`;
}

export type GraphSearchContext = { search: SearchState; sources: number[] };

export function parseGraphSearchContext(params: SearchParams): GraphSearchContext | null {
  const raw = first(params.search);
  if (!raw) return null;
  const search = parseSearchState(Object.fromEntries(new URLSearchParams(raw)));
  if (!search.q) return null;
  const sources = (first(params.sources) ?? "")
    .split(",")
    .map((id) => count(id, MAX_ARTICLE_ID, 1))
    .filter((id): id is number => id !== undefined)
    .slice(0, RESULT_COUNT);
  return { search, sources };
}

/** Splits answer text into plain strings and citation labels, mirroring citehop.rag.BRACKET. */
export type AnswerPart = { text: string } | { labels: string[]; raw: string };

export function splitCitations(text: string, known: Set<string>): AnswerPart[] {
  const parts: AnswerPart[] = [];
  const bracket = /\[([^[\]\n]{1,40})\]/g;
  let last = 0;
  for (const match of text.matchAll(bracket)) {
    const labels = match[1].split(/[,;]/).map((t) => t.trim().toUpperCase()).filter((t) => known.has(t));
    if (!labels.length) continue;
    if (match.index > last) parts.push({ text: text.slice(last, match.index) });
    parts.push({ labels, raw: match[0] });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last) });
  return parts;
}
