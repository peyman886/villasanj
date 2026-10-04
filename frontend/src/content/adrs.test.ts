import { readdirSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ADR_CARDS } from "@/content/adrs";

describe("ADR cards", () => {
  it("cover every ADR in docs/adr and nothing else", () => {
    const dir = path.resolve(__dirname, "..", "..", "..", "docs", "adr");
    const numbers = readdirSync(dir)
      .filter((n) => /^\d{4}-.+\.md$/.test(n))
      .map((n) => n.slice(0, 4))
      .sort();
    expect(Object.keys(ADR_CARDS).sort()).toEqual(numbers);
  });
});
