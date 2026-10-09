import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Dark mode follows the system (taste-skill; tokens in globals.css). Same accessibility bar.
const QUERY = "ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد زیر ۲۰ میلیون";

test.describe("dark mode", () => {
  test.use({ colorScheme: "dark" });
  test.describe.configure({ timeout: 120_000 });

  for (const path of [
    "/",
    `/search?${new URLSearchParams({ q: QUERY })}`,
    "/villas/v-6331f454983f?in=2026-10-15&out=2026-10-17&guests=6",
    "/docs",
  ]) {
    test(`${path.split("?")[0]} has a dark canvas and no serious contrast issue`, async ({
      page,
    }) => {
      await page.goto(path);
      await expect(page.locator("h1")).toBeAttached();
      const lightness = await page.evaluate(() => {
        // Computed colours may be oklch(); a canvas turns any CSS colour into RGB.
        const ctx = document.createElement("canvas").getContext("2d");
        if (!ctx) return 255;
        ctx.fillStyle = getComputedStyle(document.body).backgroundColor;
        ctx.fillRect(0, 0, 1, 1);
        const [r = 255, g = 255, b = 255] = ctx.getImageData(0, 0, 1, 1).data;
        return (r + g + b) / 3;
      });
      expect(lightness).toBeLessThan(60);
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
