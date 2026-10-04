import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { expectProvenanceOn } from "./provenance";

// A villa on both platforms (override with E2E_VILLA); its listing pages link to it.
const VILLA = process.env.E2E_VILLA ?? "v-006f26706d5e";

test.describe("villa page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/villas/${VILLA}`);
    await expect(page.locator("h1")).toBeVisible();
  });

  test("each platform keeps its own prices and nights (rule 3, M7)", async ({ page }) => {
    const rows = page.locator("[aria-labelledby=offers-title] tbody tr");
    await expect(rows.first()).toBeVisible();
    const header = page.locator("[aria-labelledby=calendar-title] thead th");
    await expect(header).toHaveCount(4); // night, two platforms, hidden flag
  });

  test("ten random numbers open their provenance (M7 criterion 3)", async ({ page }) => {
    expect(await expectProvenanceOn(page, 10)).toBe(10);
  });

  test("no serious or critical accessibility violations (M7 criterion 4)", async ({ page }) => {
    const results = await new AxeBuilder({ page }).analyze();
    const bad = results.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""));
    expect(bad.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });

  test("a member listing links back to the villa", async ({ page }) => {
    await page.locator("main a[href^='/listings/']").first().click();
    await expect(page).toHaveURL(/\/listings\//);
    const back = page.getByRole("link", { name: "صفحه‌ی ویلا" });
    await expect(back).toHaveAttribute("href", `/villas/${VILLA}`);
  });
});
