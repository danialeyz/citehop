// C14 browser journey against the real stack: search → generate → inspect citation → explore the
// article in the graph → select/expand a node → find a path → dashboard, plus Library and 390 px checks.
// Needs the API, the frontend (`npm run build && npm start`), a loaded/embedded corpus, an imported
// graph, and Ollama. One real /answer call. Usage: BASE=http://127.0.0.1:3000 npm run e2e
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const BASE = (process.env.BASE ?? "http://127.0.0.1:3000").replace(/\/$/, "");
const OUT = process.env.SHOTS ?? "../.context/e2e";
const QUESTION = process.env.QUESTION ?? "Who coined the term machine learning, and when?";
mkdirSync(OUT, { recursive: true });

let failures = 0;
const check = (ok, message) => {
  console.log(ok ? "ok:  " : "FAIL:", message);
  if (!ok) failures++;
};
const api = async (path) => (await fetch(`${BASE}/api/v1${path}`)).json();
const norm = (s) => s.replace(/\s+/g, " ").trim();

const browser = await chromium.launch();
const errors = [];
async function page(width, height = 1000) {
  const p = await (await browser.newContext({ viewport: { width, height } })).newPage();
  p.on("pageerror", (e) => errors.push(`${p.url()} ${e.message}`));
  p.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && errors.push(`${p.url()} ${m.text()}`));
  return p;
}
const overflow = (p) => p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

