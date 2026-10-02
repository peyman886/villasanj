/** The owner's blind review of review summaries (M10 criterion 3): the task and its fetch. */

import type { components } from "@/lib/api/schema";

export type SummaryReviewTask = components["schemas"]["SummaryReviewTaskOut"];
export type SummaryReviewResult =
  { kind: "ready"; task: SummaryReviewTask } | { kind: "missing" } | { kind: "error" };

type KeyLike = { code: string; altKey: boolean; ctrlKey: boolean; metaKey: boolean };

/** Physical keys (a Persian layout too): Y faithful, N not faithful. */
export function verdictFor(event: KeyLike): boolean | null {
  if (event.altKey || event.ctrlKey || event.metaKey) return null;
  if (event.code === "KeyY") return true;
  if (event.code === "KeyN") return false;
  return null;
}

export async function fetchSummaryReviewTask(
  baseUrl: string,
  queue: string,
  labeler: string,
  position?: number,
): Promise<SummaryReviewResult> {
  const params = new URLSearchParams({ queue, labeler });
  if (position !== undefined) params.set("position", String(position));
  try {
    const response = await fetch(`${baseUrl}/summary-reviews/task?${params}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 404) return { kind: "missing" };
    if (!response.ok) return { kind: "error" };
    return { kind: "ready", task: (await response.json()) as SummaryReviewTask };
  } catch {
    return { kind: "error" };
  }
}
