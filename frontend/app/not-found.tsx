import Link from "next/link";

import { EmptyState, buttonSecondary } from "@/components/ui";

export default function NotFound() {
  return (
    <EmptyState icon="◇" title="Not found" action={<Link href="/library" className={buttonSecondary}>Browse the Library</Link>}>
      <p>There is no page or article at this address in the current corpus.</p>
    </EmptyState>
  );
}
