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
import { DOCS_NAV } from "@/content/docs-nav";
import { latest } from "@/lib/artifacts";
import { faInt, faInterval, faPercent } from "@/lib/format";

export const metadata: Metadata = {
  title: { absolute: "مستندات پروژه · ویلاسنج" },
  description: "گزارش فنی ویلاسنج: معماری، تطبیق ویلاها، جستجو، حقیقت‌سنجی، ارزیابی‌ها و وضعیت.",
};
export const dynamic = "force-dynamic";

async function KeyMetrics() {
  const [er, hyp, h4, quality] = await Promise.all([
    latest("er-eval"),
    latest("hypotheses"),
    latest("h4"),
    latest("quality"),
  ]);
  const policy = er?.data.revised.policies.find((p) => p.configured);
  const chip = (a: { file: string; generated_at: string } | null) =>
    a ? <SourceChip file={a.file} generatedAt={a.generated_at} /> : null;
  const passed = quality?.data.suites.reduce((n, s) => n + s.passed, 0);
  const failed = quality?.data.suites.reduce((n, s) => n + s.failed, 0);
  return (
    <MetricGrid className="lg:grid-cols-3">
      <MetricCard
        tone="verified"
        label="دقت تطبیق ویلاها"
        value={faPercent(policy?.metrics.precision.estimate)}
        detail={`بازه‌ی ۹۵٪ ${faInterval(policy?.metrics.precision).split("(")[1]?.replace(")", "") ?? "—"}؛ معیار: ≥ ۹۵٪ با کران پایین ≥ ۹۲٪`}
        source={chip(er)}
      />
      <MetricCard
        label="ویلای یکتا از آگهی‌ها"
        value={faInt(er?.data.villas_now.villas)}
        detail={`${faInt(er?.data.villas_now.listings)} آگهی؛ ${faInt(er?.data.villas_now.multi_platform)} ویلا روی هر دو پلتفرم`}
        source={chip(er)}
      />
      <MetricCard
        label="شب‌های پنهان (H3)"
        value={
          hyp
            ? faPercent(hyp.data.h3.hidden_nights / Math.max(1, hyp.data.h3.nights_compared))
            : "—"
        }
        detail="شب‌هایی که روی یک پلتفرم آزاد و روی دیگری پر است"
        source={chip(hyp)}
      />
      <MetricCard
        tone={failed ? "danger" : quality ? "verified" : "neutral"}
        label="تست‌ها"
        value={quality ? faInt(passed) : "—"}
        detail={
          quality
            ? failed
              ? `${faInt(failed)} شکست`
              : "همه پاس؛ lint پاک"
            : "make quality-report هنوز اجرا نشده"
        }
        source={chip(quality)}
      />
      {h4
        ? h4.data.platforms.map((p) => (
            <MetricCard
              key={p.platform}
              label={`آگهی با ادعای ردشده یا ناهمخوان · ${p.platform === "jabama" ? "جاباما" : "شب"}`}
              value={faPercent(p.share.estimate)}
              detail={`بازه‌ی ۹۵٪ ${faInterval(p.share).split("(")[1]?.replace(")", "") ?? "—"} (H4)`}
              source={chip(h4)}
            />
          ))
        : null}
    </MetricGrid>
  );
}

export default function DocsHome() {
  return (
    <>
      <DocHeader
        eyebrow="مستندات پروژه · گزارش فنی"
        title="ویلاسنج: یک ویلا، همه‌ی حقیقت"
        meta={
          <>
            <ButtonLink href="/docs/demo" size="sm">
              <PlayCircle aria-hidden="true" className="size-4" />
              راهنمای دمو و بازبین
            </ButtonLink>
            <ButtonLink href="/docs/milestones" size="sm" variant="secondary">
              <Compass aria-hidden="true" className="size-4" />
              وضعیت معیارها
            </ButtonLink>
            <ButtonLink href="/" size="sm" variant="ghost">
              بازگشت به محصول
            </ButtonLink>
          </>
        }
      >
        <p>
          آگهی‌های یک ویلای واقعی روی پلتفرم‌های اجاره پخش است و هر کدام قیمت، تقویم و ادعای خودش را
          دارد. ویلاسنج آگهی‌های جاباما و شب را در منطقه‌ی رامسر تا تنکابن با crawl مؤدبانه جمع
          می‌کند، آگهی‌های یک ویلا را بدون شناسه‌ی مشترک به هم وصل می‌کند و برای هر ویلا یک صفحه
          می‌سازد: قیمت نهایی هر پلتفرم با منبعش، تقویم یکپارچه، نظرها و حقیقت‌سنجی ادعاها. جستجو
          پرسش فارسی را می‌فهمد، رتبه‌بندی‌اش شفاف است و توضیحش هیچ عددی را از خودش نمی‌سازد.
        </p>
      </DocHeader>

      <Callout kind="info" title="وضعیت فعلی: باقی‌مانده‌ها بازبینی‌های انسانی‌اند">
        همه‌ی معیارها جز دو معیار M8 بسته شده‌اند: یا انجام شده‌اند، یا مالک آن‌ها را بسته است
        (پلتفرم تازه، قیمت مستقیم و تأخیر توضیح بدون کش). دو معیار باز منتظر بازبینی مالک‌اند و
        ابزارشان در{" "}
        <Link className="focus-ring rounded-sm underline" href="/review">
          بازبینی‌های مالک
        </Link>{" "}
        است. حساب AvalAI دوباره شارژ شده و کش مسیرهای دمو گرم است؛ بدون مدل زبانی هم همه‌ی صفحه‌ها و
        پاسخ‌های کش‌شده کار می‌کنند.
      </Callout>

      <Heading as="h2" id="metrics">
        سنجه‌های کلیدی
      </Heading>
      <p className="mb-4 text-pretty text-fg-muted">
        هر عدد از یک گزارش تولیدشده خوانده می‌شود و منبعش (فایل، فرمان و زمان تولید) کنارش است.
      </p>
      <KeyMetrics />

      <Heading as="h2" id="milestones">
        مایل‌استون‌ها
      </Heading>
      <div className="space-y-4">
        <CriteriaProgress />
        <MilestoneGrid />
      </div>

      <Heading as="h2" id="architecture">
        معماری در یک نگاه
      </Heading>
      <p className="text-pretty text-fg">
        یک monolith ماژولار با معماری شش‌ضلعی: شش bounded context با جهت وابستگی ثابت، دامنه‌ی خالص،
        و یک composition root دست‌نویس. Postgres همه‌چیز را نگه می‌دارد: کاتالوگ، صف crawl، بردارها،
        داده‌ی جغرافیایی، کش و دفتر هزینه‌ی مدل زبانی.
      </p>
      <Diagram name="system-architecture" caption="اجزای سامانه و جریان درخواست" />

      <Heading as="h2" id="sections">
        بخش‌های مستندات
      </Heading>
      <div className="space-y-8">
        {DOCS_NAV.filter((g) => g.title !== "شروع").map((group) => (
          <section key={group.title} aria-labelledby={`group-${group.title}`}>
            <h3 id={`group-${group.title}`} className="mb-3 flex items-center gap-2 font-semibold">
              <BookOpen aria-hidden="true" className="size-4 text-fg-muted" />
              {group.title}
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {group.pages.map((p) => (
                <InfoCard key={p.href} title={p.title} href={p.href}>
                  {p.summary}
                </InfoCard>
              ))}
            </div>
          </section>
        ))}
      </div>

      <Heading as="h2" id="open">
        آنچه هنوز باز است
      </Heading>
      <OpenItems />
    </>
  );
}
