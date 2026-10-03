import { describe, expect, it } from "vitest";

import { parseRange, resolveInside } from "./basemap";

describe("basemap files", () => {
  it("serves one byte range, as RFC 9110 reads it", () => {
    expect(parseRange(null, 100)).toBeNull();
    expect(parseRange("bytes=0-9", 100)).toEqual({ start: 0, end: 9 });
    expect(parseRange("bytes=90-", 100)).toEqual({ start: 90, end: 99 });
    expect(parseRange("bytes=-10", 100)).toEqual({ start: 90, end: 99 });
    expect(parseRange("bytes=50-500", 100)).toEqual({ start: 50, end: 99 });
    expect(parseRange("bytes=100-", 100)).toBe("invalid");
    expect(parseRange("bytes=9-0", 100)).toBe("invalid");
    expect(parseRange("bytes=0-1,4-5", 100)).toBe("invalid");
  });

  it("never leaves the basemap directory", () => {
    expect(resolveInside("/srv/basemap", ["fonts", "Noto Sans Regular", "0-255.pbf"])).toBe(
      "/srv/basemap/fonts/Noto Sans Regular/0-255.pbf",
    );
    expect(resolveInside("/srv/basemap", ["..", "secret"])).toBeNull();
    expect(resolveInside("/srv/basemap", ["fonts", "..", "..", "etc"])).toBeNull();
    expect(resolveInside("/srv/basemap", [])).toBeNull();
  });
});
