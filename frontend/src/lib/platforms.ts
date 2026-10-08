/**
 * Platform order and colours (docs/ux/decisions.md D8.3). jabama always comes before shab: the
 * top half of a calendar day, the first column, the first row when prices are equal. The colours
 * are ours, never the platforms' own, and always sit next to the platform's name.
 */

export const PLATFORM_ORDER = ["jabama", "shab"] as const;

export function platformRank(platform: string): number {
  const index = (PLATFORM_ORDER as readonly string[]).indexOf(platform);
  return index < 0 ? PLATFORM_ORDER.length : index;
}

/** Tailwind classes per platform: a solid swatch, a soft fill and the text colour. */
export const PLATFORM_TONE: Record<string, { solid: string; soft: string; text: string }> = {
  jabama: { solid: "bg-jabama", soft: "bg-jabama-soft", text: "text-jabama" },
  shab: { solid: "bg-shab", soft: "bg-shab-soft", text: "text-shab" },
};

export function toneOf(platform: string) {
  return PLATFORM_TONE[platform] ?? { solid: "bg-sand-500", soft: "bg-sand-100", text: "text-fg" };
}
