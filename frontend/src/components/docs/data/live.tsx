import { cache } from "react";

import { BarList, ProgressBar } from "@/components/charts/bars";
import { CodeBlock } from "@/components/docs/prose";
import { Callout } from "@/components/ui/callout";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { formatFor } from "@/lib/format";
import { t, type Locale } from "@/lib/i18n";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { CLAIM_VERDICT_TEXT, faNumber } from "@/lib/listing";
import { readConfig } from "@/lib/project-files";

type Metrics = components["schemas"]["MetricsOut"];

const metrics = cache(async (): Promise<Metrics | null> => {
  try {
    const { data } = await apiClient().GET("/metrics", { cache: "no-store" });
    return data ?? null;
  } catch {
    return null;
  }
});

type Labels = Record<string, { fa: string; en: string }>;

/** The label for a key in a language, or the key itself when it is not listed. */
function label(map: Labels, key: string, locale: Locale): string {
  const hit = map[key];
  return hit ? t(locale, hit.fa, hit.en) : key;
}

const enNumber = new Intl.NumberFormat("en-US");

/** A plain number (up to three decimals) in the language's digits. */
function num(value: number | null | undefined, locale: Locale): string {
  if (locale === "fa") return faNumber(value);
  return value === null || value === undefined ? "unknown" : enNumber.format(value);
}

function seconds(value: number | null, locale: Locale): string {
  return value === null ? "-" : `${num(value, locale)} ${t(locale, "ثانیه", "s")}`;
}

const PLATFORM: Labels = {
  jabama: { fa: "جاباما", en: "Jabama" },
  shab: { fa: "شب", en: "Shab" },
};
const SCENARIO: Labels = {
  weekend: { fa: "آخر هفته", en: "Weekend" },
  midweek: { fa: "وسط هفته", en: "Midweek" },
  holiday: { fa: "تعطیلات", en: "Holiday" },
};

const UNAVAILABLE_TITLE = { fa: "سنجه‌های زنده در دسترس نیست", en: "Live metrics are unavailable" };

function Unavailable({ locale }: { locale: Locale }) {
  return (
    <Callout kind="degraded" title={t(locale, UNAVAILABLE_TITLE.fa, UNAVAILABLE_TITLE.en)}>
      {locale === "en" ? (
        <>
          The API server did not respond; <code className="ltr font-mono">crawl metrics</code> and{" "}
          <code className="ltr font-mono">catalog inventory</code> report the same metrics.
        </>
      ) : (
        <>
          سرور API پاسخ نداد؛ همین سنجه‌ها را <code className="ltr font-mono">crawl metrics</code> و{" "}
          <code className="ltr font-mono">catalog inventory</code> هم می‌دهند.
        </>
      )}
    </Callout>
  );
}

const live = (m: Metrics, locale: Locale) => (
  <SourceChip live generatedAt={m.computed_at} locale={locale} />
);

