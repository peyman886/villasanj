/**
 * The truth check as the M12 pages show it (2.1): claims grouped by what we can say about them,
 * and the 3 to 5 verified facts that become highlights. Only verified facts are highlights: a
 * claim the map or the photos support, a measured distance, and the platforms' own ratings.
 */

import type { Claims } from "@/lib/api/client";

export type Group = "verified" | "not_verified" | "map_disagrees" | "not_checked";

export const GROUP_TEXT: Record<Group, string> = {
  verified: "تأیید شد",
  not_verified: "تأیید نشد",
  map_disagrees: "با نقشه نمی‌خواند",
  not_checked: "بررسی نشد",
};

export const GROUP_ORDER: Group[] = ["verified", "not_verified", "map_disagrees", "not_checked"];

/** Which group a verdict belongs to; only «supported» is verified (A18: the host's word is not). */
export function groupOf(verdict: string): Group {
  switch (verdict) {
    case "supported":
      return "verified";
    case "contradicted":
      return "map_disagrees";
    case "not_checked":
      return "not_checked";
    default:
      return "not_verified"; // not_confirmed, consistent, shared, inconsistent
  }
}

type Distance = Claims["distances"][number];
type Feature = Claims["features"][number];

export type Highlight = {
  key: string;
  kind: "feature" | "distance";
  text: string;
  source: string; // «در عکس‌ها دیده شد», «روی نقشه تأیید شد»
};

const TARGET_PRIORITY = ["sea", "forest", "city_center", "supermarket", "restaurant", "bakery"];

/**
 * Up to ``max`` verified claims across the villa's listings: supported features first (seen in
 * the photos), then supported distances by how much a traveller cares about the target, one per
 * target. A claim several listings make appears once.
 */
export function verifiedHighlights(
  sources: { platformName: string; claims: Claims | null }[],
  featureText: (feature: string) => string,
  max = 3,
): Highlight[] {
  const features: Highlight[] = [];
  const distances: { target: string; claim: Distance }[] = [];
  const seenFeatures = new Set<string>();
  for (const { claims } of sources) {
    for (const f of claims?.features ?? []) {
      if (f.verdict !== "supported" || f.polarity !== "has" || seenFeatures.has(f.feature))
        continue;
      seenFeatures.add(f.feature);
      features.push(featureHighlight(f, featureText));
    }
    for (const d of claims?.distances ?? []) {
      if (d.verdict === "supported") distances.push({ target: d.target, claim: d });
    }
  }
  const byTarget = new Map<string, Distance>();
  for (const { target, claim } of distances) if (!byTarget.has(target)) byTarget.set(target, claim);
  const ranked = [...byTarget.entries()]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([target, claim]) => ({
      key: `distance-${target}`,
      kind: "distance" as const,
      text: claim.text.replace(/^فاصله از\s*/, "").replace(/:\s*/, ": "),
      source: "روی نقشه تأیید شد",
    }));
  return [...features, ...ranked].slice(0, max);
}

function rank(target: string): number {
  const i = TARGET_PRIORITY.indexOf(target);
  return i < 0 ? TARGET_PRIORITY.length : i;
}

function featureHighlight(f: Feature, featureText: (feature: string) => string): Highlight {
  return {
    key: `feature-${f.feature}`,
    kind: "feature",
    text: featureText(f.feature),
    // A feature is supported either by the map (near the sea, ADR-0013) or by its photos (A21).
    source: f.feature === "near_sea" ? "روی نقشه تأیید شد" : "در عکس‌ها دیده شد",
  };
}
