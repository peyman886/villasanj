/**
 * The offline basemap (ADR-0003 amendment): a Protomaps extract of the region, its glyphs and
 * sprites, prepared by infra/basemap/prepare.sh into BASEMAP_DIR and served by /basemap/*.
 * Without it the listing map falls back to OSM's raster tiles.
 */

import path from "node:path";

export type Basemap = { pmtiles: string; build: string };

export const CONTENT_TYPES: Record<string, string> = {
  ".pmtiles": "application/octet-stream",
  ".pbf": "application/x-protobuf",
  ".json": "application/json",
  ".png": "image/png",
};

export function basemapDir(): string {
  return process.env.BASEMAP_DIR ?? path.join(process.cwd(), "..", "data", "basemap");
}

/** The file a request path names inside ``root``, or null if it would leave it. */
export function resolveInside(root: string, parts: string[]): string | null {
  const base = path.resolve(root);
  const target = path.resolve(base, ...parts);
  return target.startsWith(base + path.sep) ? target : null;
}

/**
 * One byte range of a file of ``size`` bytes (RFC 9110 single range: "bytes=a-b", "bytes=a-",
 * "bytes=-n"); null when absent, "invalid" when it cannot be served (416).
 */
export function parseRange(
  header: string | null,
  size: number,
): { start: number; end: number } | null | "invalid" {
  if (!header) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!match || (match[1] === "" && match[2] === "")) return "invalid";
  let start: number;
  let end: number;
  if (match[1] === "") {
    const suffix = Number(match[2]);
    if (suffix === 0) return "invalid";
    start = Math.max(0, size - suffix);
    end = size - 1;
  } else {
    start = Number(match[1]);
    end = match[2] === "" ? size - 1 : Math.min(Number(match[2]), size - 1);
  }
  if (start > end || start >= size) return "invalid";
  return { start, end };
}

/** The prepared basemap, if any (server side; the listing page passes it to the map). */
export async function readBasemap(): Promise<Basemap | null> {
  const { readFile } = await import("node:fs/promises");
  try {
    const manifest = JSON.parse(
      await readFile(path.join(basemapDir(), "basemap.json"), "utf-8"),
    ) as Partial<Basemap>;
    if (typeof manifest.pmtiles !== "string" || typeof manifest.build !== "string") return null;
    if (resolveInside(basemapDir(), [manifest.pmtiles]) === null) return null;
    return { pmtiles: manifest.pmtiles, build: manifest.build };
  } catch {
    return null;
  }
}
