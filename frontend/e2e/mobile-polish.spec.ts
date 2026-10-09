import { expect, test, type Page } from "@playwright/test";

// M12 wave 3: phones, and copy and motion polish across the product pages.
const QUERY = "ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد زیر ۲۰ میلیون";
const SEARCH = `/search?${new URLSearchParams({ q: QUERY })}`;
const VILLA = "/villas/v-6331f454983f?in=2026-10-15&out=2026-10-17&guests=6";

test.describe("phones (390×844)", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test.describe.configure({ timeout: 120_000 });

  test("the map button stays visible and the list keeps its place (3.1)", async ({ page }) => {
    await page.goto(SEARCH);
    await expect(page.locator("#results-title")).toBeVisible();
    const button = page.locator("[data-map-button]");
    await expect(button).toBeInViewport();
    await page.mouse.wheel(0, 1600);
    await page.waitForTimeout(300);
    await expect(button).toBeInViewport();
    const y = await page.evaluate(() => scrollY);
    expect(y).toBeGreaterThan(500);
    await button.click();
    await expect(page.getByRole("dialog", { name: "نقشه‌ی نتایج" })).toBeVisible();
    await page.locator("[data-list-button]").click();
    await expect(page.getByRole("dialog", { name: "نقشه‌ی نتایج" })).toHaveCount(0);
    expect(Math.abs((await page.evaluate(() => scrollY)) - y)).toBeLessThan(5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBe(0);
  });

  test("the villa's booking card becomes a bottom bar (3.3)", async ({ page }) => {
    await page.goto(VILLA);
    const bar = page.locator("[data-mobile-booking]");
    await expect(bar).toBeInViewport();
    await expect(bar).toContainText(/از [۰-۹]/);
    await bar.getByRole("link", { name: "مقایسه‌ی پیشنهادها" }).click();
    await expect(page.locator("#booking")).toBeInViewport();
  });
});

test.describe("desktop map", () => {
  test.use({ viewport: { width: 1536, height: 864 } });
  test.describe.configure({ timeout: 120_000 });

  test("moving the map offers «جست‌وجو در همین محدوده», which becomes a chip (3.2)", async ({
    page,
  }) => {
    await page.goto(SEARCH);
    const map = page.locator("[data-search-map]");
    await expect(map.locator("canvas")).toBeVisible({ timeout: 20_000 });
    await expect(page.locator("[data-search-area]")).toHaveCount(0);
    const box = await map.boundingBox();
    if (!box) throw new Error("no map");
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 40, { steps: 8 });
    await page.mouse.up();
    await page.locator("[data-search-area]").click();
    await expect(page).toHaveURL(/area=/, { timeout: 30_000 });
    await expect(page.getByRole("link", { name: "حذف «محدوده‌ی نقشه»" })).toBeVisible();
  });
});

async function visibleText(page: Page): Promise<string> {
  return page.locator("body").innerText();
}

test.describe("copy and motion polish (3.4)", () => {
  test.describe.configure({ timeout: 120_000 });
  for (const path of ["/", SEARCH, VILLA]) {
    test(`no detached «می » or « ها» on ${path.split("?")[0]}`, async ({ page }) => {
      await page.goto(path);
      await expect(page.locator("h1")).toBeAttached();
      const text = await visibleText(page);
      expect(text.match(/(^|[\s«(])(ن?می) (?=[؀-ۿ])/gm) ?? []).toEqual([]);
      expect(text.match(/[؀-ۿ] (ها|های|هایی)(?=[\s.،؛:!؟)»]|$)/gm) ?? []).toEqual([]);
    });

    test(`with reduced motion nothing animates longer than 200 ms on ${path.split("?")[0]}`, async ({
      page,
    }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto(path);
      await expect(page.locator("h1")).toBeAttached();
      const long = await page.evaluate(() =>
        document
          .getAnimations()
          .map((a) => {
            const t = a.effect?.getComputedTiming();
            return Number(t?.duration ?? 0) + Number(t?.delay ?? 0);
          })
          .filter((ms) => ms > 200),
      );
      expect(long).toEqual([]);
    });
  }
});
