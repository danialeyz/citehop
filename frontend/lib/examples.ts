// Server-only: sample questions from the frozen dev split in eval/questions.json. Test questions are
// never shown, so the UI cannot be tuned against them. Review status is passed through unchanged.
import { readFile } from "node:fs/promises";
import path from "node:path";

import { parseFilters, type Filters } from "@/lib/search";

export type Example = { id: string; question: string; filters: Filters; reviewStatus: string };

type RawQuestion = {
  id: string;
  split: string;
  question: string;
  filters?: Record<string, string | number | null>;
  review?: { status?: string };
};

// The repository file is read at request time, not bundled; the frontend runs from `frontend/`.
const QUESTIONS_PATH = path.join(/*turbopackIgnore: true*/ process.cwd(), "..", "eval", "questions.json");

export async function loadDevExamples(): Promise<Example[] | null> {
  try {
    const data = JSON.parse(await readFile(QUESTIONS_PATH, "utf8")) as { questions: RawQuestion[] };
    return data.questions
      .filter((q) => q.split === "dev")
      .map((q) => {
        const raw = q.filters ?? {};
        const value = (key: string) => (raw[key] === null || raw[key] === undefined ? undefined : String(raw[key]));
        const filters = parseFilters((key) =>
          value({ category: "category", min: "min_length_chars", max: "max_length_chars", from: "linked_from" }[key] ?? key),
        );
        return { id: q.id, question: q.question, filters, reviewStatus: q.review?.status ?? "unreviewed" };
      })
      // Approved questions first; the rest keep their frozen order.
      .sort((a, b) => Number(b.reviewStatus === "approved") - Number(a.reviewStatus === "approved"));
  } catch {
    return null;
  }
}
