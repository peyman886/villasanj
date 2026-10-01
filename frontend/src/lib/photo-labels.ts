/** Photo-tag labelling (M9 criterion 2): the task shape, its fetch and the keyboard shortcuts. */

import type { components } from "@/lib/api/schema";

export type PhotoTask = components["schemas"]["PhotoTaskOut"];
export type PhotoTag = components["schemas"]["TagOut"]["code"];
export type PhotoTaskResult =
  { kind: "ready"; task: PhotoTask } | { kind: "missing" } | { kind: "error" };

export type PhotoShortcut =
  { kind: "toggle"; index: number } | { kind: "save" } | { kind: "previous" } | { kind: "next" };

type KeyLike = {
  code: string;
  altKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  repeat: boolean;
};

/**
 * Physical keys (they work on a Persian layout too): 1-6 toggle a tag, Enter saves and moves on.
 * The page reads right to left, so ArrowLeft moves forward and ArrowRight moves back.
 */
export function photoShortcutFor(event: KeyLike): PhotoShortcut | null {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat) return null;
  const digit = /^(?:Digit|Numpad)([1-9])$/.exec(event.code);
  if (digit) return { kind: "toggle", index: Number(digit[1]) - 1 };
  if (event.code === "Enter" || event.code === "NumpadEnter") return { kind: "save" };
  if (event.code === "ArrowLeft") return { kind: "next" };
  if (event.code === "ArrowRight") return { kind: "previous" };
  return null;
}

export function toggled(present: PhotoTag[], tag: PhotoTag): PhotoTag[] {
  return present.includes(tag) ? present.filter((t) => t !== tag) : [...present, tag];
}

function isPhotoTask(value: unknown): value is PhotoTask {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.position === "number" &&
    typeof v.total === "number" &&
    typeof v.sha256 === "string" &&
    typeof v.url === "string" &&
    Array.isArray(v.tags) &&
    Array.isArray(v.present)
  );
}

export async function fetchPhotoTask(
  baseUrl: string,
  queue: string,
  labeler: string,
  position?: number,
): Promise<PhotoTaskResult> {
  const params = new URLSearchParams({ queue, labeler });
  if (position !== undefined) params.set("position", String(position));
  try {
    const response = await fetch(`${baseUrl}/photo-labels/task?${params}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 404) return { kind: "missing" };
    const body: unknown = await response.json();
    return response.ok && isPhotoTask(body) ? { kind: "ready", task: body } : { kind: "error" };
  } catch {
    return { kind: "error" };
  }
}
