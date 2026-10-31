import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { LoadError } from "@/components/library/LoadError";
import { Pagination } from "@/components/library/Pagination";
import { CategoryLink, Chip, EmptyState, Eyebrow, MetaRow, Panel, buttonPrimary, buttonSecondary } from "@/components/ui";
import { api, type Schemas } from "@/lib/api/client";
import { load } from "@/lib/api/load";
import { PASSAGE_PAGE_SIZE, articleHref, graphHref, libraryHref, pageCount, pageNumber, parseBack } from "@/lib/library";

const MAX_ARTICLE_ID = 4_294_967_295;

function articleId(raw: string): number | null {
  const n = Number(raw);
  return /^\d+$/.test(raw) && n >= 1 && n <= MAX_ARTICLE_ID ? n : null;
}

export async function generateMetadata({ params }: PageProps<"/library/[id]">): Promise<Metadata> {
  const id = articleId((await params).id);
  if (id === null) return { title: "Article" };
  const result = await load(() => api.GET("/api/v1/articles/{article_id}", { params: { path: { article_id: id }, query: { passage_page_size: 1 } } }));
  return { title: result.ok ? result.data.title : "Article" };
}

export default async function ArticlePage({ params, searchParams }: PageProps<"/library/[id]">) {
  const id = articleId((await params).id);
  if (id === null) notFound();
  const query = await searchParams;
  const back = parseBack(query.back);
  const passagePage = pageNumber(query.pp);

  const result = await load(() =>
    api.GET("/api/v1/articles/{article_id}", {
      params: { path: { article_id: id }, query: { passage_page: passagePage, passage_page_size: PASSAGE_PAGE_SIZE } },
    }),
  );
  if (!result.ok && result.status === 404) notFound();

  return (
    <>
      <Link href={libraryHref(back)} className="mb-6 inline-flex rounded-sm text-sm text-muted hover:text-accent-soft">
        ← Back to Library
      </Link>
      {result.ok ? (
        <Detail article={result.data} back={back} passagePage={passagePage} />
      ) : (
        <LoadError {...result} retryHref={articleHref(id, back, passagePage)} />
      )}
    </>
  );
}

function Detail({ article, back, passagePage }: { article: Schemas["ArticleDetail"]; back: ReturnType<typeof parseBack>; passagePage: number }) {
  const passages = article.passages;
  const pages = pageCount(passages.total, passages.page_size);
  return (
    <>
      <header className="mb-8 max-w-4xl">
        <Eyebrow>Wikipedia article · {article.corpus_version}</Eyebrow>
        <h1 className="mt-2 text-3xl font-medium tracking-[-0.04em] [overflow-wrap:anywhere] sm:text-[38px] sm:leading-tight">{article.title}</h1>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href={graphHref(article.article_id)} className={buttonPrimary}>Explore connections</Link>
          <a href={article.source_url} target="_blank" rel="noopener noreferrer" className={buttonSecondary}>
            Read on Wikipedia ↗<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* First in DOM and focus order; the right-hand column on desktop. */}
        <aside className="flex min-w-0 flex-col gap-6 lg:col-start-2 lg:row-start-1" aria-label="Source details">
          <Panel>
            <h2 className="mb-2 text-[17px] font-medium">Source</h2>
            <dl>
              <MetaRow label="Article ID"><span className="font-mono">{article.article_id}</span></MetaRow>
              <MetaRow label="Revision">
                <a href={article.revision_url} target="_blank" rel="noopener noreferrer" className="font-mono text-accent hover:text-accent-soft">
                  {article.revision_id} ↗<span className="sr-only"> (opens in a new tab)</span>
                </a>
              </MetaRow>
              <MetaRow label="Revision time">{article.revision_timestamp ? <time dateTime={article.revision_timestamp}>{formatUtc(article.revision_timestamp)}</time> : "Not recorded"}</MetaRow>
              <MetaRow label="Length"><span className="font-mono">{article.length_chars.toLocaleString("en-US")} chars</span></MetaRow>
              <MetaRow label="Article links">
                <span className="font-mono">{article.links.outgoing} out · {article.links.incoming} in</span>
              </MetaRow>
              {article.is_smoke && <MetaRow label="Subset"><Chip tone="accent">Smoke subset</Chip></MetaRow>}
            </dl>
            <p className="mt-4 text-xs text-muted">
              {article.attribution}.{" "}
              <a href={article.license_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-soft">
                CC BY-SA 4.0<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </p>
          </Panel>
          <Panel>
            <h2 className="mb-1 text-[17px] font-medium">Categories</h2>
            <p className="mb-3 text-xs text-muted">Select one to list every article in it.</p>
            {article.categories.length ? (
              <ul className="flex flex-wrap gap-1.5">
                {article.categories.map((name) => <li key={name} className="max-w-full"><CategoryLink name={name} /></li>)}
              </ul>
            ) : (
              <p className="text-sm text-muted">No categories recorded.</p>
            )}
          </Panel>
        </aside>

        <section aria-labelledby="passages-heading" className="min-w-0 lg:col-start-1 lg:row-start-1">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="passages-heading" className="text-[22px] font-medium tracking-[-0.03em]">Stored passages</h2>
            <p className="font-mono text-xs text-muted">{passages.total} {passages.total === 1 ? "passage" : "passages"}</p>
          </div>
          <PassageList passages={passages} passagePage={passagePage} pages={pages} articleId={article.article_id} back={back} />
        </section>
      </div>
    </>
  );
}

function PassageList({ passages, passagePage, pages, articleId, back }: {
  passages: Schemas["PassagePage"]; passagePage: number; pages: number; articleId: number; back: ReturnType<typeof parseBack>;
}) {
  if (passages.total === 0) {
    return (
      <EmptyState icon="◇" title="No stored passages">
        <p>This article has not been chunked under the current configuration yet. Its metadata is loaded, but there is no passage text to show or retrieve.</p>
      </EmptyState>
    );
  }
  if (passages.items.length === 0) {
    return (
      <EmptyState icon="◇" title={`Passage page ${passagePage} is past the end`} action={<Link href={articleHref(articleId, back, pages)} className={buttonSecondary}>Go to page {pages}</Link>}>
        <p>This article has {passages.total} stored passages.</p>
      </EmptyState>
    );
  }
  return (
    <>
      <ol className="flex flex-col gap-4">
        {passages.items.map((passage) => (
          <li key={passage.chunk_id} id={`passage-${passage.ordinal}`} className="rounded-[var(--radius-card)] border border-line bg-card p-5">
            <p className="mb-3 flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs text-muted">
              <span className="text-accent">#{passage.ordinal + 1}</span>
              <span>chars {passage.char_start.toLocaleString("en-US")}–{passage.char_end.toLocaleString("en-US")}</span>
              <span>{passage.token_count} tokens</span>
              <span title={passage.chunk_id}>chunk {passage.chunk_id.slice(0, 12)}…</span>
            </p>
            <p className="whitespace-pre-line text-[15px] leading-relaxed text-ink/90 [overflow-wrap:anywhere]">{passage.text}</p>
          </li>
        ))}
      </ol>
      <Pagination page={passagePage} pages={pages} label="Passage pages" href={(n) => articleHref(articleId, back, n)} />
      {passages.chunk_config && (
        <p className="mt-4 font-mono text-[11px] text-muted [overflow-wrap:anywhere]">
          chunk config {passages.chunk_config.slice(0, 12)}… · embedding config {passages.embedding_config ? `${passages.embedding_config.slice(0, 12)}…` : "none"}
        </p>
      )}
    </>
  );
}

function formatUtc(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}
