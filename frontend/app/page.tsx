import { Eyebrow } from "@/components/ui";
import { SearchWorkspace } from "@/components/search/SearchWorkspace";
import { loadDevExamples } from "@/lib/examples";
import { parseSearchState, searchKey } from "@/lib/search";

export default async function SearchPage({ searchParams }: PageProps<"/">) {
  const state = parseSearchState(await searchParams);
  const examples = await loadDevExamples();

  return (
    <>
      <section className={`max-w-4xl ${state.q ? "mb-6" : "mb-10"}`}>
        <Eyebrow>Search</Eyebrow>
        <h1 className={`mt-3 font-medium leading-[1.05] tracking-[-0.05em] ${state.q ? "text-3xl sm:text-[38px]" : "text-4xl sm:text-[55px]"}`}>
          Ask a question.
          <br />
          <span className="text-accent">Follow the sources.</span>
        </h1>
        {!state.q && (
          <p className="mt-5 max-w-2xl text-lg text-muted">
            Retrieve passages from 100 Wikipedia machine learning articles, then generate a short answer that cites them.
          </p>
        )}
      </section>

      {/* Keyed by the committed search: a new search, back/forward, or reload starts a fresh
          workspace, so responses for an older search are discarded with it. */}
      <SearchWorkspace key={searchKey(state)} initial={state} examples={examples} />
    </>
  );
}
