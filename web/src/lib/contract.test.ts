import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type { ProposedCiteHopSearchPresentationModel as SearchView } from "./types";

const example: SearchView = JSON.parse(
  readFileSync(resolve(__dirname, "../../../design/contracts/search-view.example.json"), "utf8"),
);

describe("search view contract example", () => {
  it("keeps corpusid as an exact string", () => {
    const id = example.results[0].paper.corpusid;
    expect(typeof id).toBe("string");
    expect(BigInt(id)).toBe(BigInt("9007199254740993"));
  });

  it("shows why ids must not become numbers", () => {
    const id = example.results[0].paper.corpusid;
    expect(String(Number(id))).not.toBe(id);
  });

  it("keeps every found_via label", () => {
    expect(example.results[0].found_via).toEqual(["kw", "vec"]);
  });

  it("reports returned_count equal to the number of results", () => {
    expect(example.returned_count).toBe(example.results.length);
  });
});
