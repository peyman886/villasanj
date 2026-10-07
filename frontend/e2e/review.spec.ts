import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// The owner's review tools. These checks only read: no verdict or grade is ever submitted, so
// running them never writes a label.

async function noSeriousViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const bad = results.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""));
  expect(bad.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)).toEqual([]);
}

test.describe("owner's reviews", () => {
  test("the hub lists the open queues with their progress and links", async ({ page }) => {
    await page.goto("/review");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("بازبینی‌های مالک");
    for (const href of ["/label/queries", "/label/relevance", "/label?queue=er-human"]) {
      await expect(page.locator(`main a[href="${href}"]`)).toBeVisible();
    }
    await expect(page.getByRole("progressbar").first()).toBeVisible();
    await noSeriousViolations(page);
  });

  test("the query review shows the case and opens a correction without saving", async ({
    page,
  }) => {
    await page.goto("/label/queries?position=1");
    await expect(page.locator("#case-title")).toContainText("«");
    await expect(page.locator("dl > div").first()).toBeVisible();
    await expect(page.locator("html[data-review-keys=on]")).toHaveCount(1); // hydrated
    await page.keyboard.press("KeyN"); // opens the correction panel; nothing is posted
    await expect(page.getByLabel("برداشت درست (JSON)")).toBeVisible();
    await noSeriousViolations(page);
  });

  test("the relevance review shows the pool blind and moves with the keyboard", async ({
    page,
  }) => {
    await page.goto("/label/relevance?position=1");
    await expect(page.locator("#query-title")).toContainText("«");
    const cards = page.locator("section[aria-labelledby=pool-title] ol > li");
    expect(await cards.count()).toBeGreaterThan(2);
    // No rank or system name is shown on a card.
    await expect(cards.first()).not.toContainText(/ranking|price|rating|رتبه‌ی/);
    await expect(page.locator("html[data-review-keys=on]")).toHaveCount(1); // hydrated
    // The selection starts on the first card not graded yet (the owner may have started).
    const selected = await cards.evaluateAll((items) =>
      items.findIndex((li) => li.className.includes("border-brand-500")),
    );
    const count = await cards.count();
    await page.keyboard.press(selected < count - 1 ? "ArrowDown" : "ArrowUp");
    const next = selected < count - 1 ? selected + 1 : selected - 1;
    await expect(cards.nth(next)).toHaveClass(/border-brand-500/);
    await noSeriousViolations(page);
  });
});
