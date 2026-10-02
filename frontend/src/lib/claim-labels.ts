/** Labelling feature claims in descriptions (M9 criterion 1): the task and its fetch. */

import type { components } from "@/lib/api/schema";

export type ClaimTask = components["schemas"]["ClaimTaskOut"];
export type Stance = "has" | "has_not" | "shared" | "none";
export type ClaimTaskResult =
  { kind: "ready"; task: ClaimTask } | { kind: "missing" } | { kind: "error" };

export const STANCE_TEXT: Record<Stance, string> = {
  has: "دارد",
  has_not: "ندارد",
  shared: "مشاع است",
  none: "چیزی نمی‌گوید",
};
export const STANCES: Stance[] = ["none", "has", "has_not", "shared"];

/** Every feature with a stance: those not set yet say nothing. */
export function completeStances(
  features: string[],
  current: Record<string, Stance | undefined>,
): Record<string, Stance> {
  return Object.fromEntries(features.map((f) => [f, current[f] ?? "none"]));
}

export async function fetchClaimTask(
  baseUrl: string,
  queue: string,
  labeler: string,
  position?: number,
): Promise<ClaimTaskResult> {
  const params = new URLSearchParams({ queue, labeler });
  if (position !== undefined) params.set("position", String(position));
  try {
    const response = await fetch(`${baseUrl}/claim-labels/task?${params}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 404) return { kind: "missing" };
    if (!response.ok) return { kind: "error" };
    return { kind: "ready", task: (await response.json()) as ClaimTask };
  } catch {
    return { kind: "error" };
  }
}
