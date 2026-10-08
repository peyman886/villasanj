/**
 * The villa gallery without duplicates (M12 1.7, decisions.md D6): the same living room shown by
 * both platforms appears once. Photos are compared by the matcher's own perceptual hashes; a
 * photo whose hash is within DISPLAY_HAMMING bits of one already kept is dropped. Photos without
 * a hash (beyond the first five per listing, which are the ones fingerprinted) are kept unless
 * the same URL was already kept. Dropping is the only change: nothing is reordered or added.
 */

import type { components } from "@/lib/api/schema";
import { platformRank } from "@/lib/platforms";

export type GalleryPhoto = components["schemas"]["GalleryPhotoOut"];

/** The matcher's "close photo" bound (WEAK_HAMMING in entity_resolution/domain/evidence.py). */
export const DISPLAY_HAMMING = 10;

export function hamming(a: string, b: string): number {
  let x = BigInt(`0x${a}`) ^ BigInt(`0x${b}`);
  let bits = 0;
  while (x > 0n) {
    bits += Number(x & 1n);
    x >>= 1n;
  }
  return bits;
}

/** Photos in platform order (jabama first), each listing's own order kept, duplicates dropped. */
export function dedupeGallery(photos: GalleryPhoto[], threshold = DISPLAY_HAMMING): GalleryPhoto[] {
  const ordered = photos
    .map((photo, index) => ({ photo, index }))
    .sort(
      (a, b) =>
        platformRank(a.photo.platform) - platformRank(b.photo.platform) || a.index - b.index,
    )
    .map((x) => x.photo);
  const kept: GalleryPhoto[] = [];
  const urls = new Set<string>();
  for (const photo of ordered) {
    if (urls.has(photo.url)) continue;
    const hash = photo.phash;
    if (hash && kept.some((k) => k.phash && hamming(k.phash, hash) <= threshold)) continue;
    kept.push(photo);
    urls.add(photo.url);
  }
  return kept;
}
