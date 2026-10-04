/**
 * Generated report artifacts (reports/*.json), the source of every number the docs and the home
 * page show. Each artifact says which command produced it, when, and from which data (match run,
 * dataset hash, labels); the UI shows that next to the number. Server-only: reads REPORTS_DIR.
 */
import "server-only";

import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { cache } from "react";

export type Interval = { estimate: number | null; low: number; high: number };

export type Metrics = {
  threshold: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  unsure: number;
  precision: Interval;
  recall: Interval;
  f1: number | null;
};

export type PolicyResult = {
  name: string;
  rule: string;
  configured: boolean;
  meets_bar: boolean;
  metrics: Metrics;
  waiting: number;
  bcubed: { precision: number; recall: number; f1: number; elements: number } | null;
};

export type LabelledEvaluation = {
  labelled: number;
  queued: number;
  unsure: Interval;
  blocking_recall: Interval;
  gold_threshold: Metrics | null;
  curve: Metrics[];
  labels_by_stratum: Record<string, Record<string, number>>;
  policies: PolicyResult[];
};

export type VillaCounts = {
  labels: string;
  rule: string;
  listings: number;
  villas: number;
  multi_platform: number;
  applied: Record<string, number>;
  refused: Record<string, number>;
};

export type ErEval = {
  revised: LabelledEvaluation;
  original: LabelledEvaluation;
  revisions: {
    pair: string;
    kind: string;
    before: string;
    after: string;
    reason: string;
    revised_by: string;
    revised_at: string;
  }[];
  villas_now: VillaCounts;
  villas_before: VillaCounts;
  ablations: { name: string; at_bar: Metrics | null; best_f1: Metrics | null }[];
  judge_verdicts: Record<string, number>;
  human_queue: Record<string, number>;
};

export type Hypotheses = {
  precision: Interval | null;
  recall: Interval | null;
  h1: {
    listings: Record<string, number>;
    matched: Record<string, number>;
    pairs: number;
    corrected_pairs: Interval | null;
    villas_on_both_share: Interval | null;
  };
  h2: {
    scenario: string;
    guests: number;
    pairs: number;
    median_ratio: number | null;
    p90_ratio: number | null;
    cheaper: Record<string, number>;
  }[];
  h2_flips: { pairs: number; flips: number };
  h3: {
    nights_compared: number;
    hidden_nights: number;
    pairs_with_hidden_night: number;
    pairs: number;
    max_gap_hours: number;
  };
};

export type H4 = {
  platforms: {
    platform: string;
    listings: number;
    in_multi_platform_villas: number;
    judged: number;
    contradicted: number;
    compared: number;
    inconsistent: number;
    either: number;
    share: Interval;
    inconsistent_share: Interval;
    kinds: Record<string, number>;
  }[];
};

export type JudgeEval = {
  pairs: number;
  judged: number;
  unsure_rate: number;
  false_matches: number;
  confusion: Record<string, Record<string, number>>;
  by_confidence: Record<string, { precision: Interval; recall: Interval }>;
  cost_usd: string;
};

export type Quality = {
  suites: { name: string; passed: number; failed: number; skipped: number; seconds: number }[];
  coverage: { name: string; percent: number }[];
};

export type Performance = {
  measurements: {
    name: string;
    samples: number;
    p50_ms: number;
    p95_ms: number;
    max_ms: number;
    target_ms: number | null;
  }[];
};

type Kinds = {
  "er-eval": ErEval;
  hypotheses: Hypotheses;
  h4: H4;
  "judge-eval": JudgeEval;
  quality: Quality;
  performance: Performance;
};
export type Kind = keyof Kinds;

export type Artifact<K extends Kind = Kind> = {
  kind: K;
  file: string; // e.g. reports/er-eval-2026-10-04.json
  command: string;
  generated_at: string;
  provenance: Record<string, unknown>;
  data: Kinds[K];
};

export function reportsDir(): string {
  return process.env.REPORTS_DIR ?? path.join(process.cwd(), "..", "reports");
}

/** Every artifact in the reports directory, newest first. Missing directory = none. */
export const loadArtifacts = cache(async (): Promise<Artifact[]> => {
  const dir = reportsDir();
  let names: string[];
  try {
    names = (await readdir(dir)).filter((n) => n.endsWith(".json"));
  } catch {
    return [];
  }
  const found: Artifact[] = [];
  for (const name of names) {
    try {
      const raw = JSON.parse(await readFile(path.join(dir, name), "utf8")) as Omit<
        Artifact,
        "file"
      > & { version?: number };
      if (typeof raw.kind !== "string" || typeof raw.generated_at !== "string") continue;
      found.push({ ...raw, file: `reports/${name}` });
    } catch {
      continue; // a file that is not an artifact is ignored, never shown as data
    }
  }
  return found.sort((a, b) => b.generated_at.localeCompare(a.generated_at));
});

export async function latest<K extends Kind>(kind: K): Promise<Artifact<K> | null> {
  const all = await loadArtifacts();
  return (all.find((a) => a.kind === kind) as Artifact<K> | undefined) ?? null;
}

export async function allOf<K extends Kind>(kind: K): Promise<Artifact<K>[]> {
  return (await loadArtifacts()).filter((a) => a.kind === kind) as Artifact<K>[];
}
