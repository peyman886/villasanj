import { expect, type Page } from "@playwright/test";

import { FORBIDDEN } from "../src/lib/copy";

/**
 * The page's visible Persian text has no Latin digit and none of the forbidden words
 * (copy-and-numbers.md §1–2). Left-to-right islands (code, ids) are skipped.
 */
export async function expectCleanCopy(page: Page) {
  const found = await page.evaluate(
    (forbidden) => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const latin: string[] = [];
      const words: string[] = [];
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const parent = node.parentElement;
        const text = node.textContent ?? "";
        if (!parent || !text.trim()) continue;
        if (parent.closest("[dir=ltr], .ltr, code, script, style, .maplibregl-ctrl-attrib"))
          continue;
        if (!parent.checkVisibility()) continue;
        if (/[0-9]/.test(text) && /[؀-ۿ]/.test(text)) latin.push(text.trim().slice(0, 80));
        for (const word of forbidden)
          if (text.includes(word)) words.push(`${word}: ${text.trim().slice(0, 80)}`);
      }
      return { latin, words };
    },
    [...FORBIDDEN],
  );
  expect(found.words, "forbidden words").toEqual([]);
  expect(found.latin, "Latin digits in Persian text").toEqual([]);
}

/** How many times ``needle`` appears in the page's visible text. */
export async function countVisible(page: Page, needle: string): Promise<number> {
  const text = await page.locator("body").innerText();
  return text.split(needle).length - 1;
}
