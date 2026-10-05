import "server-only";

import { cache } from "react";

import type { Evidence } from "@/content/milestones";
import { allOf, latest, type JudgeEval } from "@/lib/artifacts";

/** The newest artifact of each kind, the inputs of every milestone criterion's evidence. */
export const loadEvidence = cache(async (): Promise<Evidence> => {
  const [er, hyp, h4, judges, quality, perf, relevance] = await Promise.all([
    latest("er-eval"),
    latest("hypotheses"),
    latest("h4"),
    allOf("judge-eval"),
    latest("quality"),
    latest("performance"),
    latest("relevance"),
  ]);
  const judge: Record<string, JudgeEval> = {};
  for (const a of judges) {
    const model = String(a.provenance.model ?? a.file);
    judge[model] ??= a.data; // newest first
  }
  return {
    er: er?.data ?? null,
    hyp: hyp?.data ?? null,
    h4: h4?.data ?? null,
    judge,
    quality: quality?.data ?? null,
    perf: perf?.data ?? null,
    relevance: relevance?.data ?? null,
  };
});
