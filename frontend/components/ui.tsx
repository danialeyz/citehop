// Shared presentational pieces for every route. Server-safe: no hooks or browser APIs.
import Link from "next/link";
import type { ReactNode } from "react";

export const buttonPrimary =
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] bg-accent px-4 py-2 text-sm font-semibold text-page hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-60";
export const buttonSecondary =
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] border border-line-strong px-4 py-2 text-sm font-medium text-ink hover:border-accent hover:text-accent-soft";
export const inputClass =
  "w-full rounded-[var(--radius-control)] border border-line bg-page px-3 py-2 text-base text-ink placeholder:text-muted/70 focus-visible:border-accent";

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent">{children}</p>;
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: ReactNode; children?: ReactNode }) {
  return (
    <header className="mb-8 max-w-3xl">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1 className="mt-2 text-3xl font-medium tracking-[-0.04em] text-ink [overflow-wrap:anywhere] sm:text-[38px] sm:leading-tight">
        {title}
      </h1>
      {children && <div className="mt-3 text-base text-muted">{children}</div>}
    </header>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-[var(--radius-card)] border border-line bg-panel p-5 sm:p-6 ${className}`}>{children}</section>;
}

export function Chip({ children, tone = "category" }: { children: ReactNode; tone?: "category" | "neutral" | "accent" }) {
  const tones = {
    category: "border-amber/30 bg-amber-tint text-amber",
    neutral: "border-line bg-strip text-muted",
    accent: "border-accent/30 bg-accent-tint text-accent-soft",
  };
  return (
    <span className={`inline-flex max-w-full items-center rounded-[var(--radius-chip)] border px-2 py-0.5 text-xs [overflow-wrap:anywhere] ${tones[tone]}`}>
      {children}
    </span>
  );
}

/** Category chip that filters the Library by that exact category. */
export function CategoryLink({ name }: { name: string }) {
  return (
    <Link
      href={`/library?category=${encodeURIComponent(name)}`}
      className="inline-flex max-w-full items-center rounded-[var(--radius-chip)] border border-amber/30 bg-amber-tint px-2 py-0.5 text-xs text-amber [overflow-wrap:anywhere] hover:border-amber"
      aria-label={`Show articles in category ${name}`}
    >
      {name}
    </Link>
  );
}

export function EmptyState({ icon, title, children, action }: { icon: string; title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div role="status" className="flex flex-col items-start gap-3 rounded-[var(--radius-card)] border border-dashed border-line-strong bg-panel/60 p-6 sm:p-8">
      <span aria-hidden className="grid size-10 place-items-center rounded-full bg-accent-tint text-lg text-accent">{icon}</span>
      <h2 className="text-xl font-medium tracking-[-0.02em]">{title}</h2>
      <div className="max-w-2xl text-muted">{children}</div>
      {action && <div className="mt-1 flex flex-wrap gap-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-[var(--radius-card)] border border-danger/40 bg-danger-tint p-6">
      <span aria-hidden className="grid size-10 place-items-center rounded-full bg-page text-lg font-bold text-danger">!</span>
      <h2 className="text-xl font-medium">{title}</h2>
      <div className="max-w-2xl text-ink/85">{children}</div>
      {action && <div className="mt-1 flex flex-wrap gap-3">{action}</div>}
    </div>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="border-l-2 border-accent/60 pl-3 text-sm text-muted">{children}</p>;
}

export function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-line py-2.5 last:border-b-0 sm:flex-row sm:justify-between sm:gap-4">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-sm text-ink [overflow-wrap:anywhere] sm:text-right">{children}</dd>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-line/60 ${className}`} />;
}
