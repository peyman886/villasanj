import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { expectProvenanceOn } from "./provenance";

// One live query (its intent and explanation are cached after the first run).
const QUERY =
  process.env.E2E_QUERY ?? "ویلای استخردار در رامسر برای ۶ نفر آخر هفته بعد زیر ۲۰ میلیون";

test.describe("search page", () => {
  // The first request can wait on the LLM (understanding, explanation) and a cold dev compile.
  test.describe.configure({ timeout: 120_000 });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/search?${new URLSearchParams({ q: QUERY })}`);
    await expect(page.getByRole("heading", { name: /آگهی مناسب/ })).toBeVisible();
  });

  test("results, the explanation and the budget question are shown", async ({ page }) => {
    await expect(page.locator("ol > li").first()).toBeVisible();
    // The explanation streams in after the results; uncached it can take several seconds.
    await expect(page.locator("#why-title")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("link", { name: /هر شب/ })).toBeVisible();
  });

  test("numbers in results and explanation open their provenance", async ({ page }) => {
    expect(await expectProvenanceOn(page, 10)).toBe(10);
  });

  test("no serious or critical accessibility violations", async ({ page }) => {
    const results = await new AxeBuilder({ page }).analyze();
    const critical = results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact ?? ""),
    );
    expect(critical.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });

  test("a result links to its listing page", async ({ page }) => {
    const link = page.locator("ol > li a[href^='/listings/']").first();
    const href = await link.getAttribute("href");
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    await expect(page.locator("h1")).toBeVisible();
  });

  test("removing a chip searches again without it, and everything can be restored", async ({
    page,
  }) => {
    const before = await page.getByRole("heading", { name: /آگهی مناسب/ }).textContent();
    await page.getByRole("link", { name: "حذف «استخر» و جستجوی دوباره" }).click();
    // A new search can wait on an uncached explanation: allow for it.
    await expect(page).toHaveURL(/drop=feature%3Apool/, { timeout: 30_000 });
    await expect(page.getByRole("link", { name: "حذف «استخر» و جستجوی دوباره" })).toHaveCount(0);
    const after = await page.getByRole("heading", { name: /آگهی مناسب/ }).textContent();
    expect(after).not.toBe(before); // no pool required: more listings
    await page.getByRole("link", { name: "بازگرداندن همه‌ی شرط‌ها" }).click();
    await expect(page.getByRole("link", { name: "حذف «استخر» و جستجوی دوباره" })).toBeVisible({
      timeout: 30_000,
    });
  });
});
