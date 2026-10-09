import { BookOpen, Compass, PlayCircle } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { DocHeader, InfoCard } from "@/components/docs/blocks";
import { Diagram } from "@/components/docs/diagram";
import { CriteriaProgress, MilestoneGrid, OpenItems } from "@/components/docs/milestones";
import { Heading } from "@/components/docs/prose";
import { ButtonLink } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { docsNav } from "@/content/docs-nav";
import { latest } from "@/lib/artifacts";
import { BRAND } from "@/lib/copy";
import { formatFor } from "@/lib/format";
import { docsHref, t, type Locale } from "@/lib/i18n";

/** The portal index's metadata in one language. */
export function docsHomeMetadata(locale: Locale): Metadata {
  return locale === "en"
    ? {
        title: { absolute: `Documentation · ${BRAND.en.name}` },
        description: BRAND.en.description,
      }
    : {
        title: { absolute: `مستندات · ${BRAND.name}` },
        description: BRAND.description,
      };
}

/** The interval part of "98.1% (93.0 to 99.5%)": "93.0 to 99.5%". */
const bounds = (formatted: string) => formatted.split("(")[1]?.replace(")", "") ?? "-";

async function KeyMetrics({ locale }: { locale: Locale }) {
  const f = formatFor(locale);
  const [er, hyp, h4, quality] = await Promise.all([
    latest("er-eval"),
    latest("hypotheses"),
    latest("h4"),
    latest("quality"),
  ]);
  const policy = er?.data.revised.policies.find((p) => p.configured);
  const chip = (a: { file: string; generated_at: string } | null) =>
    a ? <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} /> : null;
  const passed = quality?.data.suites.reduce((n, s) => n + s.passed, 0);
  const failed = quality?.data.suites.reduce((n, s) => n + s.failed, 0);
  const ci = bounds(f.interval(policy?.metrics.precision));
  return (
    <MetricGrid className="lg:grid-cols-3">
      <MetricCard
        tone="verified"
        label={t(locale, "دقت تطبیق ویلاها", "Entity resolution precision")}
        value={f.percent(policy?.metrics.precision.estimate)}
        detail={t(
          locale,
          `بازه‌ی ۹۵٪ ${ci}؛ معیار: ≥ ۹۵٪ با کران پایین ≥ ۹۲٪`,
          `95% CI ${ci}; target: ≥ 95% with a lower bound ≥ 92%`,
        )}
        source={chip(er)}
      />
      <MetricCard
        label={t(locale, "ویلای یکتا از آگهی‌ها", "Distinct villas from the listings")}
        value={f.int(er?.data.villas_now.villas)}
        detail={t(
          locale,
          `${f.int(er?.data.villas_now.listings)} آگهی؛ ${f.int(er?.data.villas_now.multi_platform)} ویلا روی هر دو پلتفرم`,
          `${f.int(er?.data.villas_now.listings)} listings; ${f.int(er?.data.villas_now.multi_platform)} villas on both platforms`,
        )}
        source={chip(er)}
      />
      <MetricCard
        label={t(locale, "شب‌های پنهان (H3)", "Hidden nights (H3)")}
        value={
          hyp
            ? f.percent(hyp.data.h3.hidden_nights / Math.max(1, hyp.data.h3.nights_compared))
            : "-"
        }
        detail={t(
          locale,
          "شب‌هایی که روی یک پلتفرم آزاد و روی دیگری پر است",
          "Nights free on one platform and taken on the other",
        )}
        source={chip(hyp)}
      />
      <MetricCard
        tone={failed ? "danger" : quality ? "verified" : "neutral"}
        label={t(locale, "تست‌ها", "Tests")}
        value={quality ? f.int(passed) : "-"}
        detail={
          quality
            ? failed
              ? t(locale, `${f.int(failed)} شکست`, `${f.int(failed)} failed`)
              : t(locale, "همه پاس شدند؛ lint بدون خطا", "All passing; lint clean")
            : t(locale, "make quality-report هنوز اجرا نشده", "make quality-report has not run yet")
        }
        source={chip(quality)}
      />
      {h4
        ? h4.data.platforms.map((p) => {
            const platform =
              p.platform === "jabama" ? t(locale, "جاباما", "Jabama") : t(locale, "شب", "Shab");
            const share = bounds(f.interval(p.share));
            return (
              <MetricCard
                key={p.platform}
                label={t(
                  locale,
                  `آگهی با ادعای مغایر با نقشه یا پلتفرم دیگر · ${platform}`,
                  `Listings with a claim the map or the other platform contradicts · ${platform}`,
                )}
                value={f.percent(p.share.estimate)}
                detail={t(locale, `بازه‌ی ۹۵٪ ${share} (H4)`, `95% CI ${share} (H4)`)}
                source={chip(h4)}
              />
            );
          })
        : null}
    </MetricGrid>
  );
}

