import { describe, expect, it } from "vitest";

import {
  areaText,
  distance,
  distanceRange,
  duration,
  durationRange,
  faDigits,
  faNum,
  faPct,
  fullToman,
  isNarrow,
  perPerson,
  pinToman,
  priceFrom,
  priceFull,
  rating,
  shortToman,
  type Bound,
  type Money,
} from "@/lib/numbers";

const money = (low: number, high: number | null): Money => ({
  low_toman: low,
  high_toman: high,
  low_rial: low * 10,
  high_rial: high === null ? null : high * 10,
});

describe("digits and separators", () => {
  it.each([
    ["0123456789", "۰۱۲۳۴۵۶۷۸۹"],
    ["ساعت 14:00", "ساعت ۱۴:۰۰"],
    ["بدون رقم", "بدون رقم"],
  ])("faDigits(%s)", (input, expected) => expect(faDigits(input)).toBe(expected));

  it.each([
    [8_500_000, 0, "۸٬۵۰۰٬۰۰۰"],
    [20.7, 1, "۲۰٫۷"],
    [100, 1, "۱۰۰"],
    [3.0, 2, "۳"],
    [1234.5, 1, "۱٬۲۳۴٫۵"],
  ])("faNum(%d, %d)", (value, digits, expected) => expect(faNum(value, digits)).toBe(expected));

  it.each([
    [1, "۱۰۰٪"],
    [0.207, "۲۰٫۷٪"],
    [0.95, "۹۵٪"],
    [0.9999, "۱۰۰٪"],
  ])("faPct(%d)", (share, expected) => expect(faPct(share)).toBe(expected));

  it("never uses a slash or a Latin digit", () => {
    for (const text of [faPct(1), faNum(8.5, 1), shortToman(8_540_000, "lower")]) {
      expect(text).not.toMatch(/[0-9/]/);
    }
  });
});

describe("short money rounds by the kind of bound", () => {
  it.each<[number, Bound, string]>([
    [8_540_000, "lower", "۸٫۵ میلیون تومان"],
    [8_540_000, "upper", "۸٫۶ میلیون تومان"],
    [8_540_000, "point", "۸٫۵ میلیون تومان"],
    [8_560_000, "point", "۸٫۶ میلیون تومان"],
    [8_500_000, "lower", "۸٫۵ میلیون تومان"],
    [8_500_000, "upper", "۸٫۵ میلیون تومان"],
    [12_000_000, "lower", "۱۲ میلیون تومان"],
    [999_999, "lower", "۹۹۹ هزار تومان"],
    [850_000, "upper", "۸۵۰ هزار تومان"],
    [1_250_000_000, "lower", "۱٫۲ میلیارد تومان"],
  ])("shortToman(%d, %s)", (toman, bound, expected) =>
    expect(shortToman(toman, bound)).toBe(expected),
  );

  it("a lower bound never shows more than the data", () => {
    for (const toman of [1_099_999, 8_549_999, 10_999_999, 23_456_789]) {
      const shown = Number(
        shortToman(toman, "lower")
          .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
          .replace("٫", ".")
          .split(" ")[0],
      );
      expect(shown * 1_000_000).toBeLessThanOrEqual(toman);
    }
  });

  it.each([
    [8_540_000, "۸٫۵"],
    [10_999_999, "۱۰٫۹"],
    [850_000, "۸۵۰ هزار"],
  ])("pinToman(%d)", (toman, expected) => expect(pinToman(toman)).toBe(expected));

  it("the booking card keeps the full number", () => {
    expect(fullToman(8_540_000)).toBe("۸٬۵۴۰٬۰۰۰ تومان");
  });
});

describe("prices with «از»", () => {
  it.each<[Money, string, string]>([
    [money(8_540_000, null), "از ۸٫۵ میلیون تومان", "از ۸٬۵۴۰٬۰۰۰ تومان"],
    [money(8_540_000, 8_540_000), "۸٫۵ میلیون تومان", "۸٬۵۴۰٬۰۰۰ تومان"],
    [money(8_000_000, 9_000_000), "از ۸ میلیون تومان", "۸٬۰۰۰٬۰۰۰ تا ۹٬۰۰۰٬۰۰۰ تومان"],
  ])("priceFrom / priceFull", (m, card, full) => {
    expect(priceFrom(m)).toBe(card);
    expect(priceFull(m)).toBe(full);
  });

  it.each<[Money, number, string]>([
    [money(8_500_000, null), 4, "نفری از ۲٫۱ میلیون"],
    [money(8_400_000, 8_400_000), 4, "نفری ۲٫۱ میلیون"],
    [money(3_000_000, null), 6, "نفری از ۵۰۰ هزار"],
  ])("perPerson", (m, people, expected) => expect(perPerson(m, people)).toBe(expected));
});

describe("ranges stay ranges unless narrow", () => {
  it.each([
    [255, 260, true], // 4:15 to 4:20
    [100, 115, true],
    [100, 117, false],
    [1500, 2400, false],
    [0, 0, true],
    [0, 700, false],
  ])("isNarrow(%d, %d)", (low, high, expected) => expect(isNarrow(low, high)).toBe(expected));

  it.each([
    [1500, 2400, "۱٫۵ تا ۲٫۴ کیلومتر"],
    [0, 700, "۰ تا ۷۰۰ متر"],
    [650, 1400, "۶۵۰ متر تا ۱٫۴ کیلومتر"],
    [1980, 2050, "حدود ۲ کیلومتر"],
    [430, 460, "حدود ۴۵۰ متر"],
  ])("distanceRange(%d, %d)", (low, high, expected) =>
    expect(distanceRange(low, high)).toBe(expected),
  );

  it.each([
    [255 * 60, 260 * 60, "حدود ۴ ساعت"],
    [100 * 60, 190 * 60, "۱ ساعت و ۳۰ دقیقه تا ۴ ساعت"],
    [40 * 60, 44 * 60, "حدود ۴۰ دقیقه"],
  ])("durationRange(%d, %d)", (low, high, expected) =>
    expect(durationRange(low, high)).toBe(expected),
  );

  it.each([
    [45, "point", "۴۵ دقیقه"],
    [135, "point", "۲ ساعت و ۱۵ دقیقه"],
    [61, "lower", "۱ ساعت"],
    [61, "upper", "۱ ساعت و ۱۵ دقیقه"],
  ] as const)("duration(%d, %s)", (minutes, bound, expected) =>
    expect(duration(minutes, bound)).toBe(expected),
  );

  it.each([
    [430, "lower", "۴۰۰ متر"],
    [430, "upper", "۴۵۰ متر"],
    [2_449, "point", "۲٫۴ کیلومتر"],
  ] as const)("distance(%d, %s)", (metres, bound, expected) =>
    expect(distance(metres, bound)).toBe(expected),
  );

  it.each([
    [[300, 220], "۲۲۰ تا ۳۰۰ متر"],
    [[300, 300], "۳۰۰ متر"],
    [[null, 120], "۱۲۰ متر"],
    [[null, undefined], null],
  ] as const)("areaText(%j)", (values, expected) => expect(areaText([...values])).toBe(expected));

  it("ratings keep two decimals at most", () => {
    expect(rating(4.893)).toBe("۴٫۸۹");
    expect(rating(5)).toBe("۵");
  });
});
