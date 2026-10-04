import { cache } from "react";

import { BarList, ProgressBar } from "@/components/charts/bars";
import { CodeBlock } from "@/components/docs/prose";
import { Callout } from "@/components/ui/callout";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { faInt, faPercent } from "@/lib/format";
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

const PLATFORM_FA: Record<string, string> = { jabama: "جاباما", shab: "شب" };
const SCENARIO_FA: Record<string, string> = {
  weekend: "آخر هفته",
  midweek: "وسط هفته",
  holiday: "تعطیلات",
};

function Unavailable() {
  return (
    <Callout kind="degraded" title="سنجه‌های زنده در دسترس نیست">
      سرور API پاسخ نداد؛ همین سنجه‌ها را <code className="ltr font-mono">crawl metrics</code> و{" "}
      <code className="ltr font-mono">catalog inventory</code> هم می‌دهند.
    </Callout>
  );
}

const live = (m: Metrics) => <SourceChip live generatedAt={m.computed_at} />;

/** Measured politeness per host: responses and the real interval between them. */
export async function CrawlHosts() {
  const m = await metrics();
  if (!m) return <Unavailable />;
  return (
    <div className="space-y-2">
      <DataTable caption="ادب crawl برای هر میزبان" minWidth="34rem">
        <thead>
          <tr>
            <th scope="col">پلتفرم</th>
            <th scope="col">میزبان</th>
            <th scope="col">پاسخ</th>
            <th scope="col">کمترین فاصله</th>
            <th scope="col">میانه‌ی فاصله</th>
          </tr>
        </thead>
        <tbody>
          {m.hosts.map((h) => (
            <tr key={h.host}>
              <td>{PLATFORM_FA[h.platform] ?? h.platform}</td>
              <td>
                <span className="ltr font-mono text-xs">{h.host}</span>
              </td>
              <td>{faInt(h.responses)}</td>
              <td>{h.min_interval_s === null ? "—" : `${faNumber(h.min_interval_s)} ثانیه`}</td>
              <td>
                {h.median_interval_s === null ? "—" : `${faNumber(h.median_interval_s)} ثانیه`}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {live(m)}
    </div>
  );
}

/** Listings, photos, coast distance and drive time per platform. */
export async function CatalogCoverage() {
  const m = await metrics();
  if (!m) return <Unavailable />;
  return (
    <div className="space-y-2">
      <DataTable caption="پوشش کاتالوگ" minWidth="40rem">
        <thead>
          <tr>
            <th scope="col">پلتفرم</th>
            <th scope="col">آگهی</th>
            <th scope="col">عکس انتخاب‌شده</th>
            <th scope="col">عکس دانلودشده</th>
            <th scope="col">فاصله تا ساحل</th>
            <th scope="col">زمان رانندگی</th>
          </tr>
        </thead>
        <tbody>
          {m.platforms.map((p) => (
            <tr key={p.platform}>
              <th scope="row" className="font-medium">
                {PLATFORM_FA[p.platform] ?? p.platform}
              </th>
              <td>{faInt(p.listings)}</td>
              <td>{faInt(p.photos_selected)}</td>
              <td>
                {faInt(p.photos_downloaded)} ({faPercent(p.photo_coverage)})
              </td>
              <td>{faInt(p.coast_measured)}</td>
              <td>{faInt(p.drive_routed)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {live(m)}
    </div>
  );
}

const STATUS_FA: Record<string, string> = {
  bookable: "قابل رزرو",
  unavailable: "شبی پر یا بسته",
  too_many_guests: "ظرفیت کم",
  below_min_nights: "کمتر از حداقل شب",
  unknown: "شبی بی‌مشاهده",
};

/** Offers per scenario × group: what share of listings can quote at all, and why not. */
export async function OfferCoverage() {
  const m = await metrics();
  if (!m) return <Unavailable />;
  const statuses = [...new Set(m.offers.flatMap((o) => Object.keys(o.by_status)))];
  return (
    <div className="space-y-2">
      <DataTable caption="پیشنهادها در هر سناریو" minWidth="44rem">
        <thead>
          <tr>
            <th scope="col">پلتفرم</th>
            <th scope="col">سناریو</th>
            <th scope="col">نفر</th>
            {statuses.map((s) => (
              <th key={s} scope="col">
                {STATUS_FA[s] ?? s}
              </th>
            ))}
            <th scope="col">قدیمی</th>
          </tr>
        </thead>
        <tbody>
          {m.offers.map((o) => (
            <tr key={`${o.platform}-${o.scenario}-${o.guests}`}>
              <td>{PLATFORM_FA[o.platform] ?? o.platform}</td>
              <td>{SCENARIO_FA[o.scenario] ?? o.scenario}</td>
              <td>{faInt(o.guests)}</td>
              {statuses.map((s) => (
                <td key={s}>{faInt(o.by_status[s] ?? 0)}</td>
              ))}
              <td>{faInt(o.stale)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {live(m)}
    </div>
  );
}

const TARGET_FA: Record<string, string> = {
  sea: "دریا",
  city_center: "مرکز شهر",
  bakery: "نانوایی",
  supermarket: "سوپرمارکت",
  restaurant: "رستوران",
  shopping: "خرید",
  medical: "درمانی",
  forest: "جنگل",
  recreation: "تفریحی",
  shrine: "زیارتگاه",
  other: "دیگر",
};
const VERDICT_FA = CLAIM_VERDICT_TEXT;

/** Every distance claim's verdict per target, both platforms together. */
export async function DistanceVerdicts() {
  const m = await metrics();
  if (!m) return <Unavailable />;
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
  return (
    <div className="space-y-2">
      <DataTable caption="حکم ادعاهای فاصله برای هر مقصد" minWidth="36rem">
        <thead>
          <tr>
            <th scope="col">مقصد</th>
            {verdicts.map((v) => (
              <th key={v} scope="col">
                {VERDICT_FA[v]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([target, row]) => (
            <tr key={target}>
              <th scope="row" className="font-medium">
                {TARGET_FA[target] ?? target}
              </th>
              {verdicts.map((v) => (
                <td key={v}>{faInt(row[v] ?? 0)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="text-sm text-pretty text-fg-muted">
        {m.platforms
          .map(
            (p) =>
              `${PLATFORM_FA[p.platform] ?? p.platform}: ${faInt(p.distance_contradicted_listings)} از ${faInt(p.distance_judged_listings)} آگهی دست‌کم یک ادعای فاصله‌ی ردشده دارند (${faPercent(p.distance_contradicted_low)} تا ${faPercent(p.distance_contradicted_high)})`,
          )
          .join("؛ ")}
        .
      </p>
      {live(m)}
    </div>
  );
}

const QUEUE_FA: Record<string, string> = {
  "gold-v1": "جفت‌های gold تطبیق",
  "photos-v1": "برچسب عکس‌ها",
  "claims-v1": "ادعاهای توضیحات",
  "summaries-v1": "بازبینی کور خلاصه‌ها",
};

/** The owner's labelling queues and how far each got. */
export async function LabellingProgress() {
  const m = await metrics();
  if (!m) return <Unavailable />;
  return (
    <div className="space-y-3 rounded-card border border-line bg-surface p-5">
      {m.labelling.map((q) => (
        <ProgressBar
          key={q.queue}
          label={`${QUEUE_FA[q.queue] ?? q.queue} (${q.queue})`}
          value={q.labelled}
          max={Math.max(1, q.total)}
          display={`${faInt(q.labelled)} از ${faInt(q.total)}`}
        />
      ))}
      {live(m)}
    </div>
  );
}

function usd(v: number): string {
  return `${faNumber(Math.round(v * 100) / 100)} دلار`;
}

/** LLM spend from the ledger, live (every call is recorded, cache hits at zero cost). */
export async function LlmSpend() {
  const m = await metrics();
  if (!m) {
    return (
      <Callout kind="degraded" title="سنجه‌های زنده در دسترس نیست">
        سرور API پاسخ نداد؛ هزینه‌ها در دفتر هزینه‌ی پایگاه داده‌اند (
        <code className="ltr font-mono">llm spend</code>).
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
        label="هزینه‌ی کل در برابر سقف پروژه"
        value={m.llm_total_usd}
        max={m.llm_cap_usd}
        display={`${usd(m.llm_total_usd)} از ${usd(m.llm_cap_usd)}`}
        tone={m.llm_total_usd > m.llm_cap_usd * 0.8 ? "caution" : "brand"}
      />
      <BarList
        label="هزینه به تفکیک کار"
        bars={byTask.map(([task, cost]) => ({ label: task, value: cost, display: usd(cost) }))}
      />
      <SourceChip live generatedAt={m.computed_at} />
    </div>
  );
}

/** A config file as it is in the repository (read at request time, never retyped). */
export async function ConfigSnippet({
  file,
  from,
  to,
}: {
  file: string;
  from?: string;
  to?: string;
}) {
  const text = await readConfig(file);
  if (text === null) return <Callout kind="caution" title={`config/${file} خوانده نشد`} />;
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
