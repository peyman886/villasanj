import { describe, expect, it, vi } from "vitest";

import {
  faDistance,
  faNumber,
  faPropertyType,
  isLabelTask,
  shortcutFor,
  fetchTask,
} from "./labeling";
import { completeStances } from "./claim-labels";
import { verdictFor } from "./summary-reviews";

const key = (code: string, extra: Partial<Record<string, boolean>> = {}) => ({
  code,
  altKey: false,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  repeat: false,
  ...extra,
});

describe("shortcutFor", () => {
  it("maps physical keys to labels, whatever the layout", () => {
    expect(shortcutFor(key("KeyM"))).toEqual({ kind: "label", label: "match" });
    expect(shortcutFor(key("KeyN"))).toEqual({ kind: "label", label: "non_match" });
    expect(shortcutFor(key("KeyU"))).toEqual({ kind: "label", label: "unsure" });
  });

  it("moves forward with ArrowLeft because the page is right to left", () => {
    expect(shortcutFor(key("ArrowLeft"))).toEqual({ kind: "next" });
    expect(shortcutFor(key("ArrowRight"))).toEqual({ kind: "previous" });
  });

  it("ignores modified, repeated and unknown keys", () => {
    expect(shortcutFor(key("KeyM", { metaKey: true }))).toBeNull();
    expect(shortcutFor(key("KeyM", { repeat: true }))).toBeNull();
    expect(shortcutFor(key("KeyQ"))).toBeNull();
  });
});

describe("formatting", () => {
  it("writes Persian digits and says when a value is unknown", () => {
    expect(faNumber(3250000, " تومان")).toBe("۳٬۲۵۰٬۰۰۰ تومان");
    expect(faNumber(null)).toBe("نامشخص");
  });

  it("translates known property types and keeps unknown ones as published", () => {
    expect(faPropertyType("cottage")).toBe("کلبه");
    expect(faPropertyType("treehouse")).toBe("treehouse");
    expect(faPropertyType(null)).toBe("نامشخص");
  });

  it("describes distances with and without an obfuscation radius", () => {
    expect(faDistance(null)).toContain("منتشر نشده");
    expect(faDistance({ centre_m: 120, min_m: 120, max_m: 120 })).not.toContain("دست‌کم");
    expect(faDistance({ centre_m: 445.2, min_m: 45.2, max_m: null })).toContain("۴۵");
  });
});

describe("isLabelTask", () => {
  const card = { id: "a:1", title: "t", url: "https://x.test", photos: [] };
  const task = {
    pair: "a:1|b:2",
    position: 0,
    total: 3,
    labeled: 0,
    current_label: null,
    left: card,
    right: card,
  };

  it("accepts the API shape and rejects anything else", () => {
    expect(isLabelTask(task)).toBe(true);
    expect(isLabelTask({ ...task, current_label: "maybe" })).toBe(false);
    expect(isLabelTask({ ...task, left: null })).toBe(false);
    expect(isLabelTask(null)).toBe(false);
  });
});

describe("fetchTask", () => {
  it("tells a queue not drawn yet from a finished one", async () => {
    const answer = (status: number) =>
      vi.fn(async () => new Response(status === 204 ? null : "{}", { status }));
    vi.stubGlobal("fetch", answer(404));
    expect(await fetchTask("http://api", "gold-v1", "owner")).toEqual({ kind: "missing" });
    expect(await fetchTask("http://api", "gold-v1", "owner", 7)).toEqual({ kind: "error" });
    vi.stubGlobal("fetch", answer(204));
    expect(await fetchTask("http://api", "gold-v1", "owner")).toEqual({ kind: "done" });
    vi.unstubAllGlobals();
  });
});

describe("verdictFor", () => {
  const press = (code: string, extra: Partial<KeyboardEvent> = {}) => ({
    code,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    ...extra,
  });
  it("reads physical Y and N, and nothing with a modifier", () => {
    expect(verdictFor(press("KeyY"))).toBe(true);
    expect(verdictFor(press("KeyN"))).toBe(false);
    expect(verdictFor(press("KeyY", { metaKey: true }))).toBeNull();
    expect(verdictFor(press("KeyM"))).toBeNull();
  });
});

describe("completeStances", () => {
  it("fills every feature, keeping what was said", () => {
    expect(completeStances(["pool", "parking"], { pool: "has" })).toEqual({
      pool: "has",
      parking: "none",
    });
  });
});
