/**
 * The status tables in docs/ROADMAP.md are generated from src/content/milestones.ts and the newest
 * report artifacts, so the ROADMAP and the portal cannot disagree. This test fails when they drift;
 * `make roadmap` (UPDATE_ROADMAP=1) rewrites the generated blocks.
 */
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { MILESTONES, OPEN_ITEMS, STATUS_EN, text, type Evidence } from "@/content/milestones";

const ROOT = path.resolve(__dirname, "..", "..", "..");
const ROADMAP = path.join(ROOT, "docs", "ROADMAP.md");

function loadEvidence(): Evidence {
  const dir = path.join(ROOT, "reports");
  const artifacts = readdirSync(dir)
    .filter((n) => n.endsWith(".json"))
    .map(
      (n) =>
        JSON.parse(readFileSync(path.join(dir, n), "utf8")) as {
          kind: string;
          generated_at: string;
          provenance: Record<string, unknown>;
          data: unknown;
        },
    )
    .sort((a, b) => b.generated_at.localeCompare(a.generated_at));
  const newest = <T>(kind: string) => (artifacts.find((a) => a.kind === kind)?.data ?? null) as T;
  const judge: Evidence["judge"] = {};
  for (const a of artifacts.filter((x) => x.kind === "judge-eval")) {
    judge[String(a.provenance.model)] ??= a.data as Evidence["judge"][string];
  }
  return {
    er: newest("er-eval"),
    hyp: newest("hypotheses"),
    h4: newest("h4"),
    judge,
    quality: newest("quality"),
    perf: newest("performance"),
    relevance: newest("relevance"),
  };
}

const cell = (s: string) => s.replaceAll("|", "\\|").replaceAll("\n", " ");

function statusBlock(evidence: Evidence): string {
  const rows = MILESTONES.flatMap((m) =>
    m.criteria.map(
      (c) =>
        `| ${m.id} | ${c.n} | ${cell(c.title_en)} | ${STATUS_EN[c.status]} | ${cell(text(c.evidence_en, evidence))} |`,
    ),
  );
  return ["| M | # | Criterion | Status | Evidence |", "|---|---|---|---|---|", ...rows].join("\n");
}

function closed(m: (typeof MILESTONES)[number]): string {
  const done = m.criteria.filter((c) => c.status === "done").length;
  const waived = m.criteria.filter((c) => c.status === "waived").length;
  return `${done}/${m.criteria.length}${waived ? ` (+${waived} closed by the owner)` : ""}`;
}

function summaryBlock(): string {
  return [
    "| M | Name | Status | Criteria |",
    "|---|---|---|---|",
    ...MILESTONES.map(
      (m) =>
        `| ${m.id} | ${m.name_en} | ${STATUS_EN[m.status]}${m.date ? ` (${m.date})` : ""} | ${closed(m)} |`,
    ),
  ].join("\n");
}

const KIND_EN = {
  not_met: "Not met",
  blocked: "Blocked by others",
  avalai: "Needs AvalAI calls",
  owner: "Needs the owner",
} as const;

function openBlock(): string {
  return (Object.keys(KIND_EN) as (keyof typeof KIND_EN)[])
    .map((k) => {
      const items = OPEN_ITEMS.filter((i) => i.kind === k).map((i) => `  - ${i.en}`);
      return items.length ? `- **${KIND_EN[k]}:**\n${items.join("\n")}` : "";
    })
    .filter(Boolean)
    .join("\n");
}

function replaceBlock(doc: string, name: string, body: string): string {
  const begin = `<!-- generated:${name}:begin -->`;
  const end = `<!-- generated:${name}:end -->`;
  const start = doc.indexOf(begin);
  const stop = doc.indexOf(end);
  if (start < 0 || stop < start) throw new Error(`ROADMAP has no ${name} markers`);
  return `${doc.slice(0, start + begin.length)}\n${body}\n${doc.slice(stop)}`;
}

describe("ROADMAP status tables", () => {
  it("match src/content/milestones.ts and the newest report artifacts", () => {
    const evidence = loadEvidence();
    const current = readFileSync(ROADMAP, "utf8");
    let expected = replaceBlock(current, "summary", summaryBlock());
    expected = replaceBlock(expected, "criteria", statusBlock(evidence));
    expected = replaceBlock(expected, "open", openBlock());
    if (process.env.UPDATE_ROADMAP === "1" && expected !== current) {
      writeFileSync(ROADMAP, expected);
      return;
    }
    expect(current, "run `make roadmap` to regenerate docs/ROADMAP.md").toBe(expected);
  });

  it("every milestone's status follows from its criteria", () => {
    for (const m of MILESTONES) {
      const closed = m.criteria.every((c) => c.status === "done" || c.status === "waived");
      if (closed) expect(m.status, m.id).toBe("done");
      else expect(m.status, m.id).not.toBe("done");
    }
  });

  it("every open criterion has an open item that says what it waits for", () => {
    const open = MILESTONES.flatMap((m) =>
      m.criteria
        .filter((c) => c.status !== "done" && c.status !== "waived")
        .map((c) => `${m.id} crit. ${c.n}`),
    );
    const listed = OPEN_ITEMS.map((i) => i.en).join(" ");
    for (const id of open) expect(listed, id).toContain(id);
  });
});
