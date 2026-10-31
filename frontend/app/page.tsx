import { ResearchIntro, ExploreMore } from "@/components/search/ResearchIntro";
import { SearchWorkspace } from "@/components/search/SearchWorkspace";
import { loadDevExamples } from "@/lib/examples";
import { parseSearchState, searchKey } from "@/lib/search";

export default async function SearchPage({ searchParams }: PageProps<"/">) {
  const state = parseSearchState(await searchParams);
  const examples = await loadDevExamples();

  return (
    <>
      <ResearchIntro compact={Boolean(state.q)} />

      {/* Keyed by the committed search: a new search, back/forward, or reload starts a fresh
          workspace, so responses for an older search are discarded with it. */}
      <SearchWorkspace key={searchKey(state)} initial={state} examples={examples} />
      {!state.q && <ExploreMore />}
    </>
  );
}
