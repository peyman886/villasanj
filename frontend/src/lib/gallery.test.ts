import { describe, expect, it } from "vitest";

import { DISPLAY_HAMMING, dedupeGallery, hamming, type GalleryPhoto } from "@/lib/gallery";

const photo = (url: string, platform: string, phash: string | null): GalleryPhoto => ({
  url,
  platform,
  phash,
});

describe("gallery deduplication", () => {
  it("counts differing bits between two 64-bit hashes", () => {
    expect(hamming("ffffffffffffffff", "ffffffffffffffff")).toBe(0);
    expect(hamming("0000000000000000", "ffffffffffffffff")).toBe(64);
    expect(hamming("00000000000000ff", "0000000000000000")).toBe(8);
  });

  it("drops the other platform's copy of a photo and keeps the rest in order", () => {
    // A fixture villa with a known duplicate: shab's first photo is jabama's living room.
    const gallery = [
      photo("https://s/0.jpg", "shab", "f0f0f0f0f0f0f0f3"), // 2 bits from j/0: a duplicate
      photo("https://s/1.jpg", "shab", "123456789abcdef0"),
      photo("https://j/0.jpg", "jabama", "f0f0f0f0f0f0f0f0"),
      photo("https://j/1.jpg", "jabama", "0f0f0f0f0f0f0f0f"),
      photo("https://j/9.jpg", "jabama", null), // not fingerprinted: kept
      photo("https://j/9.jpg", "jabama", null), // the same URL twice: once
    ];
    const kept = dedupeGallery(gallery);
    expect(kept.map((p) => p.url)).toEqual([
      "https://j/0.jpg",
      "https://j/1.jpg",
      "https://j/9.jpg",
      "https://s/1.jpg",
    ]);
    for (const a of kept) {
      for (const b of kept) {
        if (a !== b && a.phash && b.phash) {
          expect(hamming(a.phash, b.phash)).toBeGreaterThan(DISPLAY_HAMMING);
        }
      }
    }
  });

  it("keeps two photos just beyond the bound", () => {
    const near = dedupeGallery([
      photo("a", "jabama", "0000000000000000"),
      photo("b", "shab", "00000000000007ff"), // 11 bits apart
    ]);
    expect(near).toHaveLength(2);
  });
});
