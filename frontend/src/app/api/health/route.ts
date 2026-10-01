import { NextResponse } from "next/server";

import { apiBaseUrl, fetchHealth } from "@/lib/health";

/** End-to-end health: web server -> API -> database, blob store, LLM provider. */
export async function GET(): Promise<NextResponse> {
  const health = await fetchHealth(apiBaseUrl());
  if (health === null) {
    return NextResponse.json(
      { status: "unreachable", summary: "web=ok api=unreachable" },
      { status: 502 },
    );
  }
  return NextResponse.json(
    { ...health, summary: `web=ok ${health.summary}` },
    { status: health.status === "ok" ? 200 : 503 },
  );
}
