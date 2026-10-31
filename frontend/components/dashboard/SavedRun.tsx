// One saved C08 run and split: provenance, charts, comparison table, grounding review,
// CSV export, and a collapsible configuration panel. Values come from the run's files only.
import type { ReactNode } from "react";

import { LatencyChart, RecallChart } from "@/components/dashboard/RunCharts";
import { Chip, ErrorState, MetaRow, Note, Panel, buttonSecondary } from "@/components/ui";
import { runExportUrl, type Schemas } from "@/lib/api/client";
import type { Loaded } from "@/lib/api/load";
import {
  NOT_MEASURED,
  compareWithLive,
  embeddingLatency,
  formatCount,
  formatMs,
  formatRecall,
  formatUtc,
  generationLatency,
  labelReview,
  latencySamples,
  methodSummaries,
  num,
  obj,
  reviewCounts,
  shortHash,
  str,
  type Latency,
  type MethodSummary,
  type Recall,
} from "@/lib/dashboard";

type Manifest = Schemas["RunManifest"];

export function SavedRun({ manifest, split, detail, corpus }: {
  manifest: Manifest;
  split: string;
  detail: Loaded<Schemas["RunDetail"]>;
  corpus: Schemas["CorpusStats"] | null;
}) {
  if (!detail.ok) {
    return (
      <ErrorState title={detail.error?.error === "malformed_run" ? "This saved run is malformed" : "This saved run could not be loaded"}>
        <p>{detail.status === null ? "The CiteHop API is unreachable." : (detail.error?.message ?? `The API answered with HTTP ${detail.status}.`)}</p>
        <p className="mt-2 text-sm">Nothing from this run is charted, so no partial numbers are shown.</p>
      </ErrorState>
    );
  }

  const methods = methodSummaries(manifest, split);
  const measured = methods.some((m) => m.recall.value !== null || m.latency.median !== null);

  return (
    <div className="flex flex-col gap-6">
      <Provenance manifest={manifest} split={split} corpus={corpus} />
      {methods.length === 0 || !measured ? (
        <ErrorState title={`No retrieval summary for the ${split} split`}>
          <p>The run&apos;s manifest has no Recall@5 or latency values for this split. Re-summarize the run with the C08 evaluator; nothing is charted until then.</p>
        </ErrorState>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel><RecallChart methods={methods} /></Panel>
            <Panel><LatencyChart methods={methods} /></Panel>
          </div>
          <ComparisonTable manifest={manifest} split={split} methods={methods} />
        </>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ReviewPanel manifest={manifest} split={split} answers={detail.data.answers} />
        <Panel>
          <h3 className="mb-2 text-[17px] font-medium">Download the evidence</h3>
          <p className="mb-4 text-sm text-muted">
            One CSV row per question, repetition, and method across all splits ({formatCount(detail.data.counts.rows)} rows from{" "}
            {formatCount(detail.data.counts.records)} retrieval records). Empty cells are values the run did not record.
          </p>
          <a href={runExportUrl(manifest.run_id)} download={`${manifest.run_id}.csv`} className={buttonSecondary}>
            Download CSV<span className="sr-only"> for run {manifest.run_id}</span>
          </a>
        </Panel>
      </div>
      <RunDetails manifest={manifest} split={split} corpus={corpus} />
    </div>
  );
}

function Provenance({ manifest, split, corpus }: { manifest: Manifest; split: string; corpus: Schemas["CorpusStats"] | null }) {
  const compatibility = compareWithLive(manifest, corpus);
  return (
    <div className="flex flex-col gap-3">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
        <span>Measured <time dateTime={manifest.created_at}>{formatUtc(manifest.created_at)}</time></span>
        <span aria-hidden>·</span>
        <span>split <strong className="font-medium text-ink">{split}</strong>, {formatCount(manifest.splits[split])} questions</span>
        <span aria-hidden>·</span>
        <span className="font-mono">{manifest.corpus.id}</span>
        {manifest.config_id && <><span aria-hidden>·</span><span className="font-mono" title={manifest.config_id}>config {shortHash(manifest.config_id)}</span></>}
      </p>
      {manifest.final_claims_allowed !== true && (
        <div role="note" className="rounded-[var(--radius-control)] border border-amber/40 bg-amber-tint px-4 py-3 text-sm text-amber">
          <strong className="font-medium">Provisional run.</strong>{" "}
          {(manifest.status ?? "This run does not allow final claims").replace(/\.?$/, ".")} These are harness results, not final findings.
        </div>
      )}
      {compatibility.kind === "mismatch" && (
        <div role="alert" className="rounded-[var(--radius-control)] border border-danger/40 bg-danger-tint px-4 py-3 text-sm text-ink">
          <strong className="font-medium text-danger">This run does not describe the live corpus.</strong>
          <ul className="mt-1 list-disc pl-5">{compatibility.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="mt-1">Its numbers are shown as recorded; re-run the evaluation before comparing them with the live counts above.</p>
        </div>
      )}
      {compatibility.kind === "unknown" && (
        <Note>Live corpus counts are unavailable, so this run could not be checked against the current corpus version.</Note>
      )}
    </div>
  );
}

function recallCell(r: Recall) {
  return r.value === null ? <span className="text-muted">{NOT_MEASURED}</span> : <>{formatRecall(r.value)} <span className="text-muted">(n={r.n ?? "?"})</span></>;
}

function latencyCell(l: Latency) {
  if (l.median === null && l.p95 === null) return <span className="text-muted">{NOT_MEASURED}</span>;
  return <>{formatMs(l.median)} / {formatMs(l.p95)} <span className="text-muted">(n={l.n ?? "?"})</span></>;
}

const th = "px-3 py-2.5 text-left text-xs font-medium uppercase tracking-[0.08em] text-muted";
const td = "px-3 py-2.5 align-top font-mono text-[13px] whitespace-nowrap";

function ComparisonTable({ manifest, split, methods }: { manifest: Manifest; split: string; methods: MethodSummary[] }) {
  const embedding = embeddingLatency(manifest, split);
  const generation = generationLatency(manifest);
  const samples = latencySamples(manifest, split);
  return (
    <Panel>
      <h3 className="mb-1 text-[17px] font-medium">Comparison table</h3>
      <p className="mb-4 text-sm text-muted">
        Recall@5 is article-level over answerable questions only (n = questions). Latency is median / nearest-rank p95 in milliseconds
        over every timed call (n = calls, repetitions included{samples.questions !== null && samples.records !== null ? `: ${samples.records} records for ${samples.questions} questions` : ""}).
        Scores are not compared across methods.
      </p>
      <div className="flex flex-col gap-6">
        <MethodTable title="Recall@5" context={`run ${manifest.run_id}, ${split} split`} methods={methods} columns={[
          ["Recall@5", (m) => recallCell(m.recall)],
          ["Unfiltered", (m) => recallCell(m.recallUnfiltered)],
          ["Filtered", (m) => recallCell(m.recallFiltered)],
          ["Unanswerable", (m) => m.unanswerable === null ? <span className="text-muted">{NOT_MEASURED}</span> : `${m.unanswerable} excluded`],
        ]} />
        <MethodTable title="Retrieval latency" context={`run ${manifest.run_id}, ${split} split`} methods={methods} columns={[
          ["All median / p95", (m) => latencyCell(m.latency)],
          ["Unfiltered", (m) => latencyCell(m.latencyUnfiltered)],
          ["Filtered", (m) => latencyCell(m.latencyFiltered)],
        ]} />
      </div>
      <h4 className="mt-6 mb-2 text-sm font-medium">Separately timed stages</h4>
      <dl className="max-w-2xl">
        <MetaRow label={`Query embedding, ${split} (vector methods only)`}><span className="font-mono">{latencyCell(embedding)}</span></MetaRow>
        <MetaRow label="Answer generation (all generated answers in the run)"><span className="font-mono">{latencyCell(generation)}</span></MetaRow>
      </dl>
    </Panel>
  );
}

function MethodTable({ title, context, methods, columns }: {
  title: string; context: string; methods: MethodSummary[]; columns: [string, (m: MethodSummary) => ReactNode][];
}) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-control)] border border-line">
      <table className="w-full border-collapse text-sm">
        <caption className="px-3 pt-2.5 text-left text-sm font-medium text-ink">{title}<span className="sr-only"> for {context}</span></caption>
        <thead>
          <tr>
            <th scope="col" className={th}>Method</th>
            {columns.map(([label]) => <th key={label} scope="col" className={th}>{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {methods.map((m) => (
            <tr key={m.method} className="border-t border-line">
              <th scope="row" className="px-3 py-2.5 text-left align-top font-medium whitespace-nowrap">{m.label}</th>
              {columns.map(([label, cell]) => <td key={label} className={td}>{cell(m)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Count({ label, children }: { label: string; children: ReactNode }) {
  return <MetaRow label={label}><span className="font-mono">{children}</span></MetaRow>;
}

function ReviewPanel({ manifest, split, answers }: { manifest: Manifest; split: string; answers: Schemas["RunAnswer"][] }) {
  const c = reviewCounts(answers, split);
  const labels = labelReview(manifest);
  const labelTotal = labels ? Object.values(labels).reduce((a, b) => a + b, 0) : 0;
  return (
    <Panel>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[17px] font-medium">Grounding review</h3>
        {c.prepared > 0 && <Chip tone={c.reviewed === c.prepared ? "accent" : "neutral"}>{c.reviewed} of {c.prepared} reviewed</Chip>}
      </div>
      {c.prepared === 0 ? (
        <p className="text-sm text-muted">No answers were generated for the {split} split in this run, so there is nothing to review here.</p>
      ) : (
        <>
          <p className="mb-2 text-sm text-muted">Human review of saved answers. A valid citation label does not prove the passage supports the claim.</p>
          <dl>
            <Count label="Answers prepared">{c.prepared} ({c.answered} answered, {c.abstained} abstained{c.otherStatus ? `, ${c.otherStatus} other` : ""})</Count>
            <Count label="Reviewed">{c.reviewed} of {c.prepared}{c.reviewed ? ` (${c.approved} approved, ${c.needsChanges} need changes)` : ""}</Count>
            <Count label="Grounded">{c.grounded.denominator ? `${c.grounded.yes} of ${c.grounded.denominator} reviewed answers` : "Not reviewed"}</Count>
            <Count label="Correct abstentions">{c.abstentions.denominator ? `${c.abstentions.correct} of ${c.abstentions.denominator} reviewed unanswerable` : "Not reviewed"}</Count>
          </dl>
        </>
      )}
      <p className="mt-4 text-xs text-muted">
        Question labels:{" "}
        {labels && labelTotal
          ? Object.entries(labels).map(([status, n]) => `${n} of ${labelTotal} ${status}`).join(", ")
          : "Not reported"}
        {manifest.final_claims_allowed === true ? " · final claims allowed" : " · final claims not allowed"}
      </p>
    </Panel>
  );
}

function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="text-muted">Not recorded</span>;
  if (typeof value === "boolean") return <>{value ? "yes" : "no"}</>;
  if (Array.isArray(value)) return <>{value.map(String).join(", ")}</>;
  const o = obj(value);
  if (o) return <>{Object.entries(o).map(([k, v]) => `${k} ${String(v)}`).join(" · ")}</>;
  const s = String(value);
  return <span title={s}>{/^[0-9a-f]{40,64}$/.test(s) ? shortHash(s) : s}</span>;
}

function DetailGroup({ title, rows }: { title: string; rows: [string, unknown][] }) {
  return (
    <div className="min-w-0">
      <h4 className="mb-1 text-sm font-medium text-accent-soft">{title}</h4>
      <dl>
        {rows.map(([label, value]) => (
          <MetaRow key={label} label={label}><span className="font-mono text-[13px]"><Value value={value} /></span></MetaRow>
        ))}
      </dl>
    </div>
  );
}

function RunDetails({ manifest, split, corpus }: { manifest: Manifest; split: string; corpus: Schemas["CorpusStats"] | null }) {
  const config = obj(manifest.config) ?? {};
  const mariadb = obj(config.mariadb) ?? {};
  const latency = obj(manifest.latency) ?? {};
  const boundaries = obj(latency.boundaries) ?? {};
  const hardware = obj(manifest.hardware) ?? {};
  const code = obj(manifest.code) ?? {};
  const chunkConfigs = Array.isArray(manifest.chunk_configs) ? manifest.chunk_configs.map(obj).filter((c) => c !== null) : [];
  const liveTokens = corpus?.embedding_configs.find((c) => chunkConfigs.some((r) => r.chunk_config === c.chunk_config));
  const methods = obj(config.methods)?.[split];

  return (
    <details className="group rounded-[var(--radius-card)] border border-line bg-panel">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-[var(--radius-card)] p-5 sm:px-6">
        <span>
          <span className="block text-[17px] font-medium">Model, chunk, index, and timing details</span>
          <span className="block text-sm text-muted">Exactly as saved in this run&apos;s manifest.</span>
        </span>
        <span aria-hidden className="text-muted transition-transform group-open:rotate-90">›</span>
      </summary>
      <div className="grid gap-x-10 gap-y-6 border-t border-line p-5 sm:px-6 lg:grid-cols-2">
        <DetailGroup title="Embedding model" rows={[
          ["Model", config.embedding_model],
          ["Revision", config.embedding_model_revision],
          ["Embedding config", config.embedding_config],
        ]} />
        <DetailGroup title="Chunks" rows={[
          ...chunkConfigs.flatMap((c, i): [string, unknown][] => [
            [`Chunk config${chunkConfigs.length > 1 ? ` ${i + 1}` : ""}`, c.chunk_config],
            ["Chunks evaluated", num(c.chunks)],
          ]),
          ["Token range (live, same config)", liveTokens ? `${liveTokens.token_count_min ?? "?"}–${liveTokens.token_count_max ?? "?"} tokens` : null],
        ]} />
        <DetailGroup title="Retrieval and index" rows={[
          ["k", config.k],
          ["Recall definition", config.recall],
          [`Methods (${split})`, methods],
          ["Candidate depths", config.candidate_depths],
          ["MariaDB", mariadb.version],
          ["mhnsw_ef_search", mariadb.mhnsw_ef_search],
          ["mhnsw_default_m", mariadb.mhnsw_default_m],
        ]} />
        <DetailGroup title="Generation" rows={[
          ["Generator", config.generator],
          ["Prompt version", config.prompt_version],
          ["Limits", config.rag_limits],
          ["Answer passages", config.answer_passages],
        ]} />
        <DetailGroup title="Timing" rows={[
          ["Unit", latency.unit],
          ["Statistics", latency.statistics],
          ["Embedding boundary", boundaries.embedding_ms],
          ["Retrieval boundary", boundaries.retrieval_ms],
          ["Generation boundary", boundaries.generation_ms],
          ["Warm-up", manifest.warm_up],
        ]} />
        <DetailGroup title="Environment" rows={[
          ["CPU", hardware.cpu],
          ["Memory", num(hardware.memory_bytes) === null ? null : `${((hardware.memory_bytes as number) / 2 ** 30).toFixed(0)} GiB`],
          ["Platform", hardware.platform],
          ["Database", hardware.database],
          ["Code commit", str(code.commit)],
          ["Uncommitted changes", code.dirty],
          ["Run ID", manifest.run_id],
        ]} />
      </div>
    </details>
  );
}