try {
  // 1. Search retrieves only; generation is one explicit call.
  const d = await page(1440);
  let answerCalls = 0;
  d.on("request", (r) => r.url().endsWith("/api/v1/answer") && answerCalls++);
  await d.goto(BASE, { waitUntil: "networkidle" });
  await d.getByRole("search").locator("#q").fill(QUESTION);
  await d.getByRole("button", { name: "Find sources" }).click();
  await d.locator("li[id^=source-]").first().waitFor();
  const cards = await d.locator("li[id^=source-]").count();
  check(cards > 0 && cards <= 5, `${cards} ranked source cards`);
  check(answerCalls === 0, "search does not call the generator");
  await d.getByRole("button", { name: "Generate answer" }).click();
  const chip = d.locator("section[aria-labelledby=answer-title] span")
    .filter({ hasText: /Answered with citations|Not enough evidence|Answer withheld|Generator unavailable/ }).first();
  await chip.waitFor({ timeout: 240_000 });
  check((await chip.innerText()) === "Answered with citations", `answer status: ${await chip.innerText()}`);
  check(answerCalls === 1, "exactly one /answer call");
  await d.screenshot({ path: `${OUT}/search-answer-1440.png`, fullPage: true });

  // 2. A citation opens the exact stored passage.
  await d.getByRole("button", { name: /^Inspect cited passage S\d$/ }).first().click();
  const dialog = d.locator("dialog[open]");
  await dialog.waitFor();
  const chunkId = (await dialog.locator("dd span.font-mono").first().innerText()).trim();
  const articleId = Number(await dialog.locator("dd span.font-mono").nth(1).innerText());
  const shown = await dialog.locator("blockquote").innerText();
  await d.screenshot({ path: `${OUT}/search-citation-1440.png` });
  let stored = null;
  for (let pp = 1; stored === null; pp++) {
    const res = await api(`/articles/${articleId}?passage_page=${pp}&passage_page_size=50`);
    stored = res.passages.items.find((p) => p.chunk_id === chunkId)?.text ?? null;
    if (pp * 50 >= res.passages.total) break;
  }
  check(stored !== null && norm(stored) === norm(shown), `citation shows stored chunk ${chunkId.slice(0, 12)}… of article ${articleId}`);
  await d.keyboard.press("Escape");

  // 3. Explore connections → graph seeded with that article and the search context.
  await d.locator("li[id^=source-]").first().getByRole("link", { name: "Explore connections" }).click();
  await d.waitForURL(/\/graph\?article=\d+/);
  const seed = Number(new URL(d.url()).searchParams.get("article"));
  await d.locator(".react-flow__node").first().waitFor();
  check(await d.getByText("Back to search results").isVisible(), "graph keeps the search context");
  const ids = async () => d.locator(".react-flow__node").evaluateAll((els) => els.map((e) => e.dataset.id));
  const before = await ids();
  check(before.length > 1, `seed ${seed}: ${before.length} nodes rendered`);

  // 4. Select a neighbor, expand it, keep existing nodes in place.
  const neighbor = before.find((id) => id.startsWith("article:") && id !== `article:${seed}`);
  const box = async (id) => d.locator(`.react-flow__node[data-id="${id}"]`).boundingBox();
  const seedBox = await box(`article:${seed}`);
  await d.locator(`.react-flow__node[data-id="${neighbor}"]`).click();
  await d.getByRole("button", { name: "Expand neighborhood" }).click();
  await d.getByRole("button", { name: "Expanded", exact: true }).waitFor();
  const after = await ids();
  check(after.length >= before.length, `expansion: ${before.length} → ${after.length} nodes`);
  const seedAfter = await box(`article:${seed}`);
  check(Math.abs(seedAfter.x - seedBox.x) < 1 && Math.abs(seedAfter.y - seedBox.y) < 1, "seed position unchanged by expansion");

  // 5. Path from the seed to the first article in view that has a 2–3 link path (backend-checked).
  let target = null;
  for (const id of after.filter((i) => i.startsWith("article:")).map((i) => Number(i.split(":")[1]))) {
    if (id === seed) continue;
    const p = await api(`/graph/path?source_id=${seed}&target_id=${id}`);
    if (p.found && p.edges.length >= 2) { target = id; break; }
  }
  check(target !== null, `found a multi-link path target in view: ${target}`);
  await d.getByLabel("Path start article").selectOption(String(seed));
  await d.getByLabel("Path end article").selectOption(String(target));
  await d.getByRole("button", { name: "Find path" }).click();
  await d.locator(".citehop-path-edge").first().waitFor({ timeout: 15_000 }).catch(() => {});
  const pathEdges = await d.locator(".citehop-path-edge").count();
  check(pathEdges >= 2, `${pathEdges} path edges highlighted on the canvas`);
  await d.locator(`.react-flow__node[data-id="article:${target}"]`).click();
  await d.setViewportSize({ width: 1440, height: 2000 });
  await d.screenshot({ path: `${OUT}/graph-path-1440.png` });
  await d.setViewportSize({ width: 1440, height: 1000 });

  // 6. Dashboard reads live counts and saved runs; no generation on page load.
  const callsBefore = answerCalls;
  await d.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
  await d.getByText("Neo4j graph projection").waitFor();
  await d.getByText("Comparison table").waitFor();
  check(answerCalls === callsBefore, "dashboard makes no generation call");
  await d.screenshot({ path: `${OUT}/dashboard-1440.png`, fullPage: true });

  // 7. Library list and detail.
  await d.goto(`${BASE}/library`, { waitUntil: "networkidle" });
  await d.getByText("Browse the corpus").waitFor();
  await d.screenshot({ path: `${OUT}/library-1440.png`, fullPage: true });
  await d.goto(`${BASE}/library/${articleId}`, { waitUntil: "networkidle" });
  await d.screenshot({ path: `${OUT}/library-detail-1440.png`, fullPage: true });

  // 8. All four views at 390 px: no page-level horizontal scrolling.
  const m = await page(390, 844);
  for (const [name, path] of [["search", `/?q=${encodeURIComponent(QUESTION)}`], ["library", "/library"], ["graph", `/graph?article=${seed}`], ["dashboard", "/dashboard"]]) {
    await m.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    if (name === "graph") await m.locator(".react-flow__node").first().waitFor();
    if (name === "search") await m.locator("li[id^=source-]").first().waitFor();
    check((await overflow(m)) <= 0, `${name} at 390 px has no horizontal overflow`);
    await m.screenshot({ path: `${OUT}/${name}-390.png`, fullPage: name !== "graph" });
  }
  check(errors.length === 0, `no page errors${errors.length ? `: ${errors.join(" | ")}` : ""}`);
} finally {
  await browser.close();
}
console.log(failures ? `${failures} check(s) failed` : "journey passed");
process.exitCode = failures ? 1 : 0;
