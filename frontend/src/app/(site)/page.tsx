import {
  ArrowLeft,
  BookOpenText,
  CalendarSearch,
  Fingerprint,
  Layers,
  Scale,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { Metadata } from "next";

import { VillaCard } from "@/components/villa-card";
import { ButtonLink, buttonClass } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Section } from "@/components/ui/card";
import { ChipLink } from "@/components/ui/chip";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { apiClient, type Listing } from "@/lib/api/client";
import { latest } from "@/lib/artifacts";
import { faInt, faInterval, faPercent } from "@/lib/format";
import { apiBaseUrl, fetchHealth } from "@/lib/health";
import { EXAMPLE_QUERIES } from "@/lib/search";

export const metadata: Metadata = { title: { absolute: "ویلاسنج · یک ویلا، همه‌ی حقیقت" } };
export const dynamic = "force-dynamic";

const STEPS = [
  {
    Icon: Layers,
    title: "جمع‌آوری مؤدبانه",
    text: "آگهی‌های جاباما و شب، با رعایت robots.txt و شرایط استفاده؛ هر پاسخ نسخه‌ی ثابت دارد.",
  },
  {
    Icon: Fingerprint,
    title: "یک ویلا، نه چند آگهی",
    text: "عکس، موقعیت و ساختار کنار هم سنجیده می‌شوند تا آگهی‌های یک ویلای واقعی یکی شوند.",
  },
  {
    Icon: CalendarSearch,
    title: "قیمت و تقویم واقعی",
    text: "قیمت نهایی برای تاریخ و تعداد نفر شما، و شب‌هایی که فقط در یک پلتفرم آزادند.",
  },
  {
    Icon: ShieldCheck,
    title: "سنجش ادعاها",
    text: "فاصله تا دریا و امکانات در برابر نقشه و آگهی‌های دیگر همان ویلا؛ با لحن «تأیید نشد».",
  },
] as const;

const PRINCIPLES = [
  ["هیچ عدد ساختگی", "هر قیمت و ادعا منبع و زمان مشاهده دارد؛ ناشناخته یعنی بازه یا «حداقل»."],
  ["قیمت‌ها ترکیب نمی‌شوند", "هر پلتفرم پیشنهاد خودش را دارد و کنار هم نشان داده می‌شوند."],
  ["مدل زبانی عدد نمی‌نویسد", "عددها را کد می‌گذارد و بررسی می‌کند؛ مدل فقط متن را می‌نویسد."],
  ["دسترسی‌پذیری مشاهده است", "آزاد بودن یک شب مشاهده‌ای با سن است، نه وضعیت قطعی."],
] as const;

