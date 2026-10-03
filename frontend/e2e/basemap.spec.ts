import { expect, test } from "@playwright/test";

const LISTING = process.env.E2E_LISTING ?? "jabama/342085";

// M11 criterion 1 (offline demo): with a prepared basemap the listing map loads no external
// tiles. Skipped where `make basemap` was not run (the map then uses OSM's raster tiles).
test("the listing map uses the local basemap when it is prepared", async ({ page, request }) => {
  const manifest = await request.get("/basemap/basemap.json");
  test.skip(!manifest.ok(), "no local basemap (make basemap)");
  const external: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("tile.openstreetmap.org")) external.push(r.url());
  });
  const local = page.waitForResponse((r) => r.url().includes(".pmtiles") && r.status() === 206);
  await page.goto(`/listings/${LISTING}`);
  await page.locator(".maplibregl-canvas").scrollIntoViewIfNeeded();
  await local;
  await expect(page.locator(".maplibregl-ctrl-attrib")).toContainText("OpenStreetMap");
  expect(external).toEqual([]);
});
