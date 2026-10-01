import { describe, expect, it } from "vitest";

import { isHealthOut, toHealthView, type HealthOut } from "./health";

const healthy: HealthOut = {
  status: "ok",
  summary: "db=ok blob=ok llm=avalai-ok",
  checks: {
    db: { ok: true, detail: "ok" },
    blob: { ok: true, detail: "ok" },
    llm: { ok: true, detail: "avalai-ok" },
  },
};

describe("isHealthOut", () => {
  it("accepts the API shape", () => {
    expect(isHealthOut(healthy)).toBe(true);
  });

  it.each([null, "ok", { status: "fine" }, { ...healthy, checks: { db: { ok: "yes" } } }])(
    "rejects malformed payload %#",
    (payload) => {
      expect(isHealthOut(payload)).toBe(false);
    },
  );
});

describe("toHealthView", () => {
  it("labels known probes in Persian and keeps unknown keys", () => {
    const view = toHealthView({
      ...healthy,
      status: "degraded",
      checks: { ...healthy.checks, osrm: { ok: false, detail: "down" } },
    });
    expect(view.kind).toBe("degraded");
    expect(view.rows.map((row) => row.label)).toEqual([
      "پایگاه داده",
      "ذخیره‌ساز فایل",
      "مدل زبانی",
      "osrm",
    ]);
  });

  it("represents an unreachable API explicitly", () => {
    expect(toHealthView(null)).toEqual({ kind: "unreachable", rows: [] });
  });
});