/** Measured politeness per host: responses and the real interval between them. */
export async function CrawlHosts({ locale = "fa" }: { locale?: Locale }) {
  const m = await metrics();
  if (!m) return <Unavailable locale={locale} />;
  const f = formatFor(locale);
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(locale, "ادب crawl برای هر میزبان", "Crawl politeness per host")}
        minWidth="34rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "پلتفرم", "Platform")}</th>
            <th scope="col">{t(locale, "میزبان", "Host")}</th>
            <th scope="col">{t(locale, "پاسخ", "Responses")}</th>
            <th scope="col">{t(locale, "کمترین فاصله", "Shortest interval")}</th>
            <th scope="col">{t(locale, "میانه‌ی فاصله", "Median interval")}</th>
          </tr>
        </thead>
        <tbody>
          {m.hosts.map((h) => (
            <tr key={h.host}>
              <td>{label(PLATFORM, h.platform, locale)}</td>
              <td>
                <span className="ltr font-mono text-xs">{h.host}</span>
              </td>
              <td>{f.int(h.responses)}</td>
              <td>{seconds(h.min_interval_s, locale)}</td>
              <td>{seconds(h.median_interval_s, locale)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {live(m, locale)}
    </div>
  );
}

/** Listings, photos, coast distance and drive time per platform. */
export async function CatalogCoverage({ locale = "fa" }: { locale?: Locale }) {
  const m = await metrics();
  if (!m) return <Unavailable locale={locale} />;
  const f = formatFor(locale);
  return (
    <div className="space-y-2">
      <DataTable caption={t(locale, "پوشش کاتالوگ", "Catalog coverage")} minWidth="40rem">
        <thead>
          <tr>
            <th scope="col">{t(locale, "پلتفرم", "Platform")}</th>
            <th scope="col">{t(locale, "آگهی", "Listings")}</th>
            <th scope="col">{t(locale, "عکس انتخاب‌شده", "Photos selected")}</th>
            <th scope="col">{t(locale, "عکس دانلودشده", "Photos downloaded")}</th>
            <th scope="col">{t(locale, "فاصله تا ساحل", "Coast distance")}</th>
            <th scope="col">{t(locale, "زمان رانندگی", "Drive time")}</th>
          </tr>
        </thead>
        <tbody>
          {m.platforms.map((p) => (
            <tr key={p.platform}>
              <th scope="row" className="font-medium">
                {label(PLATFORM, p.platform, locale)}
              </th>
              <td>{f.int(p.listings)}</td>
              <td>{f.int(p.photos_selected)}</td>
              <td>
                {f.int(p.photos_downloaded)} ({f.percent(p.photo_coverage)})
              </td>
              <td>{f.int(p.coast_measured)}</td>
              <td>{f.int(p.drive_routed)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {live(m, locale)}
    </div>
  );
}

const STATUS: Labels = {
  bookable: { fa: "قابل رزرو", en: "Bookable" },
  unavailable: { fa: "شبی پر یا بسته", en: "A night booked or closed" },
  too_many_guests: { fa: "ظرفیت کم", en: "Too small" },
  below_min_nights: { fa: "کمتر از حداقل شب", en: "Below minimum nights" },
  unknown: { fa: "شبی بی‌مشاهده", en: "A night not observed" },
};

/** Offers per scenario × group: what share of listings can quote at all, and why not. */
export async function OfferCoverage({ locale = "fa" }: { locale?: Locale }) {
  const m = await metrics();
  if (!m) return <Unavailable locale={locale} />;
  const f = formatFor(locale);
  const statuses = [...new Set(m.offers.flatMap((o) => Object.keys(o.by_status)))];
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(locale, "پیشنهادها در هر سناریو", "Offers per scenario")}
        minWidth="44rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "پلتفرم", "Platform")}</th>
            <th scope="col">{t(locale, "سناریو", "Scenario")}</th>
            <th scope="col">{t(locale, "نفر", "Guests")}</th>
            {statuses.map((s) => (
              <th key={s} scope="col">
                {label(STATUS, s, locale)}
              </th>
            ))}
            <th scope="col">{t(locale, "قدیمی", "Stale")}</th>
          </tr>
        </thead>
        <tbody>
          {m.offers.map((o) => (
            <tr key={`${o.platform}-${o.scenario}-${o.guests}`}>
              <td>{label(PLATFORM, o.platform, locale)}</td>
              <td>{label(SCENARIO, o.scenario, locale)}</td>
              <td>{f.int(o.guests)}</td>
              {statuses.map((s) => (
                <td key={s}>{f.int(o.by_status[s] ?? 0)}</td>
              ))}
              <td>{f.int(o.stale)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {live(m, locale)}
    </div>
  );
}

const TARGET: Labels = {
  sea: { fa: "دریا", en: "Sea" },
  city_center: { fa: "مرکز شهر", en: "Town centre" },
  bakery: { fa: "نانوایی", en: "Bakery" },
  supermarket: { fa: "سوپرمارکت", en: "Supermarket" },
  restaurant: { fa: "رستوران", en: "Restaurant" },
  shopping: { fa: "خرید", en: "Shopping" },
  medical: { fa: "درمانی", en: "Medical" },
  forest: { fa: "جنگل", en: "Forest" },
  recreation: { fa: "تفریحی", en: "Recreation" },
  shrine: { fa: "زیارتگاه", en: "Shrine" },
  other: { fa: "دیگر", en: "Other" },
};
// The same wording as VerdictBadge's English labels.
const VERDICT_EN: Record<string, string> = {
  supported: "Confirmed",
  not_confirmed: "Not confirmed",
  contradicted: "Disagrees with the map",
  not_checked: "Not checked",
};

/** Every distance claim's verdict per target, both platforms together. */
export async function DistanceVerdicts({ locale = "fa" }: { locale?: Locale }) {
  const m = await metrics();
  if (!m) return <Unavailable locale={locale} />;
  const f = formatFor(locale);
  const totals = new Map<string, Record<string, number>>();
  for (const p of m.platforms) {
    for (const [target, verdicts] of Object.entries(p.distance_verdicts)) {
      const row = totals.get(target) ?? {};
      for (const [v, n] of Object.entries(verdicts)) row[v] = (row[v] ?? 0) + n;
      totals.set(target, row);
    }
  }
  const verdicts = ["supported", "not_confirmed", "contradicted", "not_checked"];
  const rows = [...totals.entries()].sort(
    ([, a], [, b]) =>
      Object.values(b).reduce((x, y) => x + y, 0) - Object.values(a).reduce((x, y) => x + y, 0),
  );
  const perPlatform = m.platforms.map((p) =>
    locale === "en"
      ? `${label(PLATFORM, p.platform, locale)}: ${f.int(p.distance_contradicted_listings)} of ${f.int(p.distance_judged_listings)} listings have at least one distance claim that disagrees with the map (${f.percent(p.distance_contradicted_low)} to ${f.percent(p.distance_contradicted_high)})`
      : `${label(PLATFORM, p.platform, locale)}: ${f.int(p.distance_contradicted_listings)} از ${f.int(p.distance_judged_listings)} آگهی دست‌کم یک ادعای فاصله‌ی ردشده دارند (${f.percent(p.distance_contradicted_low)} تا ${f.percent(p.distance_contradicted_high)})`,
  );
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(locale, "حکم ادعاهای فاصله برای هر مقصد", "Distance claim verdicts per target")}
        minWidth="36rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "مقصد", "Target")}</th>
            {verdicts.map((v) => (
              <th key={v} scope="col">
                {locale === "en" ? VERDICT_EN[v] : CLAIM_VERDICT_TEXT[v]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([target, row]) => (
            <tr key={target}>
              <th scope="row" className="font-medium">
                {label(TARGET, target, locale)}
              </th>
              {verdicts.map((v) => (
                <td key={v}>{f.int(row[v] ?? 0)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="text-sm text-pretty text-fg-muted">
        {perPlatform.join(t(locale, "؛ ", "; "))}.
      </p>
      {live(m, locale)}
    </div>
  );
}

const QUEUE: Labels = {
  "gold-v1": { fa: "جفت‌های gold تطبیق", en: "Gold-set matching pairs" },
  "photos-v1": { fa: "برچسب عکس‌ها", en: "Photo labels" },
  "claims-v1": { fa: "ادعاهای توضیحات", en: "Description claims" },
  "summaries-v1": { fa: "بازبینی کور خلاصه‌ها", en: "Blind review of summaries" },
};

/** The owner's labelling queues and how far each got. */
export async function LabellingProgress({ locale = "fa" }: { locale?: Locale }) {
  const m = await metrics();
  if (!m) return <Unavailable locale={locale} />;
  const f = formatFor(locale);
  return (
    <div className="space-y-3 rounded-card border border-line bg-surface p-5">
      {m.labelling.map((q) => (
        <ProgressBar
          key={q.queue}
          label={`${label(QUEUE, q.queue, locale)} (${q.queue})`}
          value={q.labelled}
          max={Math.max(1, q.total)}
          display={`${f.int(q.labelled)} ${t(locale, "از", "of")} ${f.int(q.total)}`}
        />
      ))}
      {live(m, locale)}
    </div>
  );
}

function usd(v: number, locale: Locale): string {
  const rounded = Math.round(v * 100) / 100;
  return locale === "en" ? `$${num(rounded, locale)}` : `${num(rounded, locale)} دلار`;
}

/** LLM spend from the ledger, live (every call is recorded, cache hits at zero cost). */
export async function LlmSpend({ locale = "fa" }: { locale?: Locale }) {
  const m = await metrics();
  if (!m) {
    return (
      <Callout kind="degraded" title={t(locale, UNAVAILABLE_TITLE.fa, UNAVAILABLE_TITLE.en)}>
        {locale === "en" ? (
          <>
            The API server did not respond; the spend is in the database&apos;s cost ledger (
            <code className="ltr font-mono">llm spend</code>).
          </>
        ) : (
          <>
            سرور API پاسخ نداد؛ هزینه‌ها در دفتر هزینه‌ی پایگاه داده‌اند (
            <code className="ltr font-mono">llm spend</code>).
          </>
        )}
      </Callout>
    );
  }
  const byTask = Object.entries(
    m.llm_spend.reduce<Record<string, number>>((acc, s) => {
      acc[s.task] = (acc[s.task] ?? 0) + s.cost_usd;
      return acc;
    }, {}),
  ).sort(([, a], [, b]) => b - a);
  return (
    <div className="space-y-4 rounded-card border border-line bg-surface p-5">
      <ProgressBar
        label={t(locale, "هزینه‌ی کل در برابر سقف پروژه", "Total spend against the project cap")}
        value={m.llm_total_usd}
        max={m.llm_cap_usd}
        display={`${usd(m.llm_total_usd, locale)} ${t(locale, "از", "of")} ${usd(m.llm_cap_usd, locale)}`}
        tone={m.llm_total_usd > m.llm_cap_usd * 0.8 ? "caution" : "brand"}
      />
      <BarList
        label={t(locale, "هزینه به تفکیک کار", "Spend by task")}
        bars={byTask.map(([task, cost]) => ({
          label: task,
          value: cost,
          display: usd(cost, locale),
        }))}
      />
      <SourceChip live generatedAt={m.computed_at} locale={locale} />
    </div>
  );
}

/** A config file as it is in the repository (read at request time, never retyped). */
export async function ConfigSnippet({
  file,
  from,
  to,
  locale = "fa",
}: {
  file: string;
  from?: string;
  to?: string;
  locale?: Locale;
}) {
  const text = await readConfig(file);
  if (text === null) {
    return (
      <Callout
        kind="caution"
        title={t(locale, `config/${file} خوانده نشد`, `config/${file} could not be read`)}
      />
    );
  }
  let shown = text;
  if (from) {
    const start = shown.indexOf(from);
    if (start >= 0) shown = shown.slice(start);
  }
  if (to) {
    const end = shown.indexOf(to);
    if (end >= 0) shown = shown.slice(0, end);
  }
  return (
    <CodeBlock title={`config/${file}`}>
      <code>{shown.trimEnd()}</code>
    </CodeBlock>
  );
}
