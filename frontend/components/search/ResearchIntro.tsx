import Link from "next/link";
import { Icon } from "@/components/icons";

export function ResearchIntro({ compact }: { compact: boolean }) {
  return (
    <section className={`research-intro ${compact ? "research-intro-compact" : ""}`}>
      <div className="relative z-10">
        <p className="mb-5 flex items-center gap-2.5 text-[10px] font-medium uppercase tracking-[0.22em] text-accent"><span className="h-px w-6 bg-accent" /> A little curiosity goes a long way</p>
        <h1 className="research-title">Big questions.<br /><span>Clear connections.</span></h1>
        {!compact && <p className="mt-5 max-w-[440px] text-[15px] leading-7 text-muted">Explore machine learning, one source at a time.<br className="hidden sm:block" /> Find the evidence. Get a cited answer. Follow the thread.</p>}
      </div>
      {!compact && <div className="research-art" aria-hidden="true">
        <div className="orbit orbit-outer" /><div className="orbit orbit-inner" />
        <svg className="art-connections" viewBox="0 0 360 260" fill="none"><path d="M80 75 180 130 291 58M180 130l103 72M180 130l-103 76" stroke="currentColor" strokeDasharray="3 5" /><circle cx="180" cy="130" r="65" stroke="currentColor" strokeOpacity=".3" /></svg>
        <div className="art-node art-question"><Icon name="search" /><span>Ask</span></div>
        <div className="art-core"><Icon name="spark" width="32" height="32" /></div>
        <div className="art-node art-source"><Icon name="library" /><span>Find sources</span></div>
        <div className="art-node art-answer"><Icon name="check" /><span>Cite</span></div>
        <div className="art-node art-explore"><Icon name="graph" /><span>Connect</span></div>
        <span className="art-caption">FOLLOW THE EVIDENCE</span>
      </div>}
    </section>
  );
}

export function ExploreMore() {
  return <section className="explore-section" aria-labelledby="explore-heading">
    <div className="mb-5 flex items-center gap-4"><h2 id="explore-heading" className="shrink-0 text-[10px] font-medium uppercase tracking-[0.18em] text-muted">There’s more to discover</h2><div className="h-px flex-1 bg-line" /></div>
    <div className="grid gap-4 sm:grid-cols-2">
      <Link href="/library" className="explore-card group"><span className="explore-icon"><Icon name="library" /></span><div className="flex-1"><h3 className="text-sm font-medium">Go straight to the source</h3><p className="mt-1 text-xs leading-5 text-muted">Browse the articles behind every answer.</p></div><Icon name="arrow" className="text-muted transition-transform group-hover:translate-x-1 group-hover:text-accent" /></Link>
      <Link href="/graph" className="explore-card group"><span className="explore-icon"><Icon name="graph" /></span><div className="flex-1"><h3 className="text-sm font-medium">See the bigger picture</h3><p className="mt-1 text-xs leading-5 text-muted">Explore how articles and ideas connect.</p></div><Icon name="arrow" className="text-muted transition-transform group-hover:translate-x-1 group-hover:text-accent" /></Link>
    </div>
    <p className="mt-8 flex items-center justify-center gap-2 text-[11px] text-muted"><Icon name="check" width="13" height="13" /> Grounded in Wikipedia. Built for curious minds.</p>
  </section>;
}
