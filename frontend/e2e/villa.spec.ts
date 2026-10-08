import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { countVisible, expectCleanCopy } from "./copy";
import { expectProvenanceOn } from "./provenance";

// The demo villa, chosen by the rule in docs/ux/decisions.md D8.4 (scripts/pick_demo_villa.py);
// override with E2E_VILLA. The stay is the demo search's (weekend after next, 6 people).
const VILLA = process.env.E2E_VILLA ?? "v-6331f454983f";
const STAY = "in=2026-10-15&out=2026-10-17&guests=6";
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8801";

async function open(page: Page, query = STAY) {
  await page.goto(`/villas/${VILLA}?${query}`);
  await expect(page.locator("h1")).toBeVisible();
}

function hamming(a: string, b: string): number {
  let x = BigInt(`0x${a}`) ^ BigInt(`0x${b}`);
  let n = 0;
  while (x > 0n) {
    n += Number(x & 1n);
    x >>= 1n;
  }
  return n;
}

test.describe("villa page", () => {
  test.describe.configure({ timeout: 90_000 });

  test("the booking card shows each platform's own price, cheaper first (M12 1.6)", async ({
    page,
  }) => {
    await open(page);
    const rows = page.locator("[data-booking-rows] > li");
    await expect(rows).toHaveCount(2);
    const first = rows.first();
    await expect(first).toContainText("ارزان‌تر");
    for (const row of await rows.all()) {
      await expect(row).toContainText(/تومان/);
      await expect(row).toContainText(/قیمتِ .* پیش/);
      await expect(row.getByRole("link", { name: /↗/ })).toHaveAttribute("href", /^https:\/\//);
    }
    const prices = await rows.evaluateAll((els) =>
      els.map((el) =>
        Number(
          (el.querySelector("[data-sourced]")?.textContent ?? "")
            .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
            .replace(/[^0-9]/g, ""),
        ),
      ),
    );
    expect(prices[0]).toBeLessThanOrEqual(prices[1] ?? Infinity);
    expect(await countVisible(page, "کارمزد")).toBe(1);
  });

  test("changing the group re-quotes both platforms from stored observations", async ({ page }) => {
    await open(page);
    const before = await page.locator("[data-booking-rows]").innerText();
    await page.getByRole("link", { name: "یک نفر بیشتر" }).click();
    await expect(page).toHaveURL(/guests=7/, { timeout: 20_000 });
    await expect(page.locator("[data-booking-rows] > li")).toHaveCount(2);
    await expect(page.locator("[data-booking-rows]")).not.toHaveText(before);
  });

  test("a stale price says its age, and a platform without a free night says so", async ({
    page,
    request,
  }) => {
    // A hidden night: free on one platform, unavailable on the other.
    const calendar = await (
      await request.get(`${API}/villas/${VILLA}/calendar?start=2026-10-08&end=2026-12-06`)
    ).json();
    const hidden = (calendar as { night: string; hidden: boolean }[]).find((n) => n.hidden);
    test.skip(!hidden, "no hidden night in the window");
    const night = hidden?.night ?? "";
    const next = new Date(`${night}T12:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    await open(page, `in=${night}&out=${next.toISOString().slice(0, 10)}&guests=4`);
    const rows = page.locator("[data-booking-rows] > li");
    await expect(rows.last()).toContainText("برای این تاریخ در");
    await expect(rows.last()).toContainText("خالی نیست");
    await expect(page.getByText(/شب از این سفر «شب پنهان» است/)).toBeVisible();
    await expect(page.locator("[data-booking-rows] .text-caution").first()).toContainText("پیش");
  });

  test("a villa on one platform shows one row and says so", async ({ page, request }) => {
    const listing = (await (await request.get(`${API}/listings/sample?n=60&seed=solo`)).json()) as {
      platform: string;
      external_id: string;
    }[];
    let solo: string | null = null;
    for (const l of listing) {
      const ref = await (
        await request.get(`${API}/villas/of/${l.platform}/${l.external_id}`)
      ).json();
      if (ref.members === 1) {
        solo = ref.villa_id;
        break;
      }
    }
    test.skip(solo === null, "no single-platform villa in the sample");
    await page.goto(`/villas/${solo}?${STAY}`);
    await expect(page.locator("[data-booking-rows] > li")).toHaveCount(1);
    await expect(page.getByText(/این ویلا را فقط در .* پیدا کردیم/)).toBeVisible();
    await expect(page.locator("[data-match-badge]")).toHaveCount(0);
  });

  test("the gallery has no duplicate photos (M12 1.7)", async ({ page }) => {
    await open(page);
    const hashes = await page
      .locator("[data-gallery] [data-phash]")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-phash") ?? ""));
    for (let i = 0; i < hashes.length; i += 1) {
      for (let j = i + 1; j < hashes.length; j += 1) {
        expect(hamming(hashes[i] ?? "", hashes[j] ?? "")).toBeGreaterThan(10);
      }
    }
    await expect(page.locator("[data-gallery] > li")).toHaveCount(5);
    await expect(page.getByRole("button", { name: /\+[۰-۹]+ عکس/ })).toBeVisible();
  });

  test("the two-platform calendar: Saturday first, split days, keyboard picks a stay", async ({
    page,
  }) => {
    await open(page);
    const calendar = page.locator("#calendar");
    await expect(calendar.locator("thead th").first()).toHaveAttribute("abbr", "شنبه");
    const day = calendar.locator("[data-day]").first();
    await expect(day.locator("> span[aria-hidden]")).toHaveCount(2); // jabama top, shab bottom
    await expect(day).toHaveAttribute("aria-label", /جاباما: .*؛ شب: /);
    // States differ by more than colour: a filled half, a hatched one, a dashed outline.
    const looks = await calendar.locator("[data-day] > span[aria-hidden]").evaluateAll((els) => [
      ...new Set(
        els.map((e) => {
          const s = getComputedStyle(e);
          return `${s.backgroundImage !== "none"}|${s.borderStyle}`;
        }),
      ),
    ]);
    expect(looks.length).toBeGreaterThan(1);
    await day.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("ArrowLeft"); // RTL: the next day
    await page.keyboard.press("ArrowLeft");
    await expect(calendar.locator("[data-day]").nth(2)).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/in=\d{4}-\d{2}-\d{2}&out=\d{4}-\d{2}-\d{2}/);
    await expect(page.locator("#booking")).toContainText("۲ شب");
  });

  test("«چرا مطمئنیم؟» shows only the recorded evidence (M12 1.9)", async ({ page, request }) => {
    const [pair] = (await (await request.get(`${API}/villas/${VILLA}/match`)).json()) as {
      photo_pairs: unknown[];
    }[];
    await open(page);
    await page.locator("[data-match-badge]").click();
    await expect(page).toHaveURL(/#match$/);
    const section = page.locator("#match");
    await expect(section).toBeInViewport();
    await expect(section.locator("[data-match-pair]")).toHaveCount(pair?.photo_pairs.length ?? 0);
    expect(pair?.photo_pairs.length ?? 0).toBeGreaterThanOrEqual(3);
    const lines = await section.locator("[data-evidence]").count();
    expect(lines).toBeGreaterThanOrEqual(2);
    expect(lines).toBeLessThanOrEqual(3);
    await expect(section.locator("[data-decision]")).toHaveCount(3);
    // The technical ER paragraph is no longer at the top of the page.
    await expect(page.locator("[data-villa-header]")).not.toContainText("داور مدل‌زبانی");
  });

  test("highlights are verified facts with their source; the truth check is grouped (2.1)", async ({
    page,
  }) => {
    await open(page);
    const highlights = page.locator("[data-highlights] > li");
    const n = await highlights.count();
    expect(n).toBeGreaterThanOrEqual(3);
    expect(n).toBeLessThanOrEqual(5);
    for (const h of await highlights.all()) {
      await expect(h).toContainText(/تأیید شد|اندازه‌گیری شد|روی نقشه|امتیاز|پلتفرم/);
    }
    const groups = page.locator("#truth [data-group]");
    expect(await groups.count()).toBeGreaterThan(0);
    const order = await groups.evaluateAll((els) => els.map((e) => e.getAttribute("data-group")));
    const rank = ["verified", "not_verified", "map_disagrees", "not_checked"];
    expect(order).toEqual([...order].sort((a, b) => rank.indexOf(a ?? "") - rank.indexOf(b ?? "")));
    // No score bar, and the blur note at most once per group.
    await expect(page.locator("#truth [style*='width']")).toHaveCount(0);
    const notes = await page.locator("#truth").getByText("تا ۵۰۰ متر خطا فرض شده").count();
    expect(notes).toBeLessThanOrEqual(await groups.count());
  });

  test("the section bar follows the scroll and moves focus to the heading (2.2)", async ({
    page,
  }) => {
    await open(page);
    const nav = page.getByRole("navigation", { name: "بخش‌های صفحه" });
    await nav.getByRole("link", { name: "نظرها" }).click();
    await expect(page.locator("#reviews-title")).toBeFocused();
    await expect(nav.getByRole("link", { name: "نظرها" })).toHaveAttribute(
      "aria-current",
      "location",
      { timeout: 5_000 },
    );
  });

  test("specs agree on one line; differences get «دو عدد متفاوت» (2.3)", async ({ page }) => {
    await open(page);
    await expect(page.locator("#stay [data-specs] > li").first()).toBeVisible();
    await expect(page.locator("#stay table")).toContainText("دو عدد متفاوت");
  });

  test("a summary point's chip filters the reviews to the ones it cites (2.4)", async ({
    page,
  }) => {
    await open(page);
    const chip = page.locator("[data-cite-chip]").first();
    await expect(chip).toBeVisible({ timeout: 30_000 });
    const label = (await chip.textContent()) ?? "";
    const cited = Number(
      label.replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0)).replace(/[^0-9]/g, ""),
    );
    expect(cited).toBeGreaterThanOrEqual(2);
    const reviews = page.locator("#reviews li[id^='review-']");
    const all = await reviews.count();
    await chip.click();
    await expect(chip).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#reviews li[id^='review-']:visible")).toHaveCount(cited);
    await page.getByRole("button", { name: "همه‌ی نظرها" }).click();
    await expect(page.locator("#reviews li[id^='review-']:visible")).toHaveCount(all);
    await expect(page.locator("[data-villa-header]")).toContainText(/[۰-۹]+ امتیاز · [۰-۹]+ نظر/);
  });

  test("words and digits follow the copy rules", async ({ page }) => {
    await open(page);
    await expectCleanCopy(page);
  });

  test("the sample prices are a closed drawer", async ({ page }) => {
    await open(page);
    await expect(page.locator("[data-drawer=samples]")).not.toHaveAttribute("open", "");
  });

  test("ten random numbers open their provenance (M7 criterion 3)", async ({ page }) => {
    await open(page);
    expect(await expectProvenanceOn(page, 10)).toBe(10);
  });

  test("no serious or critical accessibility violations (M7 criterion 4)", async ({ page }) => {
    await open(page);
    const results = await new AxeBuilder({ page }).analyze();
    const bad = results.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""));
    expect(bad.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });

  test("a member listing links back to the villa", async ({ page }) => {
    await open(page);
    await page.locator("#match a[href^='/listings/']").first().click();
    await expect(page).toHaveURL(/\/listings\//);
    const back = page.getByRole("link", { name: "صفحه‌ی ویلا" });
    await expect(back).toHaveAttribute("href", `/villas/${VILLA}`);
  });
});
