import type { Metadata } from "next";
import Link from "next/link";

import { ArticleCard } from "@/components/library/ArticleCard";
import { FilterBar } from "@/components/library/FilterBar";
import { LoadError } from "@/components/library/LoadError";
import { Pagination } from "@/components/library/Pagination";
import { EmptyState, PageHeader, buttonSecondary } from "@/components/ui";
import { api } from "@/lib/api/client";
import { load } from "@/lib/api/load";
import { PAGE_SIZE, libraryHref, pageCount, parseListState } from "@/lib/library";

export const metadata: Metadata = { title: "Library" };

export default async function LibraryPage({ searchParams }: PageProps<"/library">) {
  const state = parseListState(await searchParams);
  const result = await load(() =>
    api.GET("/api/v1/articles", {
      params: { query: { title: state.title, category: state.category, page: state.page, page_size: PAGE_SIZE } },
    }),
  );

  return (
    <>
      <PageHeader eyebrow="Library" title="Browse the corpus">
        <p>Every Wikipedia article stored in MariaDB, with its source revision, categories, and the exact passages used for retrieval.</p>
      </PageHeader>
      <FilterBar state={state} />
      <div className="mt-6">
        {result.ok ? <Results state={state} page={result.data} /> : <LoadError {...result} retryHref={libraryHref(state)} />}
      </div>
    </>
  );
}

function Results({ state, page }: { state: ReturnType<typeof parseListState>; page: import("@/lib/api/client").Schemas["ArticlePage"] }) {
  const pages = pageCount(page.total, page.page_size);
  const filtered = Boolean(state.title || state.category);

  if (page.total === 0) {
    return (
      <EmptyState
        icon="⌕"
        title={filtered ? "No articles match these filters" : "The corpus is empty"}
        action={filtered ? <Link href="/library" className={buttonSecondary}>Clear filters</Link> : undefined}
      >
        {filtered ? (
          <p>Title matching is a case-insensitive substring; the category must match a category name exactly.</p>
        ) : (
          <p>No articles are loaded in MariaDB yet. Load the snapshot with the corpus loader, then reload this page.</p>
        )}
      </EmptyState>
    );
  }

  if (page.items.length === 0) {
    return (
      <EmptyState icon="◇" title={`Page ${state.page} is past the end`} action={<Link href={libraryHref({ ...state, page: pages })} className={buttonSecondary}>Go to page {pages}</Link>}>
        <p>{page.total} {page.total === 1 ? "article matches" : "articles match"}, across {pages} {pages === 1 ? "page" : "pages"}.</p>
      </EmptyState>
    );
  }

  const start = (page.page - 1) * page.page_size + 1;
  const end = start + page.items.length - 1;
  return (
    <>
      <p className="mb-4 text-sm text-muted" aria-live="polite">
        Showing {start}–{end} of {page.total} {page.total === 1 ? "article" : "articles"}
        {state.title && <> with “{state.title}” in the title</>}
        {state.category && <> in “{state.category}”</>}
        <span className="font-mono text-xs"> · {page.corpus_version}</span>
      </p>
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {page.items.map((article) => (
          <ArticleCard key={article.article_id} article={article} state={state} />
        ))}
      </ul>
      <Pagination page={page.page} pages={pages} label="Library pages" href={(n) => libraryHref({ ...state, page: n })} />
    </>
  );
}
