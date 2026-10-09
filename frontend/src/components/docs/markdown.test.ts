import { describe, expect, it } from "vitest";

import { portalHref } from "@/components/docs/markdown";

describe("portalHref", () => {
  it("maps repository files to portal routes", () => {
    expect(portalHref("0005-llm-model-selection-and-cost.md")).toBe(
      "/docs/decisions/0005-llm-model-selection-and-cost",
    );
    expect(portalHref("adr/0014-er-decisions-rules-and-llm-judge.md#amendment")).toBe(
      "/docs/decisions/0014-er-decisions-rules-and-llm-judge#amendment",
    );
    expect(portalHref("../reports/er-eval-2026-10-04.md")).toBe("/docs/reports/er-eval-2026-10-04");
    expect(portalHref("../ROADMAP.md")).toBe("/docs/milestones");
    expect(portalHref("ARCHITECTURE.md")).toBe("/docs/architecture");
  });

  it("keeps a reader of the English portal in English", () => {
    expect(portalHref("0005-llm-model-selection-and-cost.md", "en")).toBe(
      "/en/docs/decisions/0005-llm-model-selection-and-cost",
    );
    expect(portalHref("../reports/er-eval-2026-10-04.md", "en")).toBe(
      "/en/docs/reports/er-eval-2026-10-04",
    );
    expect(portalHref("../ROADMAP.md#m5", "en")).toBe("/en/docs/milestones#m5");
    expect(portalHref("https://www.openstreetmap.org/copyright", "en")).toBe(
      "https://www.openstreetmap.org/copyright",
    );
    expect(portalHref("#context", "en")).toBe("#context");
  });

  it("keeps web links and anchors, and drops files the portal does not show", () => {
    expect(portalHref("https://www.openstreetmap.org/copyright")).toBe(
      "https://www.openstreetmap.org/copyright",
    );
    expect(portalHref("#context")).toBe("#context");
    expect(portalHref("../../backend/benchmarks/image_embeddings.py")).toBeNull();
  });
});