/** The portal's index page: what Villasanj is, the headline numbers, status and the sections. */
export function DocsHome({ locale }: { locale: Locale }) {
  const href = (path: string) => docsHref(path, locale);
  const brand = locale === "en" ? BRAND.en : BRAND;
  return (
    <>
      <DocHeader
        eyebrow={t(locale, "مستندات پروژه · گزارش فنی", "Project documentation · technical report")}
        title={`${brand.name}: ${brand.tagline}`}
        meta={
          <>
            <ButtonLink href={href("/docs/demo")} size="sm">
              <PlayCircle aria-hidden="true" className="size-4" />
              {t(locale, "راهنمای دمو و بازبینی", "Demo and review guide")}
            </ButtonLink>
            <ButtonLink href={href("/docs/milestones")} size="sm" variant="secondary">
              <Compass aria-hidden="true" className="size-4" />
              {t(locale, "وضعیت معیارها", "Criteria status")}
            </ButtonLink>
            <ButtonLink href="/" size="sm" variant="ghost">
              {t(locale, "بازگشت به محصول", "Back to the product")}
            </ButtonLink>
          </>
        }
      >
        <p>{brand.description}</p>
        <p>
          {t(
            locale,
            "آگهی‌های یک ویلای واقعی روی چند پلتفرم اجاره پخش است و هر آگهی قیمت، تقویم و ادعاهای خودش را دارد. ویلاسنج آگهی‌های جاباما و شب را در منطقه‌ی رامسر تا تنکابن با خزش مؤدبانه جمع می‌کند، آگهی‌های یک ویلا را بدون شناسه‌ی مشترک به هم وصل می‌کند و برای هر ویلا یک صفحه می‌سازد: قیمت هر پلتفرم با منبعش، تقویم یکپارچه، نظرها و راستی‌آزمایی ادعاها. جستجو پرسش فارسی را می‌فهمد، رتبه‌بندی‌اش شفاف است و توضیحش هیچ عددی را از خودش نمی‌سازد.",
            "A real villa's listings are spread across rental platforms, and each listing has its own price, calendar and claims. Villasanj collects the Jabama and Shab listings in the Ramsar to Tonekabon region by polite crawling, links the listings of one villa without a shared identifier, and builds one page per villa: each platform's price with its source, the merged calendar, the reviews and a truth check of the claims. Search understands a Persian query, its ranking is transparent, and its explanation never makes up a number.",
          )}
        </p>
      </DocHeader>

      <Callout
        kind="verified"
        title={t(locale, "وضعیت فعلی: هیچ معیاری باز نیست", "Current status: no criterion is open")}
      >
        {locale === "en" ? (
          <>
            Every acceptance criterion is either done or explicitly closed by the owner (a new
            platform, the direct quote, the explanation latency without the cache, and the relevance
            evaluation on 11 judged queries instead of 30). The human reviews are done and their
            results are in the{" "}
            <Link className="focus-ring rounded-sm underline" href={href("/docs/milestones")}>
              milestones
            </Link>{" "}
            and the reports; the cache for the demo paths is warm.
          </>
        ) : (
          <>
            همه‌ی معیارهای پذیرش یا انجام شده‌اند یا مالک صریحاً آن‌ها را بسته است (پلتفرم تازه،
            قیمت مستقیم، تأخیر توضیح بدون کش، و ارزیابی مرتبط‌بودن نتایج با ۱۱ پرسش داوری‌شده به‌جای
            ۳۰). بازبینی‌های انسانی انجام شده و نتیجه‌شان در{" "}
            <Link className="focus-ring rounded-sm underline" href={href("/docs/milestones")}>
              مایل‌استون‌ها
            </Link>{" "}
            و گزارش‌ها آمده است؛ کش مسیرهای دمو گرم است.
          </>
        )}
      </Callout>

      <Heading as="h2" id="metrics">
        {t(locale, "سنجه‌های کلیدی", "Key metrics")}
      </Heading>
      <p className="mb-4 text-pretty text-fg-muted">
        {t(
          locale,
          "هر عدد از یک گزارش تولیدشده خوانده می‌شود و منبعش (فایل، فرمان و زمان تولید) کنارش است.",
          "Every number is read from a generated report, and its source (file, command and time of generation) sits next to it.",
        )}
      </p>
      <KeyMetrics locale={locale} />

      <Heading as="h2" id="milestones">
        {t(locale, "مایل‌استون‌ها", "Milestones")}
      </Heading>
      <div className="space-y-4">
        <CriteriaProgress locale={locale} />
        <MilestoneGrid locale={locale} />
      </div>

      <Heading as="h2" id="architecture">
        {t(locale, "معماری در یک نگاه", "Architecture at a glance")}
      </Heading>
      <p className="text-pretty text-fg">
        {t(
          locale,
          "یک monolith ماژولار با معماری شش‌ضلعی: شش زمینه‌ی مستقل (bounded context) با جهت وابستگی ثابت، دامنه‌ی خالص و یک composition root دست‌نویس. همه‌چیز در Postgres است: کاتالوگ، صف خزش، بردارها، داده‌ی جغرافیایی، کش و دفتر هزینه‌ی مدل زبانی.",
          "A modular monolith with a hexagonal architecture: six bounded contexts with a fixed dependency direction, a pure domain and a hand-written composition root. Postgres holds everything: the catalog, the crawl queue, the vectors, the geodata, the cache and the LLM cost ledger.",
        )}
      </p>
      <Diagram
        name="system-architecture"
        caption={t(
          locale,
          "اجزای سامانه و جریان درخواست",
          "System components and the request flow",
        )}
        locale={locale}
      />

      <Heading as="h2" id="sections">
        {t(locale, "بخش‌های مستندات", "Documentation sections")}
      </Heading>
      <div className="space-y-8">
        {/* The first group ("start here") is this page and its two neighbours, linked above. */}
        {docsNav(locale)
          .slice(1)
          .map((group, i) => (
            <section key={group.title} aria-labelledby={`group-${i + 1}`}>
              <h3 id={`group-${i + 1}`} className="mb-3 flex items-center gap-2 font-semibold">
                <BookOpen aria-hidden="true" className="size-4 text-fg-muted" />
                {group.title}
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {group.pages.map((p) => (
                  <InfoCard key={p.href} title={p.title} href={p.href} locale={locale}>
                    {p.summary}
                  </InfoCard>
                ))}
              </div>
            </section>
          ))}
      </div>

      <Heading as="h2" id="open">
        {t(locale, "آنچه هنوز باز است", "What is still open")}
      </Heading>
      <OpenItems locale={locale} />
    </>
  );
}
