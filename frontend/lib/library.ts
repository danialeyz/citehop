// Library list state lives in the URL, so reloads, back/forward, and returning from an
// article detail page all restore the same filters and page.
export const PAGE_SIZE = 20;
export const PASSAGE_PAGE_SIZE = 10;
const MAX_TITLE = 200; // citehop.library.MAX_TITLE_FILTER_CHARS
const MAX_CATEGORY = 255;
const MAX_PAGE = 10_000;

export type SearchParams = Record<string, string | string[] | undefined>;
export type ListState = { title?: string; category?: string; page: number };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function text(value: string | string[] | undefined, max: number): string | undefined {
  const trimmed = first(value)?.trim();
  return trimmed ? trimmed.slice(0, max) : undefined;
}

export function pageNumber(value: string | string[] | undefined): number {
  const n = Number(first(value));
  return Number.isInteger(n) && n >= 1 ? Math.min(n, MAX_PAGE) : 1;
}

export function parseListState(params: SearchParams): ListState {
  return { title: text(params.title, MAX_TITLE), category: text(params.category, MAX_CATEGORY), page: pageNumber(params.page) };
}

/** Query string for a list state; page 1 and empty filters are omitted. */
export function listQuery(state: ListState): string {
  const query = new URLSearchParams();
  if (state.title) query.set("title", state.title);
  if (state.category) query.set("category", state.category);
  if (state.page > 1) query.set("page", String(state.page));
  return query.toString();
}

export function libraryHref(state: ListState): string {
  const query = listQuery(state);
  return query ? `/library?${query}` : "/library";
}

/** Changing a filter always returns to page 1. */
export function withFilters(state: ListState, filters: Pick<ListState, "title" | "category">): ListState {
  return { ...filters, page: 1 };
}

/** Detail links carry the list state in `back`, so "Back to Library" restores it exactly. */
export function articleHref(articleId: number, state?: ListState, passagePage = 1): string {
  const query = new URLSearchParams();
  const back = state ? listQuery(state) : "";
  if (back) query.set("back", back);
  if (passagePage > 1) query.set("pp", String(passagePage));
  const qs = query.toString();
  return qs ? `/library/${articleId}?${qs}` : `/library/${articleId}`;
}

/** Only known list keys are read back, so `back` cannot redirect elsewhere. */
export function parseBack(value: string | string[] | undefined): ListState {
  return parseListState(Object.fromEntries(new URLSearchParams(first(value) ?? "")));
}

export function graphHref(articleId: number): string {
  return `/graph?article=${articleId}`;
}

export function pageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}
