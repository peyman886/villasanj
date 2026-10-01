import { describe, expect, it } from "vitest";

import { faDistance, faNumber, faPropertyType, isLabelTask, shortcutFor } from "./labeling";

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
