export default function Home() {
  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-[1600px] px-5 py-16 wide:px-7 full:px-[42px]">
      <p className="font-mono text-[10px] uppercase tracking-[0.17em] text-muted">
        Frontend scaffold
      </p>
      <h1 className="mt-2 text-[43px] font-semibold leading-[1.02] tracking-tight wide:text-[57px]">
        CiteHop
      </h1>
      <p className="mt-4 max-w-xl text-muted">
        Screens are built from the approved design in <code className="font-mono">design/</code>,
        starting with FE-01 (theme and shell). See{" "}
        <code className="font-mono">design/docs/13-FRONTEND-ARCHITECTURE.md</code>.
      </p>
    </main>
  );
}
