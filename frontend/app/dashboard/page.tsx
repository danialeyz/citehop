import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState, PageHeader, buttonSecondary } from "@/components/ui";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <>
      <PageHeader eyebrow="Dashboard" title="Corpus and evaluation">
        <p>Live corpus counts, graph status, and saved retrieval and grounding runs.</p>
      </PageHeader>
      <EmptyState icon="▥" title="The dashboard is not built yet" action={<Link href="/library" className={buttonSecondary}>Browse the Library</Link>}>
        <p>
          It will read live counts and identified saved evaluation runs from the API. No numbers are shown here until that
          screen exists, so nothing on this page is a placeholder metric.
        </p>
      </EmptyState>
    </>
  );
}
