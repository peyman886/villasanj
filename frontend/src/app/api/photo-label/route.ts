import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/health";

/** Proxy a photo label to the API (it validates the queue and the tags). */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const response = await fetch(`${apiBaseUrl()}/photo-labels`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "api unreachable" }, { status: 502 });
  }
}
