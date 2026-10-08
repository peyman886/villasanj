import { describe, expect, it } from "vitest";

import { decisionTrail, evidenceLines, type MatchPair } from "@/components/villa/match-evidence";

function pair(overrides: Partial<MatchPair> = {}): MatchPair {
  return {
    left: "jabama:1",
    right: "shab:2",
    photo_pairs: [],
    photos_compared: [5, 5],
    strong_photo_matches: 3,
    weak_photo_matches: 0,
    distance_min_m: 0,
    bedrooms: [2, 2],
    max_capacity: [8, 8],
    area_m2: [356, 130],
    title_similarity: 0.6,
    rule_score: 8.75,
    threshold: -0.25,
    rules_match: true,
    contributions: { shared_photos: 6.25 },
    judge: null,
    human: null,
    ...overrides,
  };
}

describe("match evidence maps to stored ER fields only", () => {
  it("each line comes from one recorded field", () => {
    const lines = evidenceLines(pair());
    expect(lines.map((l) => l.key)).toEqual(["distance", "bedrooms", "capacity"]);
    expect(lines.map((l) => l.text)).toEqual([
      "محدوده‌ی تقریبی دو آگهی روی نقشه روی هم می‌افتد",
      "هر دو آگهی: ۲ خوابه",
      "ظرفیت: ۸ و ۸ نفر",
    ]);
  });

  it("missing fields give no line, differing ones say both values", () => {
    const lines = evidenceLines(
      pair({ distance_min_m: null, bedrooms: [2, 3], max_capacity: [null, 8] }),
    );
    expect(lines).toEqual([{ key: "bedrooms", text: "تعداد خواب: ۲ و ۳" }]);
    expect(evidenceLines(pair({ distance_min_m: 430 }))[0]?.text).toBe(
      "محدوده‌ی تقریبی دو آگهی دست‌کم ۴۰۰ متر از هم فاصله دارد",
    );
  });

  it("the decision trail says who decided and nothing more", () => {
    expect(decisionTrail(pair()).map((s) => [s.key, s.state])).toEqual([
      ["rules", "yes"],
      ["judge", "none"],
      ["human", "none"],
    ]);
    const judged = decisionTrail(
      pair({
        rules_match: false,
        judge: { verdict: "match", confidence: 0.9, evidence: ["same_interior", "new_code"] },
        human: "match",
      }),
    );
    expect(judged.map((s) => s.state)).toEqual(["no", "yes", "yes"]);
    expect(judged[1]?.detail).toBe("همان ویلاست: فضای داخلی یکسان، new_code");
    expect(decisionTrail(pair({ rule_score: null }))[0]?.state).toBe("none");
  });
});
