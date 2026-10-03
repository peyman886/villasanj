import { open, stat } from "node:fs/promises";
import path from "node:path";

import { basemapDir, CONTENT_TYPES, parseRange, resolveInside } from "@/lib/basemap";

/** Serves the offline basemap files, with byte ranges (PMTiles reads its archive in ranges). */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const parts = (await params).path;
  const file = resolveInside(basemapDir(), parts);
  const type = file ? CONTENT_TYPES[path.extname(file)] : undefined;
  if (!file || !type) return new Response(null, { status: 404 });
  let size: number;
  try {
    const info = await stat(file);
    if (!info.isFile()) return new Response(null, { status: 404 });
    size = info.size;
  } catch {
    return new Response(null, { status: 404 });
  }
  const headers = {
    "content-type": type,
    "accept-ranges": "bytes",
    // Builds are dated file names, so a file never changes in place.
    "cache-control": "public, max-age=86400",
  };
  const range = parseRange(request.headers.get("range"), size);
  if (range === "invalid") {
    return new Response(null, { status: 416, headers: { "content-range": `bytes */${size}` } });
  }
  const start = range?.start ?? 0;
  const end = range?.end ?? size - 1;
  const handle = await open(file, "r");
  try {
    const buffer = Buffer.alloc(end - start + 1);
    await handle.read(buffer, 0, buffer.length, start);
    return new Response(new Uint8Array(buffer), {
      status: range ? 206 : 200,
      headers: {
        ...headers,
        "content-length": String(buffer.length),
        ...(range ? { "content-range": `bytes ${start}-${end}/${size}` } : {}),
      },
    });
  } finally {
    await handle.close();
  }
}
