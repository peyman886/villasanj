/**
 * Colour discipline on the product pages (M12 2.7, copy-and-numbers.md §4): amber only for
 * «دو عدد متفاوت» (two listings stating different things) and a price's age, red only for
 * «با نقشه نمی‌خواند». Rating stars keep their conventional gold. Contrast itself is measured by
 * the axe E2E checks; this test catches a warm colour used for anything else.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
const PRODUCT = [
  "app/(site)/page.tsx",
  "app/(site)/search",
  "app/(site)/villas",
  "components/search",
  "components/villa",
  "components/home",
  "components/listing",
];

// file -> the warm classes it may use, and why
const ALLOWED: Record<string, { classes: RegExp; why: string }> = {
  "components/villa/specs.tsx": {
    classes: /^(bg-amber-50|ring-amber-200)$/,
    why: "«دو عدد متفاوت»",
  },
};
const STARS = /^(fill-amber-400|text-amber-500)$/; // rating stars, next to their number

function files(entry: string): string[] {
  const full = path.join(SRC, entry);
  if (statSync(full).isFile()) return [entry];
  return readdirSync(full).flatMap((name) => files(path.join(entry, name)));
}

describe("warm colours on the product pages", () => {
  it("amber and red appear only where the copy rules allow them", () => {
    const misuse: string[] = [];
    for (const file of PRODUCT.flatMap(files).filter((f) => f.endsWith(".tsx"))) {
      const source = readFileSync(path.join(SRC, file), "utf8");
      for (const match of source.matchAll(
        /\b(?:bg|text|ring|border|fill|decoration)-(?:amber|rose|red|yellow|orange)-\d+/g,
      )) {
        const cls = match[0];
        if (STARS.test(cls) && source.includes("Star")) continue;
        if (ALLOWED[file]?.classes.test(cls)) continue;
        misuse.push(`${file}: ${cls}`);
      }
      for (const match of source.matchAll(/(?:tone|kind)="(caution|danger)"/g)) {
        const ok =
          file === "app/(site)/villas/[id]/page.tsx" &&
          source.includes("آنچه دو آگهی یکسان نمی‌گویند");
        if (!ok) misuse.push(`${file}: ${match[0]}`);
      }
    }
    expect(misuse).toEqual([]);
  });

  it("the state tokens are the ones decided (D8.3, research §4.8)", () => {
    const css = readFileSync(path.join(SRC, "app/globals.css"), "utf8");
    for (const [token, value] of [
      ["jabama", "#2563eb"],
      ["shab", "#7c3aed"],
      ["verified", "#1f7a3e"],
      ["caution", "#8a5a00"],
      ["contradicted", "#b42318"],
      ["hidden", "#c99a2e"],
    ]) {
      expect(css).toContain(`--color-${token}: ${value};`);
    }
  });
});
