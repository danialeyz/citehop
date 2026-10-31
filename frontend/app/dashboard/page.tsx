import type { Metadata } from "next";
import type { ReactNode } from "react";

import { CorpusCards, GraphPanel } from "@/components/dashboard/LiveSnapshot";
import { RunPicker } from "@/components/dashboard/RunPicker";
import { SavedRun } from "@/components/dashboard/SavedRun";
import { LoadError } from "@/components/library/LoadError";
import { EmptyState, Eyebrow, Note, PageHeader } from "@/components/ui";
import { api } from "@/lib/api/client";
import { load } from "@/lib/api/load";
import { dashboardHref, formatUtc, parseDashboardState, selectRun, selectSplit } from "@/lib/dashboard";

export const metadata: Metadata = { title: "Dashboard" };

// Read-only: four GETs against saved files and live counts. Nothing here embeds, retrieves,
// generates, or benchmarks; evaluation runs only through `make eval`.
export default async function DashboardPage({ searchParams }: PageProps<"/dashboard">) {
  const state = parseDashboardState(await searchParams);
  const [stats, graph, runs] = await Promise.all([
    load(() => api.GET("/api/v1/stats")),
    load(() => api.GET("/api/v1/graph/status")),
    load(() => api.GET("/api/v1/runs")),
  ]);
  const readAt = new Date().toISOString();

  const manifest = runs.ok ? selectRun(runs.data.runs, state.run) : null;
  const split = manifest ? selectSplit(manifest, state.split) : null;
  const detail = manifest
    ? await load(() => api.GET("/api/v1/runs/{run_id}", { params: { path: { run_id: manifest.run_id } } }))
    : null;

  return (
    <>
      <PageHeader eyebrow="Dashboard" title="Corpus and evaluation">
        <p>What is loaded right now, and what one saved evaluation run measured. The two are kept apart.</p>
      </PageHeader>

      <Section
        id="live"
        eyebrow="Live snapshot"
        title="Corpus and graph right now"
        aside={<>Read from MariaDB and Neo4j at <time dateTime={readAt}>{formatUtc(readAt)}</time></>}
      >
        <CorpusCards stats={stats} retryHref={dashboardHref(state)} />
        <div className="mt-6"><GraphPanel graph={graph} retryHref={dashboardHref(state)} /></div>
      </Section>

      <Section
        id="saved"
        eyebrow="Saved evaluation"
        title="Retrieval and grounding run"
        aside="Recorded by make eval; not recomputed on this page"
      >
        {!runs.ok ? (
          <LoadError {...runs} subject="Saved runs" retryHref={dashboardHref(state)} />
        ) : (
          <div className="flex flex-col gap-6">
            {runs.data.invalid.length > 0 && (
              <div role="alert" className="rounded-[var(--radius-control)] border border-danger/40 bg-danger-tint px-4 py-3 text-sm">
                <strong className="font-medium text-danger">
                  {runs.data.invalid.length} saved {runs.data.invalid.length === 1 ? "run is" : "runs are"} malformed and hidden:
                </strong>
                <ul className="mt-1 list-disc pl-5 text-ink/85">
                  {runs.data.invalid.map((r) => <li key={r.run_id} className="[overflow-wrap:anywhere]"><span className="font-mono">{r.run_id}</span>: {r.error}</li>)}
                </ul>
              </div>
            )}
            {manifest && split && detail ? (
              <>
                {state.run && state.run !== manifest.run_id && (
                  <Note>Run “{state.run}” was not found; showing the newest saved run instead.</Note>
                )}
                <RunPicker
                  runs={runs.data.runs.map((r) => ({ runId: r.run_id, label: `${formatUtc(r.created_at)} · ${r.corpus.id} · ${r.run_id}` }))}
                  run={manifest.run_id}
                  splits={manifest.splits}
                  split={split}
                />
                <SavedRun key={`${manifest.run_id}/${split}`} manifest={manifest} split={split} detail={detail} corpus={stats.ok ? stats.data.corpus : null} />
              </>
            ) : (
              <EmptyState icon="▥" title="No saved evaluation runs">
                <p>
                  Run <code className="font-mono text-ink">make eval</code> to write one under <code className="font-mono text-ink">results/runs/</code>.
                  The dashboard only reads saved runs; it never starts a benchmark or calls a model.
                </p>
              </EmptyState>
            )}
          </div>
        )}
      </Section>
    </>
  );
}

function Section({ id, eyebrow, title, aside, children }: { id: string; eyebrow: string; title: string; aside: ReactNode; children: ReactNode }) {
  return (
    <section aria-labelledby={`${id}-heading`} className="mb-12">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-1 border-b border-line pb-3">
        <div>
          <Eyebrow>{eyebrow}</Eyebrow>
          <h2 id={`${id}-heading`} className="mt-1 text-[22px] font-medium tracking-[-0.03em]">{title}</h2>
        </div>
        <p className="text-xs text-muted">{aside}</p>
      </div>
      {children}
    </section>
  );
}
