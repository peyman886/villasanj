import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Light is the default; dark is the reader's choice from the header, kept in localStorage
// (lib/theme.ts, tokens in globals.css). Same accessibility bar in both.
const QUERY = "ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد زیر ۲۰ میلیون";

async function bodyLightness(page: Page): Promise<number> {
  return page.evaluate(() => {
    // Computed colours may be oklch(); a canvas turns any CSS colour into RGB.
    const ctx = document.createElement("canvas").getContext("2d");
    if (!ctx) return 255;
    ctx.fillStyle = getComputedStyle(document.body).backgroundColor;
    ctx.fillRect(0, 0, 1, 1);
    const [r = 255, g = 255, b = 255] = ctx.getImageData(0, 0, 1, 1).data;
    return (r + g + b) / 3;
  });
}

test.describe("theme choice", () => {
  test.use({ colorScheme: "dark" }); // the system's preference does not decide

  test("light by default; the toggle switches to dark, and the choice survives a reload", async ({
    page,
  }) => {
    await page.goto("/");
    expect(await bodyLightness(page)).toBeGreaterThan(200);
    await page.locator("header [data-theme-toggle]").click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await bodyLightness(page)).toBeLessThan(60);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await page.evaluate(() => localStorage.getItem("villasanj-theme"))).toBe("dark");
    await page.locator("header [data-theme-toggle]").click();
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", "dark");
    await page.goto("/en/docs");
    expect(await bodyLightness(page)).toBeGreaterThan(200);
  });
});

test.describe("dark theme", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("villasanj-theme", "dark"));
  });
  test.describe.configure({ timeout: 120_000 });

  for (const path of [
    "/",
    `/search?${new URLSearchParams({ q: QUERY })}`,
    "/villas/v-6331f454983f?in=2026-10-15&out=2026-10-17&guests=6",
    "/docs",
    "/en/docs",
  ]) {
    test(`${path.split("?")[0]} has a dark canvas and no serious contrast issue`, async ({
      page,
    }) => {
      await page.goto(path);
      await expect(page.locator("h1")).toBeAttached();
      expect(await bodyLightness(page)).toBeLessThan(60);
      await page.waitForFunction(() =>
        document.getAnimations().every((a) => a.playState !== "running"),
      );
      const results = await new AxeBuilder({ page }).analyze();
      const bad = results.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact ?? ""),
      );
      expect(
        bad.map(
          (v) =>
            `${v.id}: ${v.nodes
              .map((n) => n.target.join(" "))
              .slice(0, 3)
              .join(", ")}`,
        ),
      ).toEqual([]);
    });
  }
});
