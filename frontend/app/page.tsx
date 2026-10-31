import Image from "next/image";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center gap-8 px-6 py-16">
      <Image src="/logo-dark.svg" alt="CiteHop" width={320} height={100} priority className="h-auto max-w-full" />
      <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">Ask a question.<br />Follow the sources.</h1>
      <p className="max-w-xl text-lg text-slate-300">Explore machine learning through Wikipedia passages and the connections between articles.</p>
      <p className="border-l-2 border-cyan-400 pl-4 text-slate-400">The local foundation is ready. Search, answers, and graph exploration are coming in the next course tasks.</p>
    </main>
  );
}
