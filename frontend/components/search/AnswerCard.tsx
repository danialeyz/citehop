import { Chip, Skeleton, buttonPrimary, buttonSecondary } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";
import { splitCitations } from "@/lib/search";

import type { Failure } from "./errors";

export type AnswerState =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "done"; data: Schemas["AnswerResponse"] }
  | { kind: "failed"; failure: Failure };

const STATUS: Record<Schemas["AnswerResponse"]["status"], { title: string; tone: "accent" | "neutral" }> = {
  answered: { title: "Answered with citations", tone: "accent" },
  insufficient_evidence: { title: "Not enough evidence", tone: "neutral" },
  invalid_citations: { title: "Answer withheld", tone: "neutral" },
  provider_error: { title: "Generator unavailable", tone: "neutral" },
};

const DETAIL: Record<Exclude<Schemas["AnswerResponse"]["status"], "answered">, string> = {
  insufficient_evidence: "The retrieved passages do not contain enough to answer this question, so no answer is given. Try other words, Keyword search, or fewer filters.",
  invalid_citations: "The generated text cited passages that were not provided, so it is not shown.",
  provider_error: "The answer generator did not respond. The sources below are still valid; you can try again.",
};

export function AnswerCard({
  state,
  sourceCount,
  blockedReason,
  onGenerate,
  onCite,
  onSearchAgain,
}: {
  state: AnswerState;
  sourceCount: number;
  /** Why generation is unavailable right now, e.g. the query was edited after searching. */
  blockedReason: string | null;
  onGenerate: () => void;
  onCite: (label: string) => void;
  onSearchAgain: () => void;
}) {
  const pending = state.kind === "pending";
  const data = state.kind === "done" ? state.data : null;
  const regenerate = data ? data.status !== "answered" && data.status !== "insufficient_evidence" : state.kind === "failed";
  const showButton = state.kind === "idle" || pending || regenerate;
  const label = pending ? "Generating…" : regenerate ? "Try again" : "Generate answer";

  return (
    <section aria-labelledby="answer-title" aria-busy={pending} className="rounded-[var(--radius-card)] border border-accent/40 bg-panel p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="answer-title" className="text-[17px] font-medium">Answer</h2>
        {data && <Chip tone={STATUS[data.status].tone}>{STATUS[data.status].title}</Chip>}
      </div>

      <div aria-live="polite" className="mt-3">
        {state.kind === "idle" && (
          <p className="text-muted">
            Generate a short answer that cites only the top {sourceCount} {sourceCount === 1 ? "passage" : "passages"} below. Nothing is generated until you ask.
          </p>
        )}
        {pending && (
          <div className="flex flex-col gap-2" aria-label="Generating answer">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-11/12" />
            <Skeleton className="h-4 w-2/3" />
            <p className="mt-1 text-sm text-muted">Generating with the local model. This can take a little while.</p>
          </div>
        )}
        {state.kind === "failed" && (
          <div role="alert">
            <p className="font-medium text-danger">{state.failure.title}</p>
            <p className="mt-1 text-sm text-ink/85">{state.failure.message}</p>
          </div>
        )}
        {data?.status === "answered" && data.text && <AnswerText text={data.text} labels={data.citations} onCite={onCite} />}
        {data && data.status !== "answered" && (
          <div>
            <p className="text-ink/90">{DETAIL[data.status]}</p>
            {data.reason && <p className="mt-1 font-mono text-xs text-muted [overflow-wrap:anywhere]">Reason: {data.reason}</p>}
          </div>
        )}
      </div>

      {data?.status === "answered" && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4 text-sm">
          <span className="text-muted">Cited passages:</span>
          {data.citations.map((l) => (
            <button key={l} type="button" onClick={() => onCite(l)} className="rounded-[var(--radius-chip)] border border-accent/40 bg-accent-tint px-2 py-0.5 font-mono text-xs text-accent-soft hover:border-accent">
              {l}
            </button>
          ))}
        </div>
      )}
      {data && (
        <p className="mt-3 font-mono text-[11px] text-muted [overflow-wrap:anywhere]">
          {[
            data.model && `model ${data.model}`,
            data.generation_ms !== null && `${Math.round(data.generation_ms).toLocaleString("en")} ms generation`,
            `prompt ${data.prompt_version}`,
            data.truncated && "stopped at the output limit",
            data.omitted.length > 0 && `${data.omitted.length} passage(s) omitted to fit the context budget`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}

      {(showButton || blockedReason) && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {showButton && (
            <button type="button" onClick={onGenerate} disabled={pending || Boolean(blockedReason) || sourceCount === 0} className={buttonPrimary}>
              {label}
            </button>
          )}
          {state.kind === "failed" && state.failure.recovery.includes("search-again") && (
            <button type="button" onClick={onSearchAgain} className={buttonSecondary}>Search again</button>
          )}
          {blockedReason && <p className="text-sm text-muted">{blockedReason}</p>}
        </div>
      )}
    </section>
  );
}

/** Plain-text answer; citation labels become buttons. Never rendered as HTML. */
function AnswerText({ text, labels, onCite }: { text: string; labels: string[]; onCite: (label: string) => void }) {
  return (
    <p className="whitespace-pre-line text-[17px] leading-relaxed text-ink [overflow-wrap:anywhere]">
      {splitCitations(text, new Set(labels)).map((part, i) =>
        "text" in part ? (
          <span key={i}>{part.text}</span>
        ) : (
          <span key={i} className="whitespace-nowrap">
            {part.labels.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => onCite(l)}
                aria-label={`Inspect cited passage ${l}`}
                className="mx-0.5 rounded-[var(--radius-chip)] border border-accent/40 bg-accent-tint px-1.5 align-[0.1em] font-mono text-xs text-accent-soft hover:border-accent"
              >
                {l}
              </button>
            ))}
          </span>
        ),
      )}
    </p>
  );
}
