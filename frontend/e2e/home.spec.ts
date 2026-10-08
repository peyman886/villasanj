import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { expectCleanCopy } from "./copy";

test.describe("home page (M12 2.5)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toHaveText("یک ویلا، همه‌ی حقیقت");
  });

  test("the two-platform villas come right after the hero, each with both prices", async ({
    page,
  }) => {
    const sections = await page
      .locator("main section[aria-labelledby]")
      .evaluateAll((els) => els.map((e) => e.getAttribute("aria-labelledby")));
    expect(sections.slice(0, 2)).toEqual(["hero-title", "villas-title"]);
    const card = page.locator("[aria-labelledby=villas-title] li").first();
    await expect(card).toContainText("جاباما");
    await expect(card).toContainText("شب");
    await expect(card).toContainText("یک ویلا در ۲ آگهی");
  });

  test("one proof strip to /metrics, no stats cards, principles or dark docs box", async ({
    page,
  }) => {
    const strip = page.locator("[data-proof-strip]");
    await expect(strip).toHaveAttribute("href", "/metrics");
    await expect(strip).toContainText("ویلا در هر دو پلتفرم");
    await expect(page.getByText("ویلاسنج تا امروز")).toHaveCount(0);
    await expect(page.getByText("چرا می‌شود به این صفحه‌ها اعتماد کرد")).toHaveCount(0);
    await expect(page.getByText("گزارش فنی کامل پروژه")).toHaveCount(0);
    await expect(page.locator("footer").getByText("برای داوران")).toBeVisible();
    await expect(page.locator("footer a[href='/docs/demo']")).toBeVisible();
  });

  test("the proof strip's numbers come from the newest ER artifact", async ({ page }) => {
    const dir = path.resolve(process.cwd(), "..", "reports"); // tests run from frontend/
    const newest = readdirSync(dir)
      .filter((n) => n.startsWith("er-eval-") && n.endsWith(".json"))
      .map((n) => JSON.parse(readFileSync(path.join(dir, n), "utf8")))
      .sort((a, b) => String(b.generated_at).localeCompare(String(a.generated_at)))[0];
    const fa = new Intl.NumberFormat("fa-IR");
    const strip = page.locator("[data-proof-strip]");
    await expect(strip).toContainText(fa.format(newest.data.villas_now.villas));
    await expect(strip).toContainText(fa.format(newest.data.villas_now.multi_platform));
  });

  test("words and digits follow the copy rules; no serious accessibility issue", async ({
    page,
  }) => {
    await expectCleanCopy(page);
    const results = await new AxeBuilder({ page }).analyze();
    const bad = results.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""));
    expect(bad.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
