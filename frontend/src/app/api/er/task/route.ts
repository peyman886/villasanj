import { type NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/health";
import { fetchTask } from "@/lib/labeling";

/** Proxy to the API's labelling queue, so the browser talks to one origin. */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const params = request.nextUrl.searchParams;
  const raw = params.get("position");
  const position = raw === null ? undefined : Number.parseInt(raw, 10);
  const result = await fetchTask(
    apiBaseUrl(),
    params.get("queue") ?? "gold-v1",
    params.get("labeler") ?? "owner",
    Number.isNaN(position) ? undefined : position,
  );
  return NextResponse.json(result, { status: result.kind === "error" ? 502 : 200 });
}