async function featuredVillas(): Promise<{ id: string; members: Listing[] }[]> {
  try {
    const api = apiClient();
    const { data } = await api.GET("/villas/sample", {
      params: { query: { n: 6, seed: "home" } },
      cache: "no-store",
    });
    const villas = await Promise.all(
      (data ?? []).map(async ({ villa_id }) => {
        const { data: villa } = await api.GET("/villas/{villa_id}", {
          params: { path: { villa_id } },
          cache: "no-store",
        });
        return villa ? { id: villa.id, members: villa.members } : null;
      }),
    );
    return villas.filter((v): v is { id: string; members: Listing[] } => v !== null);
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const [er, hypotheses, h4, health, villas] = await Promise.all([
    latest("er-eval"),
    latest("hypotheses"),
    latest("h4"),
    fetchHealth(apiBaseUrl()),
    featuredVillas(),
  ]);
  const configured = er?.data.revised.policies.find((p) => p.configured);
  const listings = hypotheses ? Object.values(hypotheses.data.h1.listings) : [];
  const h3 = hypotheses?.data.h3;
  const llmDown = health !== null && health.checks.llm?.ok === false;

  return (
    <>
      <div className="border-b border-line bg-gradient-to-b from-brand-50 to-canvas">
        <div className="mx-auto max-w-6xl px-4 pt-14 pb-16 sm:px-6 sm:pt-20">
          <p className="text-sm font-semibold text-accent">ترب برای ویلا · رامسر تا تنکابن</p>
          <h1 className="mt-3 max-w-3xl text-4xl font-bold text-balance text-fg sm:text-5xl">
            یک ویلا، همه‌ی حقیقت
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-pretty text-fg-muted">
            هر ویلای واقعی یک صفحه دارد: قیمت نهایی برای تاریخ و تعداد نفر شما، تقویم همه‌ی
            پلتفرم‌ها کنار هم، نظرهای جمع‌شده و سنجش ادعاهای آگهی. هر عدد منبع دارد.
          </p>
          <form action="/search" method="get" role="search" className="mt-8 max-w-3xl">
            <label htmlFor="home-q" className="sr-only">
              ویلای مورد نظرتان را توصیف کنید
            </label>
            <div className="flex flex-col gap-2 rounded-card border border-line-strong bg-surface p-2 shadow-float sm:flex-row">
              <div className="flex min-w-0 flex-1 items-center gap-2 px-2">
                <Search aria-hidden="true" className="size-5 shrink-0 text-fg-subtle" />
                <input
                  id="home-q"
                  name="q"
                  required
                  placeholder="مثلاً ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد"
                  className="h-11 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-fg-subtle"
                />
              </div>
              <button type="submit" className={buttonClass("primary", "lg")}>
                جستجو
              </button>
            </div>
          </form>
          <div className="mt-4 flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.slice(0, 4).map((q) => (
              <ChipLink key={q} href={`/search?${new URLSearchParams({ q })}`}>
                {q}
              </ChipLink>
            ))}
          </div>
          {llmDown ? (
            <Callout
              kind="degraded"
              title="مدل زبانی فعلاً در دسترس نیست"
              className="mt-6 max-w-3xl"
            >
              جستجوهایی که قبلاً پرسیده شده‌اند (مثل نمونه‌های بالا) از حافظه پاسخ می‌گیرند؛ صفحه‌ی
              ویلاها، قیمت‌ها و تقویم‌ها بدون مدل کار می‌کنند.
            </Callout>
          ) : null}
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-20 px-4 pt-14 sm:px-6">
        <Section
          id="numbers"
          eyebrow="سنجیده، نه ادعا"
          title="ویلاسنج تا امروز"
          description="عددها از گزارش‌های تولیدشده می‌آیند؛ روی منبع هر کدام بزنید تا گزارش کامل را ببینید."
        >
          <MetricGrid>
            <MetricCard
              label="آگهی در منطقه"
              value={faInt(listings.reduce((a, b) => a + b, 0))}
              detail={
                hypotheses
                  ? Object.entries(hypotheses.data.h1.listings)
                      .map(
                        ([p, n]) =>
                          `${p === "jabama" ? "جاباما" : p === "shab" ? "شب" : p} ${faInt(n)}`,
                      )
                      .join(" · ")
                  : undefined
              }
              source={<SourceChip file={hypotheses?.file} generatedAt={hypotheses?.generated_at} />}
            />
            <MetricCard
              tone="verified"
              label="ویلای واقعی روی هر دو پلتفرم"
              value={faInt(er?.data.villas_now.multi_platform)}
              detail={er ? `از ${faInt(er.data.villas_now.villas)} ویلای یکتا` : undefined}
              source={<SourceChip file={er?.file} generatedAt={er?.generated_at} />}
            />
            <MetricCard
              label="شب‌های «پنهان»"
              value={h3 ? faPercent(h3.hidden_nights / h3.nights_compared) : "—"}
              detail="شب‌هایی که در یک پلتفرم آزاد و در دیگری پرند"
              source={<SourceChip file={hypotheses?.file} generatedAt={hypotheses?.generated_at} />}
            />
            <MetricCard
              tone="verified"
              label="دقت تطبیق ویلاها"
              value={configured ? faPercent(configured.metrics.precision.estimate) : "—"}
              detail={
                configured
                  ? `بازه‌ی ۹۵٪: ${faInterval(configured.metrics.precision).split("(")[1]?.replace(")", "") ?? ""}`
                  : undefined
              }
              source={<SourceChip file={er?.file} generatedAt={er?.generated_at} />}
            />
          </MetricGrid>
          {h4 ? (
            <p className="mt-3 text-sm text-fg-muted">
              ادعای مکانی یا امکاناتی که نقشه رد می‌کند یا آگهی دیگر همان ویلا خلافش را می‌گوید:{" "}
              {h4.data.platforms
                .map(
                  (p) =>
                    `${p.platform === "jabama" ? "جاباما" : "شب"} ${faPercent(p.share.estimate)}`,
                )
                .join("، ")}{" "}
              از آگهی‌ها.
            </p>
          ) : null}
        </Section>

        <Section id="how" eyebrow="چطور کار می‌کند" title="از آگهی‌های پراکنده تا یک ویلای سنجیده">
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ Icon, title, text }, index) => (
              <li
                key={title}
                className="rounded-card border border-line bg-surface p-5 shadow-raised"
              >
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-full bg-brand-50 text-brand-700">
                    <Icon aria-hidden="true" className="size-5" />
                  </span>
                  <span className="text-sm font-semibold text-fg-subtle tabular-nums">
                    {faInt(index + 1)}
                  </span>
                </div>
                <p className="mt-4 font-semibold">{title}</p>
                <p className="mt-1 text-sm text-pretty text-fg-muted">{text}</p>
              </li>
            ))}
          </ol>
        </Section>

        {villas.length > 0 ? (
          <Section
            id="villas"
            eyebrow="روی هر دو پلتفرم"
            title="ویلاهایی که یکی شده‌اند"
            description="هر کارت یک ویلای واقعی است با آگهی‌هایش در جاباما و شب؛ قیمت هر پلتفرم جدا می‌ماند."
            action={
              <ButtonLink href="/search" variant="ghost">
                جستجوی ویلا
                <ArrowLeft aria-hidden="true" className="size-4" />
              </ButtonLink>
            }
          >
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {villas.map((v) => (
                <li key={v.id} className="flex">
                  <VillaCard id={v.id} members={v.members} />
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        <Section id="principles" eyebrow="قاعده‌ها" title="چرا می‌شود به این صفحه‌ها اعتماد کرد">
          <ul className="grid gap-4 sm:grid-cols-2">
            {PRINCIPLES.map(([title, text]) => (
              <li key={title} className="flex gap-3 rounded-card border border-line bg-surface p-5">
                <Scale aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-brand-700" />
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="mt-1 text-sm text-pretty text-fg-muted">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </Section>

        <section
          aria-labelledby="docs-cta"
          className="flex flex-col items-start gap-5 rounded-card bg-brand-900 p-8 text-white sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="max-w-xl">
            <h2 id="docs-cta" className="text-xl font-semibold text-balance">
              گزارش فنی کامل پروژه
            </h2>
            <p className="mt-2 text-sm text-pretty text-brand-100">
              معماری، ارزیابی تطبیق ویلاها، فرضیه‌ها، هزینه‌ی مدل‌ها، تست‌ها و وضعیت هر معیار پذیرش؛
              همه از داده‌ی واقعی پروژه.
            </p>
          </div>
          <ButtonLink href="/docs" variant="secondary" size="lg" className="border-transparent">
            <BookOpenText aria-hidden="true" className="size-5" />
            مستندات پروژه
          </ButtonLink>
        </section>
      </div>
    </>
  );
}
