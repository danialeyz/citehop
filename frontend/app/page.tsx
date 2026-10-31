import Link from "next/link";

import { EmptyState, Eyebrow, Panel, buttonSecondary } from "@/components/ui";

const STEPS = [
  { label: "Keyword", text: "MariaDB FULLTEXT search over stored passages." },
  { label: "Meaning", text: "Native MariaDB vector search with BGE base embeddings (768 dimensions)." },
  { label: "Answer", text: "A bounded answer that cites only the retrieved passages." },
];

export default function SearchPage() {
  return (
    <>
      <section className="mb-10 max-w-4xl">
        <Eyebrow>Search</Eyebrow>
        <h1 className="mt-3 text-4xl font-medium leading-[1.05] tracking-[-0.05em] sm:text-[55px]">
          Ask a question.
          <br />
          <span className="text-accent">Follow the sources.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted">
          Explore machine learning through Wikipedia passages and the real links between articles.
        </p>
      </section>

      <EmptyState
        icon="⌕"
        title="Search is not connected to this screen yet"
        action={<Link href="/library" className={buttonSecondary}>Browse the Library</Link>}
      >
        <p>
          The API can already retrieve passages and generate cited answers, but the search screen that calls it is the next step
          in the build. Until then, browse the stored articles and their exact passages in the Library.
        </p>
      </EmptyState>

      <Panel className="mt-8">
        <h2 className="mb-4 text-[17px] font-medium">How answers will be built</h2>
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <li key={step.label} className="rounded-xl border border-line bg-strip p-4">
              <p className="font-mono text-xs text-accent">0{i + 1} / {step.label.toUpperCase()}</p>
              <p className="mt-2 text-sm text-muted">{step.text}</p>
            </li>
          ))}
        </ol>
      </Panel>
    </>
  );
}
