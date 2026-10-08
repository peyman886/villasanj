import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { expectProvenanceOn } from "./provenance";

// A listing with offers, calendar nights and reviews in the demo data (override with E2E_LISTING).
const LISTING = process.env.E2E_LISTING ?? "jabama/342085";

test.describe("listing page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/listings/${LISTING}`);
    await expect(page.locator("h1")).toBeVisible();
  });

  test("ten random numbers each open their provenance (M7 criterion 3)", async ({ page }) => {
    expect(await expectProvenanceOn(page, 10)).toBe(10);
  });

  test("claims sit beside their evidence in calm words (M9)", async ({ page }) => {
    const section = page.locator("[aria-labelledby=claims-title]");
    await expect(section).toBeVisible();
    await expect(section.locator("li").first()).toBeVisible();
    for (const word of ["دروغ", "تقلب", "نادرست است", "غلط"]) {
      await expect(section.locator("li", { hasText: word })).toHaveCount(0);
    }
  });

  test("no serious or critical accessibility violations (M7 criterion 4)", async ({ page }) => {
    const results = await new AxeBuilder({ page }).analyze();
    const critical = results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact ?? ""),
    );
    expect(critical.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });

  test("calendar nights work with the keyboard (M7 criterion 4)", async ({ page }) => {
    const night = page.locator("table [data-sourced]").first();
    await night.focus();
    await page.keyboard.press("Enter");
    const id = await night.getAttribute("popovertarget");
    const card = page.locator(`[id="${id}"]`);
    await expect(card).toBeVisible();
    await page.keyboard.press("Tab");
    expect(await card.evaluate((el) => el.contains(document.activeElement))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(card).toBeHidden();
  });

  test("the page never scrolls sideways on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.reload();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("summary points cite reviews that are on the page (M10)", async ({ page }) => {
    const summary = page.locator("#summary-title");
    await expect(summary).toBeVisible({ timeout: 60_000 }); // streamed after the page
    // Each point's chip filters the list to the reviews it cites (M12 2.4): they must be here.
    const targets = await page
      .locator("[aria-labelledby=summary-title] [data-cite-chip]")
      .evaluateAll((chips) =>
        chips.flatMap((c) => (c.getAttribute("data-anchors") ?? "").split(" ")),
      );
    expect(targets.length).toBeGreaterThan(0);
    for (const target of new Set(targets)) {
      await expect(page.locator(`[id="${target}"]`)).toHaveCount(1);
    }
  });
});
