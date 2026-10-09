import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { countVisible, expectCleanCopy } from "./copy";
import { expectProvenanceOn } from "./provenance";

// The demo query (its intent and explanation are cached after the first run).
const QUERY =
  process.env.E2E_QUERY ?? "ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد زیر ۲۰ میلیون";
const URL = `/search?${new URLSearchParams({ q: QUERY })}`;

async function open(page: Page) {
  await page.goto(URL);
  await expect(page.locator("#results-title")).toContainText("ویلا");
}

test.describe("search page", () => {
  // The first request can wait on the LLM (understanding, explanation) and a cold dev compile.
  test.describe.configure({ timeout: 120_000 });

  for (const [width, height] of [
    [1440, 900],
    [1536, 864],
  ] as const) {
    test(`map and the first full card are above the fold at ${width}×${height}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height });
      await open(page);
      const card = await page.locator("[data-result]").first().boundingBox();
      const map = await page.locator("[data-search-map]").boundingBox();
      expect(card && map).toBeTruthy();
      const article = await page.locator("[data-result] article").first().boundingBox();
      expect((article?.y ?? 0) + (article?.height ?? 0)).toBeLessThanOrEqual(height);
      expect(map?.y ?? height).toBeLessThan(height / 2);
      // Nothing between the chip bar and the first card is taller than 80 px (M12 1.3).
      const between = await page
        .locator("section[aria-labelledby=results-title] > :not(ol)")
        .evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
      for (const h of between) expect(h).toBeLessThanOrEqual(80);
    });
  }

  test("cards speak Torob: «از», «در ۲ پلتفرم», each platform's own price", async ({ page }) => {
    await open(page);
    await expect(page.locator("#results-title")).not.toContainText("آگهی");
    const cards = page.locator("[data-result]");
    const count = await cards.count();
    expect(count).toBeGreaterThan(2);
    let multi = 0;
    for (let i = 0; i < count; i += 1) {
      const card = cards.nth(i);
      const text = await card.locator("article").innerText();
      const rows = card.locator("[data-offers] > li");
      if (text.includes("پلتفرم") && /در [۰-۹]+ پلتفرم/.test(text)) {
        multi += 1;
        expect(text).toMatch(/از [۰-۹]/);
        expect(text).toContain("جاباما");
        expect(text).toContain("شب");
      } else {
        expect(text).toMatch(/در (جاباما|شب)/);
        expect(await rows.count()).toBe(0);
      }
    }
    expect(multi).toBeGreaterThan(0);
    await expect(page.getByText("بهترین تطابق")).toHaveCount(1);
    await expect(cards.first().getByText("بهترین تطابق")).toBeVisible();
    expect(await countVisible(page, "کارمزد")).toBe(1);
  });

  test("the explanation streams inside the first card, not above the results", async ({ page }) => {
    await open(page);
    const why = page.locator("[data-result]").first().locator("#why-title");
    await expect(why).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("#why-title")).toHaveCount(1);
  });

  test("hovering a card lights its pin and hovering a pin outlines its card", async ({ page }) => {
    await page.setViewportSize({ width: 1536, height: 864 });
    await open(page);
    const card = page.locator("[data-result]").nth(1);
    const id = await card.getAttribute("data-result");
    const pin = page.locator(`[data-pin="${id}"]`);
    await expect(pin).toBeAttached({ timeout: 15_000 });
    await card.hover();
    const started = Date.now();
    await expect(pin).toHaveAttribute("data-active", "", { timeout: 1_000 });
    expect(Date.now() - started).toBeLessThan(1_000); // measured in-page below, too
    const lag = await page.evaluate(async (pinId) => {
      const el = document.querySelector(`[data-pin="${pinId}"]`);
      const other = document.querySelector("[data-result]:nth-child(3)");
      other?.dispatchEvent(new PointerEvent("pointerover", { bubbles: true }));
      const t0 = performance.now();
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return { off: !el?.hasAttribute("data-active"), ms: performance.now() - t0 };
    }, id);
    expect(lag.off).toBe(true);
    expect(lag.ms).toBeLessThan(100);
    await page.mouse.move(0, 0);
    await pin.dispatchEvent("pointerenter");
    await expect(card).toHaveAttribute("data-active", "");
  });

  test("flipping the budget chip re-ranks without a full reload and keeps the chips", async ({
    page,
  }) => {
    await open(page);
    await page.evaluate(() => ((window as unknown as { kept: number }).kept = 42));
    const chips = await page.locator("section[aria-label='برداشت ما از جستجو'] li").count();
    await page.getByRole("link", { name: /^هر شب/ }).click();
    await expect(page).toHaveURL(/drop=basis%3Aper_night/, { timeout: 30_000 });
    await expect(page.getByRole("link", { name: /^هر شب/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(await page.evaluate(() => (window as unknown as { kept?: number }).kept)).toBe(42);
    expect(await page.locator("section[aria-label='برداشت ما از جستجو'] li").count()).toBe(chips);
  });

  test("the filter panel counts live, applies on the server and becomes removable chips", async ({
    page,
  }) => {
    await open(page);
    await page.locator("[data-filter-button]").click();
    const dialog = page.getByRole("dialog", { name: "فیلترها" });
    await expect(dialog).toBeVisible();
    const apply = dialog.locator("[data-apply-filters]");
    await expect(apply).toHaveText(/نمایش [۰-۹]+ ویلا/, { timeout: 30_000 });
    const before = await apply.textContent();
    await dialog.getByRole("button", { name: /رزرو آنی/ }).click();
    await expect(dialog.getByRole("button", { name: /رزرو آنی/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await dialog.getByRole("radio", { name: /^تا ۱ کیلومتر/ }).click();
    await expect(apply).not.toHaveText(before ?? "");
    const promised = ((await apply.textContent()) ?? "").match(/[۰-۹]+/)?.[0];
    const axe = await new AxeBuilder({ page }).include("dialog[open]").analyze();
    expect(
      axe.violations
        .filter((v) => ["critical", "serious"].includes(v.impact ?? ""))
        .map((v) => v.id),
    ).toEqual([]);
    await apply.click();
    await expect(page).toHaveURL(/instant=1&sea=1000/, { timeout: 30_000 });
    await expect(page.locator("#results-title")).toContainText(`${promised} ویلا`);
    const chips = page.locator("[data-filter-chip]");
    await expect(chips).toHaveCount(2);
    await page.getByRole("link", { name: "حذف فیلتر «رزرو آنی»" }).click();
    await expect(page).not.toHaveURL(/instant=1/, { timeout: 30_000 });
    await expect(page).toHaveURL(/sea=1000/);
    await page.locator("[data-filter-button]").click();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("words and digits follow the copy rules", async ({ page }) => {
    await open(page);
    await expect(page.locator("#why-title")).toBeVisible({ timeout: 30_000 });
    await expectCleanCopy(page);
  });

  test("numbers in results and explanation open their provenance", async ({ page }) => {
    await open(page);
    expect(await expectProvenanceOn(page, 10)).toBe(10);
  });

  test("no serious or critical accessibility violations", async ({ page }) => {
    await open(page);
    // Measure after the explanation has faded in (mid-fade text has a lower contrast).
    await expect(page.locator("#why-title")).toBeVisible({ timeout: 30_000 });
    await page.waitForFunction(() =>
      document.getAnimations().every((a) => a.playState !== "running"),
    );
    const results = await new AxeBuilder({ page }).analyze();
    const critical = results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact ?? ""),
    );
    expect(critical.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });

  test("the CTA of a two-platform card opens the villa with the search's stay", async ({
    page,
  }) => {
    await open(page);
    const cta = page.getByRole("link", { name: "مقایسه‌ی پیشنهادها" }).first();
    await expect(cta).toHaveAttribute("href", /\/villas\/v-[0-9a-f]+\?in=.*&out=.*&guests=6/);
    await cta.click();
    await expect(page.locator("#booking")).toBeVisible();
  });

  test("removing a chip searches again without it, and everything can be restored", async ({
    page,
  }) => {
    await open(page);
    const before = await page.locator("#results-title").textContent();
    await page.getByRole("link", { name: "حذف «استخر» و جستجوی دوباره" }).click();
    await expect(page).toHaveURL(/drop=feature%3Apool/, { timeout: 30_000 });
    await expect(page.getByRole("link", { name: "حذف «استخر» و جستجوی دوباره" })).toHaveCount(0);
    const after = await page.locator("#results-title").textContent();
    expect(after).not.toBe(before); // no pool required: more villas
    await page.getByRole("link", { name: "بازگرداندن همه‌ی شرط‌ها" }).click();
    await expect(page.getByRole("link", { name: "حذف «استخر» و جستجوی دوباره" })).toBeVisible({
      timeout: 30_000,
    });
  });
});
