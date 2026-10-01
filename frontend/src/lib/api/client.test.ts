import { describe, expect, it } from "vitest";

import { apiClient, type Offer } from "./client";

describe("apiClient", () => {
  it("builds typed requests from the OpenAPI paths", async () => {
    const seen: string[] = [];
    const offer = { status: "bookable", kind: "open" } as Offer;
    const fake = async (input: Request | string | URL) => {
      seen.push(input instanceof Request ? input.url : String(input));
      return new Response(JSON.stringify(offer), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    const client = apiClient("http://api.test", fake as typeof fetch);
    const { data } = await client.GET("/listings/{platform}/{external_id}/offer", {
      params: {
        path: { platform: "jabama", external_id: "1" },
        query: { check_in: "2026-10-15", check_out: "2026-10-17", guests: 4 },
      },
    });
    expect(seen[0]).toBe(
      "http://api.test/listings/jabama/1/offer?check_in=2026-10-15&check_out=2026-10-17&guests=4",
    );
    expect(data?.kind).toBe("open");
  });
});
