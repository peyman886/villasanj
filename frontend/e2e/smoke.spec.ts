import { expect, test } from "@playwright/test";

// M7 criterion 2 at listing level: a deterministic sample of 50 listings across both platforms
// renders without errors (villa pages come with M5). The API gives the sample, so it follows
// the catalog: E2E_API_URL is the API (default the host API on 8801). `make test-smoke` runs it;
// the first run summarises the reviews of listings not summarised yet (real LLM calls, about
// $0.04 for this seed on 2026-10-02), later runs hit the cache.
const API = process.env.E2E_API_URL ?? "http://localhost:8801";
const SAMPLE = Number(process.env.E2E_SAMPLE ?? 50);

type Ref = { platform: string; external_id: string };

test.describe("listing pages smoke", () => {
  test.describe.configure({ timeout: 300_000 });

  test(`@smoke a sample of ${SAMPLE} listings renders without errors (M7 criterion 2)`, async ({
    page,
    request,
  }) => {
    const response = await request.get(`${API}/listings/sample?n=${SAMPLE}&seed=smoke`);
    expect(response.ok()).toBe(true);
    const refs = (await response.json()) as Ref[];
    expect(refs).toHaveLength(SAMPLE);
    const failures: string[] = [];
    page.on("pageerror", (error) => failures.push(`${page.url()}: ${error.message}`));
    page.on("console", (message) => {
      // Hotlinked photos may fail on the platform's CDN: that is theirs, not a render error.
      if (message.type() === "error" && !/Failed to load resource/.test(message.text())) {
        failures.push(`${page.url()}: ${message.text()}`);
      }
    });
    for (const ref of refs) {
      const visit = await page.goto(`/listings/${ref.platform}/${ref.external_id}`);
      expect(visit?.status(), `${ref.platform}/${ref.external_id}`).toBe(200);
      await expect(page.locator("h1")).toBeVisible();
      await expect(page.locator("#offers-title")).toBeAttached();
    }
    expect(failures).toEqual([]);
  });
});
