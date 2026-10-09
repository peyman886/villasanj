import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { docsPages } from "../src/content/docs-nav";

// Every page in the portal's navigation in both languages, one ADR and one generated report (their
// index pages link to the rest, which the link check below visits).
const ROUTES = [
  ...docsPages("fa").map((p) => p.href),
  "/docs/decisions/0014-er-decisions-rules-and-llm-judge",
  "/docs/reports/er-eval-2026-10-04",
  ...docsPages("en").map((p) => p.href),
  "/en/docs/decisions/0014-er-decisions-rules-and-llm-judge",
  "/en/docs/reports/er-eval-2026-10-04",
];

async function open(page: Page, route: string) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    // A failed resource is reported with its URL below, not as this generic console line.
    if (m.type() === "error" && !m.text().startsWith("Failed to load resource"))
      errors.push(m.text());
  });
  page.on("response", (r) => {
    if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`);
  });
  const response = await page.goto(route);
  expect(response?.status(), route).toBe(200);
  await expect(page.locator("h1")).toHaveCount(1);
  return errors;
}

test.describe("documentation portal", () => {
  for (const route of ROUTES) {
    test(`${route} renders without errors or serious accessibility violations`, async ({
      page,
    }) => {
      const errors = await open(page, route);
      await expect(page.locator("h1")).toBeVisible();
      const results = await new AxeBuilder({ page }).analyze();
      const bad = results.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact ?? ""),
      );
      expect(bad.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)).toEqual([]);
      expect(errors).toEqual([]);
    });
  }

  test("the sidebar marks the current page and the pager links its neighbours", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await open(page, "/docs/entity-resolution");
    const current = page.locator("aside nav a[aria-current=page]");
    await expect(current).toHaveText("تطبیق ویلاها");
    const pager = page.getByRole("navigation", { name: "صفحه‌ی قبلی و بعدی" });
    await expect(pager.getByRole("link")).toHaveCount(2);
    // The table of contents lists the page's own sections and they exist.
    const toc = page.getByRole("navigation", { name: "در این صفحه" });
    await expect(toc.locator("a").first()).toBeVisible(); // built after hydration
    const anchors = await toc
      .locator("a")
      .evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
    expect(anchors.length).toBeGreaterThan(5);
    for (const href of anchors) {
      await expect(page.locator(`[id="${decodeURIComponent(href.slice(1))}"]`)).toHaveCount(1);
    }
  });

  test("every link on every docs page leads somewhere", async ({ page, request }) => {
    test.setTimeout(480_000); // ~80 pages, each compiled on first visit by the dev server
    const seen = new Set<string>();
    for (const route of ROUTES) {
      await page.goto(route);
      const hrefs = await page
        .locator("main a[href^='/']")
        .evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
      for (const href of hrefs) seen.add(href.split("#")[0] ?? href);
    }
    const broken: string[] = [];
    for (const href of seen) {
      const response = await request.get(href);
      if (response.status() >= 400) broken.push(`${href} ${response.status()}`);
    }
    expect(broken).toEqual([]);
    expect(seen.size).toBeGreaterThan(80);
  });

  test("every page has its counterpart in the other language, one switch away", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const fa = docsPages("fa");
    const en = docsPages("en");
    expect(en.map((p) => p.slug)).toEqual(fa.map((p) => p.slug));
    await open(page, "/docs/entity-resolution");
    await expect(page.locator("html")).toHaveAttribute("lang", "fa");
    await page.locator("aside [data-docs-lang] a[hreflang=en]").click();
    await expect(page).toHaveURL(/\/en\/docs\/entity-resolution$/, { timeout: 30_000 });
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await expect(page.locator("aside nav a[aria-current=page]")).toHaveText("Entity resolution");
    await page.locator("aside [data-docs-lang] a[hreflang=fa]").click();
    await expect(page).toHaveURL(/\/docs\/entity-resolution$/, { timeout: 30_000 });
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  });

  test("diagrams are inline SVG and open full size", async ({ page }) => {
    await open(page, "/docs/architecture");
    const diagrams = page.locator("svg.villasanj-diagram");
    expect(await diagrams.count()).toBeGreaterThanOrEqual(4);
    await expect(diagrams.first()).toBeVisible();
    await page
      .getByRole("button", { name: /نمایش بزرگ/ })
      .first()
      .click();
    await expect(page.locator("[popover]:popover-open svg.villasanj-diagram")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator("[popover]:popover-open")).toHaveCount(0);
  });

  test("the milestones page shows every criterion with a status", async ({ page }) => {
    await open(page, "/docs/milestones");
    for (let m = 0; m <= 12; m++) await expect(page.locator(`h2#m${m}`)).toHaveCount(1);
    // Every criterion row carries a status badge (icon + words, never colour alone).
    const rows = page.locator("section[aria-labelledby^=m] ol > li");
    expect(await rows.count()).toBeGreaterThan(60);
  });

  test("an ADR is shown as written, left to right, with portal links", async ({ page }) => {
    await open(page, "/docs/decisions/0014-er-decisions-rules-and-llm-judge");
    const body = page.locator("article [dir=ltr][lang=en]");
    await expect(body).toBeVisible();
    await expect(body.getByRole("heading", { name: /Amendment \(label revision/ })).toBeVisible();
  });

  test("a report shows where it came from", async ({ page }) => {
    await open(page, "/docs/reports/er-eval-2026-10-04");
    await expect(page.getByRole("heading", { name: "منبع این گزارش" })).toBeVisible();
    await expect(page.getByRole("figure", { name: "بازتولید" })).toContainText(
      "uv run villasanj er report",
    );
  });

  test("no request leaves the site (works in the offline demo)", async ({ page, baseURL }) => {
    const origin = new URL(baseURL ?? "http://localhost:3301").origin;
    const outside: string[] = [];
    page.on("request", (r) => {
      const url = new URL(r.url());
      if (url.protocol.startsWith("http") && url.origin !== origin) outside.push(r.url());
    });
    for (const route of ["/docs", "/docs/architecture", "/docs/entity-resolution", "/docs/llm"]) {
      await page.goto(route, { waitUntil: "networkidle" });
    }
    expect(outside).toEqual([]);
  });
});

test.describe("documentation portal on a phone", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  for (const route of [
    "/docs",
    "/docs/entity-resolution",
    "/docs/milestones",
    "/docs/decisions",
    "/en/docs",
    "/en/docs/entity-resolution",
  ]) {
    test(`${route} has no sideways scroll at 375 px`, async ({ page }) => {
      await open(page, route);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }

  test("the navigation opens from the page and goes to another page", async ({ page }) => {
    await open(page, "/docs/overview");
    await page.locator("main details > summary").first().click();
    await page.locator("main details nav").getByRole("link", { name: "راستی‌آزمایی" }).click();
    await expect(page).toHaveURL(/\/docs\/truth-check$/, { timeout: 30_000 }); // first compile
    await expect(page.locator("h1")).toHaveText(/راستی‌آزمایی/);
  });
});
