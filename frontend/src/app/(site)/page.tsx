import { ArrowLeft, CalendarRange, Fingerprint, Search, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { HeroMap } from "@/components/home/hero-map";
import { HomeVillaCard } from "@/components/home/villa-card";
import { ButtonLink } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { ChipLink } from "@/components/ui/chip";
import { apiClient, type Listing, type Offer } from "@/lib/api/client";
import { latest } from "@/lib/artifacts";
import { readBasemap } from "@/lib/basemap";
import { faDay } from "@/lib/calendar";
import { apiBaseUrl, fetchHealth } from "@/lib/health";
import { faNum, faPct } from "@/lib/numbers";
import { EXAMPLE_QUERIES } from "@/lib/search";

export const metadata: Metadata = { title: { absolute: "ویلاسنج · یک ویلا، همه‌ی حقیقت" } };
export const dynamic = "force-dynamic";

const FEATURED = 6;

const STEPS = [
  {
    Icon: Search,
    title: "فارسی بنویسید",
    text: "«ویلای استخردار برای ۶ نفر آخر هفته‌ی بعد»؛ ما شرط‌ها را می‌فهمیم و نشان می‌دهیم.",
  },
  {
    Icon: Fingerprint,
    title: "یک ویلا، نه چند آگهی",
    text: "آگهی‌های یک ویلا در جاباما و شب یکی می‌شوند، با شاهد: عکس‌های مشترک و موقعیت.",
  },
  {
    Icon: CalendarRange,
    title: "قیمت هر پلتفرم برای سفر شما",
    text: "برای تاریخ و تعداد نفر شما، کنار هم؛ و شب‌هایی که فقط در یک پلتفرم خالی‌اند.",
  },
  {
    Icon: ShieldCheck,
    title: "ادعاها سنجیده",
    text: "«۵ دقیقه تا دریا» در برابر نقشه؛ هر عدد منبع و زمان مشاهده دارد.",
  },
] as const;

type Featured = { id: string; members: Listing[]; offers: Offer[] };

async function featuredVillas(): Promise<{ villas: Featured[]; stay: string }> {
  try {
    const api = apiClient();
    const [sample, scenarios] = await Promise.all([
      api.GET("/villas/sample", {
        params: { query: { n: FEATURED, seed: "home" } },
        cache: "no-store",
      }),
      api.GET("/scenarios", { cache: "no-store" }),
    ]);
    const scenario = scenarios.data?.[0];
    const guests = scenario?.guests[0] ?? 4;
    const villas = await Promise.all(
      (sample.data ?? []).map(async ({ villa_id }) => {
        const path = { villa_id };
        const [villa, offers] = await Promise.all([
          api.GET("/villas/{villa_id}", { params: { path }, cache: "no-store" }),
          scenario
            ? api.GET("/villas/{villa_id}/offers", {
                params: {
                  path,
                  query: { check_in: scenario.check_in, check_out: scenario.check_out, guests },
                },
                cache: "no-store",
              })
            : Promise.resolve({ data: [] as Offer[] }),
        ]);
        return villa.data
          ? { id: villa.data.id, members: villa.data.members, offers: offers.data ?? [] }
          : null;
      }),
    );
    return {
      villas: villas.filter((v): v is Featured => v !== null),
      stay: scenario
        ? `برای ${scenario.name} (${faDay(scenario.check_in)})، ${faNum(guests)} نفر`
        : "",
    };
  } catch {
    return { villas: [], stay: "" };
  }
}

export default async function HomePage() {
  const [er, health, featured, basemap] = await Promise.all([
    latest("er-eval"),
    fetchHealth(apiBaseUrl()),
    featuredVillas(),
    readBasemap(),
  ]);
  const configured = er?.data.revised.policies.find((p) => p.configured);
  const llmDown = health !== null && health.checks.llm?.ok === false;
  const points = featured.villas.flatMap((v) =>
    v.members
      .filter((m) => m.location)
      .slice(0, 1)
      .map((m) => ({ lat: m.location?.lat ?? 0, lon: m.location?.lon ?? 0 })),
  );
  return (
    <>
      <section aria-labelledby="hero-title" className="border-b border-line">
        <div className="mx-auto grid max-w-7xl items-center gap-8 px-4 pt-10 pb-10 sm:px-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:pt-14">
          <div>
            <p className="text-sm font-semibold text-accent">ترب برای ویلا · رامسر تا تنکابن</p>
            <h1
              id="hero-title"
              className="mt-3 text-4xl font-extrabold text-balance text-fg sm:text-5xl"
            >
              یک ویلا، همه‌ی حقیقت
            </h1>
            <p className="mt-4 max-w-xl text-lg text-pretty text-fg-muted">
              ویلای مناسب را فارسی بنویسید؛ قیمت هر پلتفرم را برای سفر خودتان کنار هم ببینید.
            </p>
            <form action="/search" method="get" role="search" className="mt-7 max-w-2xl">
              <label htmlFor="home-q" className="sr-only">
                ویلای مورد نظرتان را توصیف کنید
              </label>
              <div className="flex h-16 items-center gap-2 rounded-full border border-line-strong bg-surface p-2 ps-5 shadow-float focus-within:border-brand-500">
                <Search aria-hidden="true" className="size-5 shrink-0 text-fg-subtle" />
                <input
                  id="home-q"
                  name="q"
                  required
                  placeholder="مثلاً: ویلای استخردار نزدیک دریا برای ۶ نفر، آخر هفته، تا ۲۰ میلیون"
                  className="h-full min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-fg-subtle"
                />
                <button
                  type="submit"
                  className="focus-ring h-12 shrink-0 rounded-full bg-brand-gradient px-6 font-semibold text-white shadow-raised hover:opacity-95"
                >
                  جستجو
                </button>
              </div>
            </form>
            <ul aria-label="نمونه‌ی جستجو" className="mt-4 flex flex-wrap gap-2">
              {EXAMPLE_QUERIES.map((q) => (
                <li key={q}>
                  <ChipLink href={`/search?${new URLSearchParams({ q })}`}>{q}</ChipLink>
                </li>
              ))}
            </ul>
            {llmDown ? (
              <Callout kind="degraded" title="مدل زبانی فعلاً در دسترس نیست" className="mt-6">
                جستجوهای نمونه از حافظه پاسخ می‌گیرند؛ صفحه‌ی ویلاها، قیمت‌ها و تقویم‌ها بدون مدل
                کار می‌کنند.
              </Callout>
            ) : null}
          </div>
          <div className="hidden h-80 lg:block xl:h-96">
            <HeroMap basemap={basemap?.pmtiles ?? null} points={points} />
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-16 px-4 pt-10 sm:px-6">
        {featured.villas.length > 0 ? (
          <section aria-labelledby="villas-title">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="villas-title" className="text-2xl font-bold text-balance">
                  ویلاهایی که در هر دو پلتفرم پیدا کردیم
                </h2>
                <p className="mt-1 text-sm text-fg-muted">
                  هر کارت یک ویلای واقعی است و قیمت هر پلتفرم جداست. {featured.stay}.
                </p>
              </div>
              <ButtonLink href="/search" variant="ghost">
                جستجوی ویلا
                <ArrowLeft aria-hidden="true" className="size-4" />
              </ButtonLink>
            </div>
            <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {featured.villas.map((v) => (
                <li key={v.id} className="flex">
                  <HomeVillaCard
                    id={v.id}
                    members={v.members}
                    offers={v.offers}
                    stayText={featured.stay}
                  />
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section aria-labelledby="how-title">
          <h2 id="how-title" className="text-2xl font-bold text-balance">
            چطور کار می‌کند
          </h2>
          <ol className="mt-5 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ Icon, title, text }) => (
              <li key={title}>
                <Icon aria-hidden="true" className="size-6 text-brand-700" />
                <p className="mt-2 font-semibold">{title}</p>
                <p className="mt-1 text-sm text-pretty text-fg-muted">{text}</p>
              </li>
            ))}
          </ol>
        </section>

        {er ? (
          <Link
            href="/metrics"
            data-proof-strip=""
            className="focus-ring flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-card border border-line bg-surface px-5 py-4 text-sm tabular-nums hover:border-brand-400"
          >
            <span>
              <strong>{faNum(er.data.villas_now.villas)}</strong> ویلا
            </span>
            <span aria-hidden="true" className="text-fg-subtle">
              ·
            </span>
            <span>
              <strong>{faNum(er.data.villas_now.multi_platform)}</strong> ویلا در هر دو پلتفرم
            </span>
            {configured?.metrics.precision.estimate != null ? (
              <>
                <span aria-hidden="true" className="text-fg-subtle">
                  ·
                </span>
                <span>
                  دقت تطبیق <strong>{faPct(configured.metrics.precision.estimate, 0)}</strong>
                </span>
              </>
            ) : null}
            <span className="text-accent">سنجه‌ها ←</span>
          </Link>
        ) : null}
      </div>
    </>
  );
}
