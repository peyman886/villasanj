import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/health";

/** Proxy a label to the API (it validates the pair, the queue and the label). */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const response = await fetch(`${apiBaseUrl()}/er/labels`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "api unreachable" }, { status: 502 });
  }
}
