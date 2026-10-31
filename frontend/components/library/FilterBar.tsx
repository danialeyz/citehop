"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { buttonPrimary, buttonSecondary, inputClass } from "@/components/ui";
import { libraryHref, withFilters, type ListState } from "@/lib/library";

export function FilterBar({ state }: { state: ListState }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const filtered = Boolean(state.title || state.category);

  function apply(form: FormData) {
    const title = String(form.get("title") ?? "").trim() || undefined;
    const category = String(form.get("category") ?? "").trim() || undefined;
    startTransition(() => router.push(libraryHref(withFilters(state, { title, category }))));
  }

  return (
    <form
      // Remount on URL changes so inputs show the active filters after back/forward.
      key={`${state.title ?? ""}\u0000${state.category ?? ""}`}
      action={apply}
      role="search"
      aria-label="Filter articles"
      className="grid gap-4 rounded-[var(--radius-card)] border border-line bg-panel p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end"
    >
      <label className="flex flex-col gap-1.5 text-sm text-muted">
        Title contains
        <input name="title" defaultValue={state.title} maxLength={200} placeholder="e.g. neural" className={inputClass} />
      </label>
      <label className="flex flex-col gap-1.5 text-sm text-muted">
        Category (exact name)
        <input name="category" defaultValue={state.category} maxLength={255} placeholder="e.g. Machine learning" className={inputClass} />
      </label>
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={pending} className={buttonPrimary}>
          {pending ? "Filtering…" : "Apply filters"}
        </button>
        {filtered && (
          <button
            type="button"
            disabled={pending}
            onClick={() => startTransition(() => router.push(libraryHref({ page: 1 })))}
            className={buttonSecondary}
          >
            Clear
          </button>
        )}
      </div>
    </form>
  );
}
