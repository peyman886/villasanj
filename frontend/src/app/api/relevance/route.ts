import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/health";

/** Proxy a relevance grade (the API checks the villa is in that query's pool). */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const response = await fetch(`${apiBaseUrl()}/reviews/relevance`, {
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
