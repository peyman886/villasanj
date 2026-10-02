import type { Metadata } from "next";

import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { faDateTime, faNumber } from "@/lib/listing";

export const metadata: Metadata = { title: "سنجه‌ها · ویلاسنج" };

type Metrics = components["schemas"]["MetricsOut"];

const VERDICT_TEXT: Record<string, string> = {
  supported: "تأیید شد",
  not_confirmed: "تأیید نشد",
  contradicted: "رد شد",
};
const KIND_TEXT: Record<string, string> = { exact: "دقیق", range: "بازه", open: "حداقل" };

function percent(value: number): string {
  return `${faNumber(Math.round(value * 1000) / 10)}٪`;
}

function seconds(value: number | null): string {
  return value === null ? "—" : `${faNumber(Math.round(value * 100) / 100)} ثانیه`;
}

function Table({ caption, head, rows }: { caption: string; head: string[]; rows: string[][] }) {
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-stone-200 bg-white">
      <table className="w-full min-w-[28rem] text-start text-sm tabular-nums">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-stone-100 text-stone-600">
          <tr>
            {head.map((h) => (
              <th key={h} scope="col" className="p-2.5 text-start font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-200">
          {rows.map((row) => (
            <tr key={row.join("|")}>
              {row.map((cell, index) => (
                <td key={index} className="p-2.5">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function MetricsPage() {
  let metrics: Metrics | null = null;
  try {
    const { data } = await apiClient().GET("/metrics", { cache: "no-store" });
    metrics = data ?? null;
  } catch {
    metrics = null;
  }
  if (!metrics) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-10">
        <h1 className="text-2xl font-semibold">سنجه‌ها</h1>
        <p className="mt-3 text-stone-600" role="alert">
          سنجه‌ها در دسترس نیست. API در دسترس است؟
        </p>
      </main>
    );
  }
  const m = metrics;
  return (
    <main className="mx-auto max-w-4xl px-4 pt-6 pb-16">
      <h1 className="text-2xl font-semibold text-balance">سنجه‌های ویلاسنج</h1>
      <p className="mt-1 text-sm text-pretty text-stone-600">
        همه از همین پایگاه داده و با همان کدهایی که گزارش‌ها می‌سازند، در{" "}
        {faDateTime(m.computed_at)} حساب شده‌اند.
      </p>

      <section aria-labelledby="crawl" className="mt-8">
        <h2 id="crawl" className="text-lg font-semibold">
          ادب در crawl
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          حداقل فاصله‌ی دو درخواست پیاپی به هر میزبان (قاعده: دست‌کم ۳ ثانیه).
        </p>
        <Table
          caption="ترافیک هر میزبان"
          head={["میزبان", "پاسخ‌ها", "کمترین فاصله", "میانه‌ی فاصله"]}
          rows={m.hosts.map((h) => [
            h.host,
            faNumber(h.responses),
            seconds(h.min_interval_s),
            seconds(h.median_interval_s),
          ])}
        />
      </section>

      <section aria-labelledby="coverage" className="mt-8">
        <h2 id="coverage" className="text-lg font-semibold">
          پوشش و حقیقت‌سنجی
        </h2>
        <Table
          caption="پوشش هر پلتفرم"
          head={[
            "پلتفرم",
            "آگهی",
            "عکس دانلودشده",
            "فاصله تا ساحل",
            "زمان رانندگی",
            "ادعای دریا",
            "دست‌کم یک ادعای ردشده",
          ]}
          rows={m.platforms.map((p) => [
            p.platform,
            faNumber(p.listings),
            `${faNumber(p.photos_downloaded)} از ${faNumber(p.photos_selected)} (${percent(p.photo_coverage)})`,
            faNumber(p.coast_measured),
            faNumber(p.drive_routed),
            faNumber(p.sea_claim_listings),
            `${faNumber(p.sea_contradicted_listings)} (${percent(p.sea_claim_listings ? p.sea_contradicted_listings / p.sea_claim_listings : 0)})`,
          ])}
        />
        <p className="mt-2 text-xs text-stone-500">
          حکم ادعاهای دریا:{" "}
          {m.platforms
            .map(
              (p) =>
                `${p.platform}: ${Object.entries(p.sea_verdicts)
                  .map(([k, v]) => `${VERDICT_TEXT[k] ?? k} ${faNumber(v)}`)
                  .join("، ")}`,
            )
            .join(" · ")}
        </p>
      </section>

      <section aria-labelledby="offers" className="mt-8">
        <h2 id="offers" className="text-lg font-semibold">
          پیشنهادهای قیمت
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          هیچ پلتفرمی کارمزدش را منتشر نمی‌کند، پس قیمت‌های قابل رزرو «حداقل» هستند.
        </p>
        <Table
          caption="پیشنهادها به تفکیک سناریو"
          head={["پلتفرم", "سناریو", "نفر", "وضعیت", "نوع قیمت", "قدیمی"]}
          rows={m.offers.map((o) => [
            o.platform,
            o.scenario,
            faNumber(o.guests),
            Object.entries(o.by_status)
              .map(([k, v]) => `${k} ${faNumber(v)}`)
              .join("، "),
            Object.entries(o.by_kind)
              .map(([k, v]) => `${KIND_TEXT[k] ?? k} ${faNumber(v)}`)
              .join("، ") || "—",
            faNumber(o.stale),
          ])}
        />
      </section>

      <section aria-labelledby="llm" className="mt-8">
        <h2 id="llm" className="text-lg font-semibold">
          هزینه‌ی مدل زبانی
        </h2>
        <p className="mt-1 text-sm text-stone-600 tabular-nums">
          جمع {faNumber(Math.round(m.llm_total_usd * 10000) / 10000)} دلار از سقف{" "}
          {faNumber(m.llm_cap_usd)} دلار.
        </p>
        <Table
          caption="هزینه به تفکیک کار و مدل"
          head={["کار", "مدل", "فراخوانی", "ناموفق", "دلار"]}
          rows={m.llm_spend.map((s) => [
            s.task,
            s.model,
            faNumber(s.calls),
            faNumber(s.failed),
            faNumber(Math.round(s.cost_usd * 10000) / 10000),
          ])}
        />
      </section>

      <section aria-labelledby="labels" className="mt-8">
        <h2 id="labels" className="text-lg font-semibold">
          برچسب‌گذاری
        </h2>
        {m.labelling.length === 0 ? (
          <p className="mt-1 text-sm text-stone-600">هنوز صف برچسب‌گذاری ساخته نشده است.</p>
        ) : (
          <Table
            caption="پیشرفت برچسب‌گذاری"
            head={["صف", "برچسب‌خورده", "کل"]}
            rows={m.labelling.map((l) => [l.queue, faNumber(l.labelled), faNumber(l.total)])}
          />
        )}
        <p className="mt-3 text-sm text-pretty text-stone-600">
          هنوز نیامده: هم‌پوشانی پلتفرم‌ها، دقت تطبیق آگهی‌ها با بازه‌ی اطمینان و شب‌های پنهان.
          این‌ها به برچسب‌های انسانی M3 و ویلاهای یکپارچه‌ی M5 نیاز دارند.
        </p>
      </section>
    </main>
  );
}
