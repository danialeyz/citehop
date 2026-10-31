"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { buttonPrimary, inputClass } from "@/components/ui";
import { dashboardHref } from "@/lib/dashboard";

type Option = { runId: string; label: string };

/** Run and split live in the URL, so one navigation re-renders every chart and table together. */
export function RunPicker({ runs, run, splits, split }: { runs: Option[]; run: string; splits: Record<string, number>; split: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function apply(form: FormData) {
    // A split the newly chosen run lacks falls back to that run's default on the server.
    const next = { run: String(form.get("run") ?? run), split: String(form.get("split") ?? split) };
    startTransition(() => router.push(dashboardHref(next)));
  }

  return (
    <form
      key={`${run}\u0000${split}`}
      action={apply}
      aria-label="Choose a saved evaluation run"
      className="grid gap-4 rounded-[var(--radius-card)] border border-line bg-panel p-4 sm:p-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] lg:items-end"
    >
      <label className="flex min-w-0 flex-col gap-1.5 text-sm text-muted">
        Saved run
        <select name="run" defaultValue={run} className={`${inputClass} font-mono text-sm`}>
          {runs.map((r) => <option key={r.runId} value={r.runId}>{r.label}</option>)}
        </select>
      </label>
      <label className="flex min-w-0 flex-col gap-1.5 text-sm text-muted">
        Question split
        <select name="split" defaultValue={split} className={inputClass}>
          {Object.entries(splits).map(([name, n]) => (
            <option key={name} value={name}>{name} ({n} questions)</option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={pending} className={buttonPrimary}>
        {pending ? "Loading…" : "Show run"}
      </button>
    </form>
  );
}
