import type { Metadata } from "next";

import { BarList, ProgressBar } from "@/components/charts/bars";
import { Section } from "@/components/ui/card";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { ErrorState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { latest } from "@/lib/artifacts";
import { faInt, faInterval, faPercent } from "@/lib/format";
import { CLAIM_TARGET_TEXT, faDateTime, faNumber } from "@/lib/listing";

export const metadata: Metadata = { title: "سنجه‌ها" };
export const dynamic = "force-dynamic";

type Metrics = components["schemas"]["MetricsOut"];

const PLATFORM_FA: Record<string, string> = { jabama: "جاباما", shab: "شب" };
const KIND_TEXT: Record<string, string> = { exact: "دقیق", range: "بازه", open: "حداقل" };
const STATUS_FA: Record<string, string> = {
  bookable: "آزاد",
  unavailable: "پر",
  too_many_guests: "ظرفیت کم",
  below_min_nights: "زیر حداقل شب",
  unknown: "نامعلوم",
};
const CLAIM_COLUMNS = ["supported", "not_confirmed", "contradicted", "not_checked"] as const;
const CLAIM_COLUMN_TEXT: Record<string, string> = {
  supported: "تأیید شد",
  not_confirmed: "تأیید نشد",
  contradicted: "با نقشه نمی‌خواند",
  not_checked: "بررسی نشد",
};

function seconds(value: number | null): string {
  return value === null ? "-" : `${faNumber(Math.round(value * 100) / 100)} ثانیه`;
}

function usd(value: number): string {
  return `${faNumber(Math.round(value * 100) / 100)} دلار`;
}

export default async function MetricsPage() {
  let metrics: Metrics | null = null;
  try {
    const { data } = await apiClient().GET("/metrics", { cache: "no-store" });
    metrics = data ?? null;
  } catch {
    metrics = null;
  }
  const [er, hypotheses, h4] = await Promise.all([
    latest("er-eval"),
    latest("hypotheses"),
    latest("h4"),
  ]);
  if (!metrics) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <h1 className="text-2xl font-bold">سنجه‌ها</h1>
        <ErrorState title="سنجه‌های زنده در دسترس نیست" className="mt-6">
          سرور API پاسخ نداد؛ گزارش‌های تولیدشده در بخش مستندات هنوز در دسترس‌اند.
        </ErrorState>
      </div>
    );
  }
  const m = metrics;
  const configured = er?.data.revised.policies.find((p) => p.configured);
  const h3 = hypotheses?.data.h3;
  return (
    <div className="mx-auto max-w-6xl space-y-14 px-4 pt-8 pb-16 sm:px-6">
      <header>
        <h1 className="text-2xl font-bold text-balance">سنجه‌های ویلاسنج</h1>
        <p className="mt-1 text-sm text-pretty text-fg-muted">
          سنجه‌های زنده از همین پایگاه داده و با همان کدهایی که گزارش‌ها می‌سازند، در{" "}
          {faDateTime(m.computed_at)} حساب شده‌اند؛ نتیجه‌های ارزیابی از آخرین گزارش تولیدشده
          می‌آیند.
        </p>
      </header>

      <MetricGrid>
        <MetricCard
          tone="verified"
          label="ویلای روی هر دو پلتفرم"
          value={faInt(er?.data.villas_now.multi_platform)}
          detail={er ? `از ${faInt(er.data.villas_now.villas)} ویلای یکتا` : undefined}
          source={<SourceChip file={er?.file} generatedAt={er?.generated_at} />}
        />
        <MetricCard
          tone="verified"
          label="دقت تطبیق (سیاست فعلی)"
          value={faPercent(configured?.metrics.precision.estimate)}
          detail={configured ? `بازیابی ${faInterval(configured.metrics.recall)}` : undefined}
          source={<SourceChip file={er?.file} generatedAt={er?.generated_at} />}
        />
        <MetricCard
          label="شب‌های پنهان"
          value={h3 ? faPercent(h3.hidden_nights / h3.nights_compared) : "-"}
          detail={
            h3 ? `در ${faInt(h3.pairs_with_hidden_night)} ویلا از ${faInt(h3.pairs)}` : undefined
          }
          source={<SourceChip file={hypotheses?.file} generatedAt={hypotheses?.generated_at} />}
        />
        <MetricCard
          tone={m.llm_total_usd > m.llm_cap_usd * 0.8 ? "caution" : "neutral"}
          label="هزینه‌ی مدل زبانی"
          value={usd(m.llm_total_usd)}
          detail={`از سقف ${usd(m.llm_cap_usd)}`}
          source={<SourceChip live />}
        />
      </MetricGrid>

      {h4 ? (
        <Section
          id="h4"
          title="ادعاهای تأییدنشده (H4)"
          description="سهم آگهی‌هایی که دست‌کم یک ادعای مکانی یا امکاناتی‌شان با نقشه نمی‌خواند یا آگهی دیگر همان ویلا خلافش را می‌گوید."
          action={<SourceChip file={h4.file} generatedAt={h4.generated_at} />}
        >
          <BarList
            label="سهم H4 به تفکیک پلتفرم"
            max={0.3}
            bars={h4.data.platforms.map((p) => ({
              label: PLATFORM_FA[p.platform] ?? p.platform,
              value: p.share.estimate ?? 0,
              display: faInterval(p.share),
              tone: "caution",
            }))}
          />
          <p className="mt-2 text-xs text-fg-muted">
            مقیاس تا ۳۰٪؛ فرضیه‌ی گزارش پژوهشی «دست‌کم ۲۵٪» بود.
          </p>
        </Section>
      ) : null}

      <Section
        id="crawl"
        title="ادب در crawl"
        description="کمترین و میانه‌ی فاصله‌ی دو درخواست پیاپی به هر میزبان (قاعده: دست‌کم ۳ ثانیه)."
      >
        <DataTable caption="ترافیک هر میزبان">
          <thead>
            <tr>
              <th scope="col">میزبان</th>
              <th scope="col">پاسخ‌ها</th>
              <th scope="col">کمترین فاصله</th>
              <th scope="col">میانه‌ی فاصله</th>
            </tr>
          </thead>
          <tbody>
            {m.hosts.map((h) => (
              <tr key={h.host}>
                <td>
                  <span className="ltr font-mono text-xs">{h.host}</span>
                </td>
                <td>{faNumber(h.responses)}</td>
                <td>{seconds(h.min_interval_s)}</td>
                <td>{seconds(h.median_interval_s)}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </Section>

      <Section
        id="coverage"
        title="پوشش داده"
        description="عکس‌های انتخاب‌شده (۵ تا برای هر آگهی)، فاصله تا ساحل و زمان رانندگی."
      >
        <div className="grid gap-4 md:grid-cols-2">
          {m.platforms.map((p) => (
            <div
              key={p.platform}
              className="space-y-3 rounded-card border border-line bg-surface p-5"
            >
              <p className="font-semibold">
                {PLATFORM_FA[p.platform] ?? p.platform}{" "}
                <span className="text-sm font-normal text-fg-muted">
                  ({faNumber(p.listings)} آگهی)
                </span>
              </p>
              <ProgressBar
                label="عکس دانلودشده"
                value={p.photos_downloaded}
                max={p.photos_selected}
                display={`${faNumber(p.photos_downloaded)} از ${faNumber(p.photos_selected)}`}
              />
              <ProgressBar
                label="فاصله تا ساحل اندازه‌گیری‌شده"
                value={p.coast_measured}
                max={p.listings}
                display={`${faNumber(p.coast_measured)} از ${faNumber(p.listings)}`}
              />
              <ProgressBar
                label="زمان رانندگی از تهران"
                value={p.drive_routed}
                max={p.listings}
                display={`${faNumber(p.drive_routed)} از ${faNumber(p.listings)}`}
              />
              <p className="text-sm text-fg-muted">
                ادعای فاصله‌ی ناسازگار با نقشه:{" "}
                {p.distance_judged_listings
                  ? `${faNumber(p.distance_contradicted_listings)} از ${faNumber(p.distance_judged_listings)} آگهی (${faPercent(
                      p.distance_contradicted_listings / p.distance_judged_listings,
                    )}؛ ${faPercent(p.distance_contradicted_low)} تا ${faPercent(p.distance_contradicted_high)})`
                  : "-"}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        id="claims"
        title="ادعاهای فاصله به تفکیک مقصد"
        description="هر ادعای منتشرشده‌ی فاصله در برابر نقشه. «بررسی نشد» یعنی برای آن مقصد شاهدی نداریم؛ نقشه همه‌ی مغازه‌ها را ندارد، پس آن‌ها فقط تأیید می‌کنند."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          {m.platforms.map((p) => (
            <DataTable key={p.platform} caption={`ادعاهای فاصله در ${p.platform}`} minWidth="26rem">
              <thead>
                <tr>
                  <th scope="col">{PLATFORM_FA[p.platform] ?? p.platform}</th>
                  {CLAIM_COLUMNS.map((c) => (
                    <th key={c} scope="col">
                      {CLAIM_COLUMN_TEXT[c]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(p.distance_verdicts).map(([target, counts]) => (
                  <tr key={target}>
                    <th scope="row" className="font-normal">
                      {CLAIM_TARGET_TEXT[target] ?? target}
                    </th>
                    {CLAIM_COLUMNS.map((c) => (
                      <td
                        key={c}
                        className={
                          c === "contradicted" && (counts[c] ?? 0) > 0 ? "text-rose-700" : undefined
                        }
                      >
                        {faNumber(counts[c] ?? 0)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </DataTable>
          ))}
        </div>
      </Section>

      <Section
        id="offers"
        title="پیشنهادهای قیمت"
        description="هیچ پلتفرمی کارمزدش را منتشر نمی‌کند، پس قیمت‌های قابل رزرو «حداقل» هستند."
      >
        <DataTable caption="پیشنهادها به تفکیک سناریو" minWidth="40rem">
          <thead>
            <tr>
              <th scope="col">پلتفرم</th>
              <th scope="col">سناریو</th>
              <th scope="col">نفر</th>
              <th scope="col">وضعیت</th>
              <th scope="col">نوع قیمت</th>
              <th scope="col">قدیمی</th>
            </tr>
          </thead>
          <tbody>
            {m.offers.map((o) => (
              <tr key={`${o.platform}-${o.scenario}-${o.guests}`}>
                <td>{PLATFORM_FA[o.platform] ?? o.platform}</td>
                <td>{o.scenario}</td>
                <td>{faNumber(o.guests)}</td>
                <td className="text-fg-muted">
                  {Object.entries(o.by_status)
                    .map(([k, v]) => `${STATUS_FA[k] ?? k} ${faNumber(v)}`)
                    .join("، ")}
                </td>
                <td className="text-fg-muted">
                  {Object.entries(o.by_kind)
                    .map(([k, v]) => `${KIND_TEXT[k] ?? k} ${faNumber(v)}`)
                    .join("، ") || "-"}
                </td>
                <td>{faNumber(o.stale)}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </Section>

      <Section
        id="llm"
        title="هزینه‌ی مدل زبانی"
        description={`جمع ${usd(m.llm_total_usd)} از سقف ${usd(m.llm_cap_usd)} پروژه، از دفتر هزینه (هر فراخوانی ثبت می‌شود).`}
        action={<SourceChip live />}
      >
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <BarList
            label="هزینه به تفکیک کار"
            bars={Object.entries(
              m.llm_spend.reduce<Record<string, number>>((acc, s) => {
                acc[s.task] = (acc[s.task] ?? 0) + s.cost_usd;
                return acc;
              }, {}),
            )
              .sort(([, a], [, b]) => b - a)
              .map(([task, cost]) => ({ label: task, value: cost, display: usd(cost) }))}
          />
          <DataTable caption="هزینه به تفکیک کار و مدل" minWidth="28rem">
            <thead>
              <tr>
                <th scope="col">کار</th>
                <th scope="col">مدل</th>
                <th scope="col">فراخوانی</th>
                <th scope="col">دلار</th>
              </tr>
            </thead>
            <tbody>
              {m.llm_spend.map((s) => (
                <tr key={`${s.task}-${s.model}`}>
                  <td>
                    <span className="ltr font-mono text-xs">{s.task}</span>
                  </td>
                  <td>
                    <span className="ltr font-mono text-xs">{s.model}</span>
                  </td>
                  <td>{faNumber(s.calls)}</td>
                  <td>{faNumber(Math.round(s.cost_usd * 1000) / 1000)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      </Section>

      <Section
        id="labels"
        title="برچسب‌گذاری انسانی"
        description="هر صف و پیشرفتش؛ برچسب‌های مالک تنها معیار سنجش‌اند."
      >
        {m.labelling.length === 0 ? (
          <p className="text-sm text-fg-muted">هنوز صف برچسب‌گذاری ساخته نشده است.</p>
        ) : (
          <div className="grid gap-4 rounded-card border border-line bg-surface p-5 sm:grid-cols-2">
            {m.labelling.map((l) => (
              <ProgressBar
                key={l.queue}
                label={l.queue}
                value={l.labelled}
                max={l.total}
                display={`${faNumber(l.labelled)} از ${faNumber(l.total)}`}
                tone={l.labelled >= l.total ? "brand" : "sand"}
              />
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
