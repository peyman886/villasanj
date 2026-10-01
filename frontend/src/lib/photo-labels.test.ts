import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchPhotoTask, photoShortcutFor, toggled } from "./photo-labels";

const key = (code: string, extra: Partial<KeyboardEvent> = {}) => ({
  code,
  altKey: false,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  repeat: false,
  ...extra,
});

describe("photo labelling shortcuts", () => {
  it("maps physical keys to toggles, save and navigation", () => {
    expect(photoShortcutFor(key("Digit1"))).toEqual({ kind: "toggle", index: 0 });
    expect(photoShortcutFor(key("Numpad6"))).toEqual({ kind: "toggle", index: 5 });
    expect(photoShortcutFor(key("Enter"))).toEqual({ kind: "save" });
    expect(photoShortcutFor(key("ArrowLeft"))).toEqual({ kind: "next" });
    expect(photoShortcutFor(key("ArrowRight"))).toEqual({ kind: "previous" });
    expect(photoShortcutFor(key("Digit1", { ctrlKey: true }))).toBeNull();
    expect(photoShortcutFor(key("KeyA"))).toBeNull();
  });

  it("toggles a tag in and out", () => {
    expect(toggled(["pool"], "forest")).toEqual(["pool", "forest"]);
    expect(toggled(["pool", "forest"], "pool")).toEqual(["forest"]);
  });
});

describe("fetchPhotoTask", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads a task, a missing queue and a broken answer", async () => {
    const task = { position: 1, total: 2, sha256: "a", url: "u", tags: [], present: [] };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(task), { status: 200 })),
    );
    expect(await fetchPhotoTask("http://api", "photos-v1", "owner")).toEqual({
      kind: "ready",
      task,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 404 })),
    );
    expect(await fetchPhotoTask("http://api", "nope", "owner")).toEqual({ kind: "missing" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
    expect(await fetchPhotoTask("http://api", "photos-v1", "owner", 3)).toEqual({ kind: "error" });
  });
});
