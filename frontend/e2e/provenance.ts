import { expect, type Page } from "@playwright/test";

/** Deterministic pick of ``count`` items (a small LCG: the same sample on every run). */
export function sample<T>(items: T[], count: number, seed = 7): T[] {
  const pool = [...items];
  const picked: T[] = [];
  let state = seed;
  while (picked.length < count && pool.length > 0) {
    state = (state * 1_103_515_245 + 12_345) % 2_147_483_648;
    picked.push(pool.splice(state % pool.length, 1)[0] as T);
  }
  return picked;
}

/** Click numbers and assert each opens its provenance card, which Escape closes again. */
export async function expectProvenanceOn(page: Page, count: number): Promise<number> {
  const targets = await page
    .locator("[data-sourced]")
    .evaluateAll((buttons) => buttons.map((b) => b.getAttribute("popovertarget") ?? ""));
  const chosen = sample(
    targets.filter((t) => t),
    count,
  );
  for (const id of chosen) {
    const button = page.locator(`[popovertarget="${id}"][data-sourced]`);
    await button.scrollIntoViewIfNeeded();
    await button.click();
    const card = page.locator(`[id="${id}"]`);
    await expect(card).toBeVisible();
    await expect(card).toContainText("منبع");
    await expect(card).toContainText("زمان مشاهده");
    await page.keyboard.press("Escape");
    await expect(card).toBeHidden();
  }
  return chosen.length;
}
