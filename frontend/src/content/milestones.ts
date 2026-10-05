/**
 * Milestones and their acceptance criteria: the single source for the portal's checklist
 * (/docs/milestones) and for the generated status tables in docs/ROADMAP.md (a test keeps them in
 * sync; UPDATE_ROADMAP=1 npm test rewrites them). Evidence that depends on a measurement is a
 * function of the generated artifacts, so it cannot go stale; dated historical results are text.
 */

import type { Status } from "@/components/ui/status";
import type {
  ErEval,
  H4,
  Hypotheses,
  Interval,
  JudgeEval,
  Performance,
  Quality,
  Relevance,
} from "@/lib/artifacts";
import { faDecimal, faInt, faInterval, faPercent, faRatio } from "@/lib/format";

export type { Status };

export type Evidence = {
  er: ErEval | null;
  hyp: Hypotheses | null;
  h4: H4 | null;
  judge: Record<string, JudgeEval>;
  quality: Quality | null;
  perf: Performance | null;
  relevance?: Relevance | null;
};

type Text = string | ((e: Evidence) => string);

export type Criterion = {
  n: number;
  title_fa: string;
  title_en: string;
  status: Status;
  evidence_fa: Text;
  evidence_en: Text;
  links?: { href: string; label: string }[];
};

export type Milestone = {
  id: string;
  name_fa: string;
  name_en: string;
  status: Status;
  date?: string; // when it was delivered or approved
  summary_fa: string;
  criteria: Criterion[];
};

// English formatting for the ROADMAP (Persian goes through lib/format).
const en = {
  pct: (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`,
  ci: (i: Interval | null | undefined) =>
    !i || i.estimate === null
      ? "—"
      : `${(i.estimate * 100).toFixed(1)}% (${(i.low * 100).toFixed(1)}–${(i.high * 100).toFixed(1)}%)`,
  int: (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : v.toLocaleString("en-US"),
};

const policy = (e: Evidence, name: string) => e.er?.revised.policies.find((p) => p.name === name);
const configured = (e: Evidence) => e.er?.revised.policies.find((p) => p.configured);
const judge = (e: Evidence) => e.judge["gemini-3.8-flash"];
const suite = (e: Evidence, prefix: string) =>
  e.quality?.suites.find((s) => s.name.startsWith(prefix));
const perf = (e: Evidence, name: string) => e.perf?.measurements.find((m) => m.name === name);

export const MILESTONES: Milestone[] = [
  {
    id: "M0",
    name_fa: "فهم و طراحی",
    name_en: "Understanding & design",
    status: "done",
    date: "2026-10-01",
    summary_fa: "خواندن چالش و گزارش پژوهشی، طراحی معماری، ADRهای ۱ تا ۱۰ و نقشه‌ی راه.",
    criteria: [
      {
        n: 1,
        title_fa: "همه‌ی فایل‌های زمینه خوانده و فهم خلاصه شد",
        title_en: "All context files read; understanding summarised",
        status: "done",
        evidence_fa: "تأیید مالک در ۹ مهر (۲۰۲۶-۱۰-۰۱).",
        evidence_en: "Approved by the owner on 2026-10-01.",
      },
      {
        n: 2,
        title_fa: "سخت‌افزار و محیط فهرست شد",
        title_en: "Hardware/environment inventoried",
        status: "done",
        evidence_fa: "Apple M4، ۱۶ گیگابایت، Docker با ۷٫۷۵ گیگابایت (CLAUDE.md).",
        evidence_en: "Apple M4, 16 GB, Docker with 7.75 GB (CLAUDE.md).",
      },
      {
        n: 3,
        title_fa: ".env بدون چاپ بررسی و فهرست مدل‌ها گرفته شد",
        title_en: ".env checked without printing; models fetched; tier inferred",
        status: "done",
        evidence_fa: "۳۶۵ مدل از /v1/models؛ tier ۳.",
        evidence_en: "365 models from /v1/models; tier 3.",
      },
      {
        n: 4,
        title_fa: "مدل هر کار با شاهد پیشنهاد شد",
        title_en: "Model per LLM task proposed with evidence",
        status: "done",
        evidence_fa: "ADR-0005؛ هزینه‌ی آزمایش حدود ۰٫۰۰۶ دلار.",
        evidence_en: "ADR-0005; probe spend about $0.006.",
      },
      {
        n: 5,
        title_fa: "هیچ کد اجرایی نوشته نشد",
        title_en: "No executable project code written",
        status: "done",
        evidence_fa: "فقط سند و تصمیم.",
        evidence_en: "Documents and decisions only.",
      },
    ],
  },
  {
    id: "M1",
    name_fa: "اسکلت و سکوی مدل زبانی",
    name_en: "Skeleton & LLM platform",
    status: "done",
    date: "2026-10-01",
    summary_fa:
      "monorepo، Docker، Postgres، دروازه‌ی مدل زبانی با کش و دفتر هزینه، قراردادهای معماری.",
    criteria: [
      {
        n: 1,
        title_fa: "استک روی clone تازه سالم بالا می‌آید",
        title_en: "Clean clone: make setup && make up healthy; make health",
        status: "done",
        evidence_fa: "setup ۱۷ ثانیه، up ۲۹ ثانیه (۹ مهر).",
        evidence_en: "Setup 17 s, up 29 s (2026-10-01).",
      },
      {
        n: 2,
        title_fa: "make lint بدون یافته",
        title_en: "make lint = 0 findings",
        status: "done",
        evidence_fa: (e) =>
          e.quality
            ? e.quality.lint.ok
              ? "پاک در آخرین گزارش کیفیت."
              : "در آخرین گزارش کیفیت شکست خورد."
            : "پاک (۹ مهر).",
        evidence_en: (e) =>
          e.quality
            ? e.quality.lint.ok
              ? "Clean in the latest quality report."
              : "Failed in the latest quality report."
            : "Clean (2026-10-01).",
      },
      {
        n: 3,
        title_fa: "تست معماری با fixture شکست‌خورنده",
        title_en: "Architecture test with deliberately failing fixtures",
        status: "done",
        evidence_fa: "خلوص دامنه، نبود نام پلتفرم در هسته، نبود نویسه‌ی نامرئی.",
        evidence_en: "Domain purity, no platform names in core, no invisible characters.",
      },
      {
        n: 4,
        title_fa: "تست‌های هسته؛ پوشش دامنه ≥ ۹۵٪",
        title_en: "Kernel tests; domain coverage ≥ 95%",
        status: "done",
        evidence_fa: (e) => {
          const c = e.quality?.coverage.find((x) => x.name === "domain");
          return c ? `پوشش دامنه ${faPercent(c.percent / 100)}.` : "۹۸٪ (۹ مهر).";
        },
        evidence_en: (e) => {
          const c = e.quality?.coverage.find((x) => x.name === "domain");
          return c ? `Domain coverage ${c.percent}%.` : "98% (2026-10-01).";
        },
      },
      {
        n: 5,
        title_fa: "تست‌های زنجیره‌ی مدل بدون شبکه",
        title_en: "LLM stack unit tests (zero network)",
        status: "done",
        evidence_fa:
          "کش، تلاش دوباره با بازخورد، پشتیبان، بودجه پیش از فراخوانی، dry-run بی‌فراخوانی، توقف با سقف کلید.",
        evidence_en:
          "Cache, validation retry, fallback, budget before calling, dry-run with 0 calls, stop on a spent key quota.",
      },
      {
        n: 6,
        title_fa: "تست زنده‌ی اختیاری زیر ۰٫۰۵ دلار",
        title_en: "Opt-in live test, spend < $0.05",
        status: "done",
        evidence_fa: "۰٫۰۰۲۵ دلار در هر اجرا (۹ مهر).",
        evidence_en: "$0.0025 per run (2026-10-01).",
      },
      {
        n: 7,
        title_fa: "بهداشت راز",
        title_en: "Secret hygiene",
        status: "done",
        evidence_fa: "تست repr و لاگ و خطا؛ gitleaks؛ .env در git نیست.",
        evidence_en: "repr/log/error tests; gitleaks; .env never committed.",
      },
      {
        n: 8,
        title_fa: "تطبیق دفتر هزینه با داشبورد AvalAI",
        title_en: "Ledger vs AvalAI dashboard",
        status: "done",
        evidence_fa: "مالک تطبیق دفتر هزینه با داشبورد AvalAI را تأیید کرد (۱۳ مهر).",
        evidence_en: "The owner confirmed the ledger against the AvalAI dashboard (2026-10-05).",
      },
    ],
  },
  {
    id: "M2",
    name_fa: "برش عمودی اول: جاباما ← شب",
    name_en: "First vertical slice: jabama → shab",
    status: "done",
    date: "2026-10-01",
    summary_fa: "crawl مؤدبانه‌ی دو پلتفرم، snapshot و parser خالص، نرمال‌سازی، اثبات OCP با شب.",
    criteria: [
      {
        n: 1,
        title_fa: "robots.txt، فاصله و توقف هنگام مسدودی",
        title_en: "robots.txt, pacing and stop-on-block tested",
        status: "done",
        evidence_fa: "تست واحد و یکپارچگی؛ هیچ درخواست ممنوعی فرستاده نشد.",
        evidence_en: "Unit and integration tested; no disallowed request was sent.",
      },
      {
        n: 2,
        title_fa: "همه‌ی آگهی‌های جاباما در منطقه؛ parse ≥ ۹۸٪",
        title_en: "jabama: every regional listing, parse ≥ 98%",
        status: "done",
        evidence_fa: "۱۰۰٪ parse؛ شکاف ۳۱ آگهی با دور دوم بسته شد.",
        evidence_en: "100% parsed; the 31-listing gap was closed by a second pass.",
      },
      {
        n: 3,
        title_fa: "≥ ۶ fixture برای هر adapter",
        title_en: "≥ 6 trimmed fixtures per adapter",
        status: "done",
        evidence_fa: "۶ برای جاباما، ۶ برای شب؛ بعداً fixture نظرها.",
        evidence_en: "6 for jabama, 6 for shab; review fixtures added later.",
      },
      {
        n: 4,
        title_fa: "≥ ۶۰ حالت نرمال‌ساز",
        title_en: "Normalizer ≥ 60 table-driven cases",
        status: "done",
        evidence_fa: "۱۱۱ حالت.",
        evidence_en: "111 cases.",
      },
      {
        n: 5,
        title_fa: "make reparse بی‌شبکه با hash یکسان",
        title_en: "make reparse: 0 network requests, identical hashes",
        status: "done",
        evidence_fa: "تست مسدودکننده‌ی socket؛ دو بازسازی با hash یکسان.",
        evidence_en: "Socket-blocking test; two rebuilds with identical hashes.",
      },
      {
        n: 6,
        title_fa: "اثبات OCP",
        title_en: "OCP proof",
        status: "done",
        evidence_fa:
          "کامیت شب فقط پوشه‌ی خودش، fixtureها و یک entry point را تغییر داد (با یک توسعه‌ی عمومی پیشین).",
        evidence_en:
          "The shab commit touched only its folder, fixtures and one entry point (after one generic core extension).",
      },
      {
        n: 7,
        title_fa: "برداشت سناریو ≥ ۹۰٪ در ۲۴ ساعت",
        title_en: "Scenario capture ≥ 90% within 24 h",
        status: "done",
        evidence_fa: "جاباما ۱۰۰٪، شب ۹۹٫۳٪.",
        evidence_en: "jabama 100%, shab 99.3%.",
      },
      {
        n: 8,
        title_fa: "موجودی منطقه",
        title_en: "Regional inventory",
        status: "done",
        evidence_fa: "۳٬۵۵۴ صفحه‌ی آگهی (۹ مهر).",
        evidence_en: "3,554 listing pages (2026-10-01).",
      },
    ],
  },
  {
    id: "M3",
    name_fa: "آزمون فرضیه‌ها",
    name_en: "Hypothesis test",
    status: "done",
    date: "2026-10-03",
    summary_fa: "gold-v1 با برچسب مالک، ارزیابی خط پایه، موتور قیمت و فرضیه‌های H1 تا H3.",
    criteria: [
      {
        n: 1,
        title_fa: "gold-v1 با ≥ ۳۰۰ برچسب طبقه‌بندی‌شده",
        title_en: "Gold set v1 ≥ 300 stratified labels, protocol, unsure rate",
        status: "done",
        evidence_fa: (e) =>
          e.er
            ? `${faInt(e.er.revised.labelled)} برچسب؛ نامطمئن ${faInterval(e.er.revised.unsure)} پس از اصلاح ${faInt(e.er.revisions.length)} برچسب.`
            : "۳۶۲ برچسب.",
        evidence_en: (e) =>
          e.er
            ? `${e.er.revised.labelled} labels; unsure ${en.ci(e.er.revised.unsure)} after ${e.er.revisions.length} label revisions.`
            : "362 labels.",
      },
      {
        n: 2,
        title_fa: "خط پایه با بازه‌ی Wilson و ماتریس درهم‌ریختگی",
        title_en: "Baseline P/R/F1 at the chosen threshold with Wilson CIs",
        status: "done",
        evidence_fa: (e) => {
          const r = e.er?.revised.gold_threshold;
          const o = e.er?.original.gold_threshold;
          return r
            ? `فقط قواعد، برچسب‌های اصلاح‌شده: آستانه‌ی ${r.threshold}، دقت ${faInterval(r.precision)}، بازیابی ${faInterval(r.recall)}. روی برچسب‌های اولیه: آستانه‌ی ${o?.threshold ?? "—"}، دقت ${faInterval(o?.precision)}.`
            : "—";
        },
        evidence_en: (e) => {
          const r = e.er?.revised.gold_threshold;
          const o = e.er?.original.gold_threshold;
          return r
            ? `Rules alone on revised labels: threshold ${r.threshold}, precision ${en.ci(r.precision)}, recall ${en.ci(r.recall)}. On the labels as first given: threshold ${o?.threshold ?? "—"}, precision ${en.ci(o?.precision)}.`
            : "—";
        },
      },
      {
        n: 3,
        title_fa: "موتور قیمت با پوشش شاخه‌ی ۱۰۰٪",
        title_en: "Pricing engine v1, 100% branch coverage on pricing/domain",
        status: "done",
        evidence_fa: (e) => {
          const c = e.quality?.coverage.find((x) => x.name === "pricing domain");
          return c
            ? `پوشش ${faPercent(c.percent / 100)}، در make test اجبار می‌شود.`
            : "در make test اجبار می‌شود.";
        },
        evidence_en: (e) => {
          const c = e.quality?.coverage.find((x) => x.name === "pricing domain");
          return c ? `Coverage ${c.percent}%, enforced by make test.` : "Enforced by make test.";
        },
      },
      {
        n: 4,
        title_fa: "گزارش H1 تا H3",
        title_en: "Hypothesis report H1–H3",
        status: "done",
        evidence_fa: (e) =>
          e.hyp
            ? `H1: ${faInt(e.hyp.h1.pairs)} جفت، حدود ${faInt(Math.round(e.hyp.h1.corrected_pairs?.estimate ?? 0))} پس از اصلاح؛ H2: میانه‌ی تعطیلات ${faRatio(e.hyp.h2.find((g) => g.scenario === "holiday")?.median_ratio)}؛ H3: ${faPercent(e.hyp.h3.hidden_nights / Math.max(1, e.hyp.h3.nights_compared))} شب پنهان.`
            : "—",
        evidence_en: (e) =>
          e.hyp
            ? `H1: ${e.hyp.h1.pairs} pairs, about ${Math.round(e.hyp.h1.corrected_pairs?.estimate ?? 0)} corrected; H2: holiday median ${e.hyp.h2.find((g) => g.scenario === "holiday")?.median_ratio?.toFixed(2)}×; H3: ${en.pct(e.hyp.h3.hidden_nights / Math.max(1, e.hyp.h3.nights_compared))} hidden nights.`
            : "—",
        links: [{ href: "/docs/evaluation", label: "ارزیابی و فرضیه‌ها" }],
      },
      {
        n: 5,
        title_fa: "بازبینی مالک و اولویت‌ها",
        title_en: "Owner review: M4–M11 priorities",
        status: "done",
        evidence_fa:
          "دستور مالک (۱۱ مهر): همه‌ی مایل‌استون‌ها تا جایی که وابستگی‌ها اجازه می‌دهند.",
        evidence_en:
          "Owner's instruction (2026-10-03): every milestone as far as dependencies allow.",
      },
    ],
  },
  {
    id: "M4",
    name_fa: "پوشش: پلتفرم‌ها، منطقه و برداشت هم‌زمان",
    name_en: "Coverage: platforms, region, same-window capture",
    status: "done",
    date: "2026-10-05",
    summary_fa:
      "برداشت هم‌زمان، خط لوله‌ی عکس و موجودی؛ مالک پلتفرم تازه نمی‌خواهد، پس دامنه جاباما و شب می‌ماند.",
    criteria: [
      {
        n: 1,
        title_fa: "adapter پلتفرم‌های دارای مجوز",
        title_en: "Adapters for platforms with written permission",
        status: "waived",
        evidence_fa:
          "مالک: پلتفرم تازه لازم نیست (۱۳ مهر). جاجیگا، اتاقک و میهمانشو crawl را در شرایط استفاده منع کرده‌اند (ADR-0011).",
        evidence_en:
          "The owner wants no new platform (2026-10-05); jajiga, otaghak and mihmansho forbid crawling in their terms (ADR-0011).",
      },
      {
        n: 2,
        title_fa: "گزارش پوشش منطقه",
        title_en: "Regional coverage reported per platform",
        status: "done",
        evidence_fa: (e) =>
          e.hyp
            ? `جاباما ${faInt(e.hyp.h1.listings.jabama)} و شب ${faInt(e.hyp.h1.listings.shab)} آگهی.`
            : "catalog inventory.",
        evidence_en: (e) =>
          e.hyp
            ? `jabama ${en.int(e.hyp.h1.listings.jabama)}, shab ${en.int(e.hyp.h1.listings.shab)} listings.`
            : "catalog inventory.",
      },
      {
        n: 3,
        title_fa: "برداشت هم‌زمان همه‌ی سناریوها با پراکندگی ≤ ۶ ساعت",
        title_en: "Same-window capture with spread ≤ 6 h",
        status: "done",
        evidence_fa: "۱۲ مهر: جاباما ۲٬۹۸۷ از ۲٬۹۸۷ در ۳٫۲ ساعت، شب ۵۹۷ از ۶۰۱ در ۰٫۶ ساعت.",
        evidence_en: "2026-10-03: jabama 2,987/2,987 in 3.2 h, shab 597/601 in 0.6 h.",
      },
      {
        n: 4,
        title_fa: "خط لوله‌ی عکس ≥ ۹۹٪",
        title_en: "Photo pipeline ≥ 99%, pHash, storage reported",
        status: "done",
        evidence_fa: "۱۰۰٪ عکس‌های انتخاب‌شده در هر دو پلتفرم؛ ۸٫۴۸ و ۱٫۰۹ گیگابایت.",
        evidence_en: "100% of selected photos on both platforms; 8.48 and 1.09 GB.",
      },
    ],
  },
  {
    id: "M5",
    name_fa: "تطبیق کامل ویلاها",
    name_en: "Full entity resolution",
    status: "done",
    date: "2026-10-04",
    summary_fa: "داور مدل‌زبانی، سیاست تصمیم، خوشه‌بندی مقید، صف انسانی و اصلاح برچسب‌ها.",
    criteria: [
      {
        n: 1,
        title_fa: "recall مرحله‌ی blocking ≥ ۹۸٪ با تعداد نامزدها",
        title_en: "Blocking recall ≥ 98% with the candidate count",
        status: "done",
        evidence_fa: (e) =>
          e.er
            ? `${faInterval(e.er.revised.blocking_recall)} روی جفت‌های «یکی است»؛ ${faInt(e.er.candidates?.total)} جفت نامزد، ${faInt(e.er.candidates?.blocked)} از blocking تولید.`
            : "—",
        evidence_en: (e) =>
          e.er
            ? `${en.ci(e.er.revised.blocking_recall)} of gold matches; ${en.int(e.er.candidates?.total)} candidate pairs, ${en.int(e.er.candidates?.blocked)} from production blocking.`
            : "—",
      },
      {
        n: 2,
        title_fa: "دقت سرتاسری ≥ ۹۵٪ با کران پایین ≥ ۹۲٪",
        title_en: "End-to-end precision ≥ 95% (Wilson low ≥ 92%), recall reported",
        status: "done",
        evidence_fa: (e) => {
          const c = configured(e);
          return c
            ? `سیاست فعلی (داور رد می‌کند، انسان ادغام می‌کند): دقت ${faInterval(c.metrics.precision)}، بازیابی ${faInterval(c.metrics.recall)}. فقط قواعد در ۰٫۲۵− دیگر پاس نمی‌شود: ${faInterval(policy(e, "rules alone")?.metrics.precision)}.`
            : "—";
        },
        evidence_en: (e) => {
          const c = configured(e);
          return c
            ? `Configured policy (judge vetoes, a human merges): precision ${en.ci(c.metrics.precision)}, recall ${en.ci(c.metrics.recall)}. Rules alone at −0.25 no longer pass: ${en.ci(policy(e, "rules alone")?.metrics.precision)}.`
            : "—";
        },
        links: [{ href: "/docs/entity-resolution", label: "تطبیق ویلاها" }],
      },
      {
        n: 3,
        title_fa: "P/R/F1، B-cubed و منحنی، قابل بازتولید",
        title_en: "Pairwise P/R/F1, B-cubed, PR curve; reproducible",
        status: "done",
        evidence_fa: "reports/er-eval-*.md از er report، با match run و dataset hash.",
        evidence_en: "reports/er-eval-*.md from er report, with the match run and dataset hash.",
      },
      {
        n: 4,
        title_fa: "مقایسه‌ی سه مدل داور؛ دقت «یکی است» ≥ ۹۵٪",
        title_en: "Judge bake-off; MATCH precision ≥ 95%",
        status: "done",
        evidence_fa: (e) => {
          const j = judge(e);
          return j
            ? `gemini-3.8-flash روی ${faInt(j.judged)} جفت gold: ${faInt(j.confusion.match?.match ?? 0)} حکم «یکی است» درست و ${faInt(j.false_matches)} نادرست؛ دقت وزن‌دار طبقه‌ها ${faInterval(j.by_confidence["0.8"]?.precision)} (بازه پهن است چون طبقه‌ها وزن متفاوت دارند).`
            : "ADR-0005.";
        },
        evidence_en: (e) => {
          const j = judge(e);
          return j
            ? `gemini-3.8-flash on ${j.judged} gold pairs: ${j.confusion.match?.match ?? 0} correct MATCH verdicts, ${j.false_matches} false; stratum-weighted precision ${en.ci(j.by_confidence["0.8"]?.precision)} (wide because strata carry different weights).`
            : "ADR-0005.";
        },
      },
      {
        n: 5,
        title_fa: "هیچ ویلایی دو آگهی از یک پلتفرم ندارد؛ هر ادغام قابل ردیابی",
        title_en: "≤ 1 listing per platform; every merge traceable",
        status: "done",
        evidence_fa: (e) =>
          e.er
            ? `قید پایگاه داده و تست؛ ادغام‌ها به تفکیک تصمیم‌گیرنده: ${Object.entries(
                e.er.villas_now.applied,
              )
                .map(([k, v]) => `${k} ${faInt(v)}`)
                .join("، ")}.`
            : "—",
        evidence_en: (e) =>
          e.er
            ? `DB constraint and tests; merges by decider: ${Object.entries(e.er.villas_now.applied)
                .map(([k, v]) => `${k} ${v}`)
                .join(", ")}.`
            : "—",
      },
      {
        n: 6,
        title_fa: "ablation برای H5",
        title_en: "Ablations (H5)",
        status: "done",
        evidence_fa: "عکس به‌تنهایی و شواهد دیگر به‌تنهایی به معیار نمی‌رسند؛ با هم می‌رسند.",
        evidence_en: "Photos alone and other evidence alone miss the bar; together they clear it.",
      },
      {
        n: 7,
        title_fa: "صف انسانی و حل بی‌اثر جانبی",
        title_en: "Human queue; idempotent resolution",
        status: "done",
        evidence_fa: (e) =>
          e.er
            ? `صف er-human: ${Object.entries(e.er.human_queue)
                .map(([k, v]) => `${k.replace("judge:", "")} ${faInt(v)}`)
                .join("، ")}؛ هر برچسب ویلاها را دوباره می‌سازد.`
            : "—",
        evidence_en: (e) =>
          e.er
            ? `Queue er-human: ${Object.entries(e.er.human_queue)
                .map(([k, v]) => `${k.replace("judge:", "")} ${v}`)
                .join(", ")}; each label rebuilds the villas.`
            : "—",
      },
    ],
  },
  {
    id: "M6",
    name_fa: "قیمت کامل و پیشنهادها",
    name_en: "Pricing complete & offers",
    status: "done",
    date: "2026-10-05",
    summary_fa: "پیشنهاد هر آگهی با منبع، بازه‌ها و تازگی؛ مقایسه با قیمت مستقیم ممکن نشد.",
    criteria: [
      {
        n: 1,
        title_fa: "هر جزء قیمت منبع دارد (تست property)",
        title_en: "Every quote component has provenance (property test)",
        status: "done",
        evidence_fa: "test_every_quote_carries_provenance_for_every_component.",
        evidence_en: "test_every_quote_carries_provenance_for_every_component.",
      },
      {
        n: 2,
        title_fa: "هر پیشنهاد دقیق، بازه یا «حداقل»",
        title_en: "Each offer EXACT, RANGE or OPEN, reported",
        status: "done",
        evidence_fa: "همه «حداقل»اند چون کارمزدها منتشر نمی‌شوند (pricing offers).",
        evidence_en: "All OPEN: no platform publishes its fees (pricing offers).",
      },
      {
        n: 3,
        title_fa: "مقایسه با قیمت مستقیم پلتفرم",
        title_en: "Direct-quote comparison on ≥ 100 listings",
        status: "waived",
        evidence_fa:
          "هیچ منبع عمومی قیمت مستقیم وجود ندارد؛ مالک معیار را بست (۱۳ مهر). پیشنهادها «حداقل» می‌مانند.",
        evidence_en:
          "No public direct-quote source exists; the owner closed the criterion (2026-10-05). Offers stay open-ended (≥ X).",
      },
      {
        n: 4,
        title_fa: "پیشنهاد قدیمی در API علامت می‌خورد",
        title_en: "Stale offers flagged in the API",
        status: "done",
        evidence_fa: "فیلد stale برای هر پیشنهاد (۲۴ ساعت).",
        evidence_en: "A stale flag on every offer (24 h).",
      },
    ],
  },
  {
    id: "M7",
    name_fa: "API و صفحه‌ی ویلا",
    name_en: "API & canonical villa page",
    status: "done",
    date: "2026-10-03",
    summary_fa: "صفحه‌ی یک ویلا با قیمت هر پلتفرم، تقویم یکپارچه، ناهمخوانی‌ها و نظرها.",
    criteria: [
      {
        n: 1,
        title_fa: "OpenAPI و client تایپ‌شده",
        title_en: "OpenAPI generated; TS client strict; contract tests",
        status: "done",
        evidence_fa: "make openapi-check.",
        evidence_en: "make openapi-check.",
      },
      {
        n: 2,
        title_fa: "smoke روی ۵۰ ویلای دوپلتفرمی",
        title_en: "Smoke over 50 multi-platform villas",
        status: "done",
        evidence_fa: (e) => {
          const s = suite(e, "smoke");
          return s
            ? `دو تست smoke (۵۰ آگهی نمونه و ۵۰ ویلای دوپلتفرمی نمونه): ${faInt(s.passed)} پاس، ${faInt(s.failed)} شکست.`
            : "make test-smoke.";
        },
        evidence_en: (e) => {
          const s = suite(e, "smoke");
          return s
            ? `Two smoke tests (50 sampled listings, 50 sampled two-platform villas): ${s.passed} passed, ${s.failed} failed.`
            : "make test-smoke.";
        },
      },
      {
        n: 3,
        title_fa: "هر عدد به منبعش پیوند دارد (E2E)",
        title_en: "Every number links to its provenance (E2E)",
        status: "done",
        evidence_fa: "۱۰ عدد تصادفی در صفحه‌های آگهی، ویلا و جستجو.",
        evidence_en: "10 random numbers on listing, villa and search pages.",
      },
      {
        n: 4,
        title_fa: "دسترسی‌پذیری بدون خطای جدی",
        title_en: "No critical axe violations; keyboard",
        status: "done",
        evidence_fa: (e) => {
          const s = suite(e, "E2E");
          return s
            ? `E2E (شامل axe): ${faInt(s.passed)} پاس، ${faInt(s.failed)} شکست.`
            : "make test-e2e.";
        },
        evidence_en: (e) => {
          const s = suite(e, "E2E");
          return s ? `E2E (with axe): ${s.passed} passed, ${s.failed} failed.` : "make test-e2e.";
        },
      },
      {
        n: 5,
        title_fa: "p95 ویلا و پیشنهادها < ۳۰۰ میلی‌ثانیه",
        title_en: "p95 villa + offers < 300 ms",
        status: "done",
        evidence_fa: (e) => {
          const m = perf(e, "villa + offers");
          return m
            ? `p95 ${faInt(Math.round(m.p95_ms))} میلی‌ثانیه روی ${faInt(m.samples)} ویلا.`
            : "make perf-report.";
        },
        evidence_en: (e) => {
          const m = perf(e, "villa + offers");
          return m ? `p95 ${m.p95_ms} ms on ${m.samples} villas.` : "make perf-report.";
        },
      },
    ],
  },
  {
    id: "M8",
    name_fa: "جستجو، رتبه و زمان رانندگی",
    name_en: "Search: intent, retrieval, ranking, drive time",
    status: "partial",
    summary_fa: "فهم پرسش با محافظ عدد، رتبه‌ی شفاف، گروه‌بندی ویلا و زمان رانندگی.",
    criteria: [
      {
        n: 1,
        title_fa: "ارزیابی فهم پرسش روی ۵۰ پرسش",
        title_en: "Query understanding eval on 50 queries",
        status: "provisional",
        evidence_fa:
          "روی پیش‌نویس ۵۰ پرسش (نوشته‌ی عامل): ۱۰۰٪ اسلات، ۰ عدد ساختگی، p95 ۱٫۴ ثانیه؛ تا بازبینی مالک در /label/queries موقت است.",
        evidence_en:
          "On the agent-written 50-query draft: 100% slots, 0 invented numbers, p95 1.4 s; provisional until the owner's review at /label/queries.",
      },
      {
        n: 2,
        title_fa: "ارزیابی بازیابی با ۳۰ پرسش داوری‌شده",
        title_en: "Retrieval eval: 30 queries with judged relevant villas",
        status: "owner_review",
        evidence_fa: (e) =>
          e.relevance
            ? `${faInt(e.relevance.judged)} از ${faInt(e.relevance.total)} پرسش داوری‌شده: ` +
              e.relevance.systems
                .map(
                  (x) =>
                    `${x.system} nDCG@10 ${x.ndcg_at_10 === null ? "—" : faDecimal(x.ndcg_at_10, 3)}، Recall@20 ${x.recall_at_20 === null ? "—" : faDecimal(x.recall_at_20, 3)}`,
                )
                .join("؛ ")
            : "۳۰ پرسش با ۹۴۶ ویلای تجمیع‌شده از رتبه‌بندی فعلی و دو baseline (ارزان‌ترین و بهترین امتیاز)، کور، در /label/relevance منتظر داوری مالک است. FTS و جستجوی برداری ساخته نشده‌اند؛ برداری فقط اگر nDCG@10 را دست‌کم ۰٫۰۳ بهتر کند.",
        evidence_en: (e) =>
          e.relevance
            ? `${e.relevance.judged}/${e.relevance.total} queries judged: ` +
              e.relevance.systems
                .map(
                  (x) =>
                    `${x.system} nDCG@10 ${x.ndcg_at_10?.toFixed(3) ?? "-"}, Recall@20 ${x.recall_at_20?.toFixed(3) ?? "-"}`,
                )
                .join("; ")
            : "30 queries with 946 pooled villas from the shipped ranking and two baselines (cheapest, best rated), blind, await the owner's grades at /label/relevance. FTS and dense retrieval are not built; dense ships only if it lifts nDCG@10 by ≥ 0.03.",
      },
      {
        n: 3,
        title_fa: "زمان رانندگی برای ۱۰۰٪ ویلاها با یادداشت پوشش",
        title_en: "Drive time for 100% of villas, coverage note",
        status: "done",
        evidence_fa: "OSRM بدون ترافیک از میدان آزادی برای همه‌ی ۳٬۵۸۸ آگهی.",
        evidence_en: "Free-flow OSRM from Azadi Square for all 3,588 listings.",
      },
      {
        n: 4,
        title_fa: "تفکیک امتیاز در API و UI",
        title_en: "Score breakdown in API and UI",
        status: "done",
        evidence_fa: "روی هر کارت نتیجه «چرا این رتبه؟».",
        evidence_en: "'Why this rank?' on every result card.",
      },
    ],
  },
  {
    id: "M9",
    name_fa: "غنی‌سازی و حقیقت‌سنجی",
    name_en: "Enrichment & truth check",
    status: "done",
    summary_fa: "ادعاهای فاصله و امکانات، شاهد عکس و نقشه، ناهمخوانی بین پلتفرم‌ها و H4.",
    criteria: [
      {
        n: 1,
        title_fa: "استخراج ادعا روی ۶۰ توضیح: دقت ≥ ۹۰٪، بازیابی ≥ ۸۰٪",
        title_en: "Claim extraction on 60 descriptions: P ≥ 90%, R ≥ 80%",
        status: "done",
        evidence_fa:
          "قواعد + باقی‌مانده‌ی مدل: دقت ۹۳٫۷٪ (۸۴٫۸ تا ۹۷٫۵)، بازیابی ۸۰٫۸٪ (۷۰٫۳ تا ۸۸٫۲)؛ همه‌ی نقل‌قول‌ها عینی (۱۱ مهر).",
        evidence_en:
          "Rules + LLM residue: precision 93.7% (84.8–97.5%), recall 80.8% (70.3–88.2%); every quote verbatim (2026-10-03).",
      },
      {
        n: 2,
        title_fa: "برچسب عکس روی ۳۰۰ عکس؛ زیر ۸۵٪ استفاده نمی‌شود",
        title_en: "Photo tags on 300 photos; < 85% precision unused",
        status: "done",
        evidence_fa:
          "۳۳۶ برچسب مالک؛ استخر، جکوزی، جنگل و باربیکیو استفاده می‌شوند؛ منظره‌ی دریا و شومینه نه.",
        evidence_en:
          "336 owner labels; pool, jacuzzi, forest, barbecue used; sea view and fireplace not.",
      },
      {
        n: 3,
        title_fa: "تست قاعده‌ی حکم",
        title_en: "Verdict rule tests (best case; walk and drive)",
        status: "done",
        evidence_fa: "تست‌های واحد.",
        evidence_en: "Unit tests.",
      },
      {
        n: 4,
        title_fa: "H4 با بازه‌ی اطمینان",
        title_en: "H4 measured with CI",
        status: "done",
        evidence_fa: (e) =>
          e.h4
            ? e.h4.platforms
                .map((p) => `${p.platform === "jabama" ? "جاباما" : "شب"} ${faInterval(p.share)}`)
                .join("، ") + "؛ فرضیه‌ی ≥ ۲۵٪ تأیید نشد."
            : "—",
        evidence_en: (e) =>
          e.h4
            ? e.h4.platforms.map((p) => `${p.platform} ${en.ci(p.share)}`).join(", ") +
              "; the ≥ 25% hypothesis is not supported."
            : "—",
      },
      {
        n: 5,
        title_fa: "برآورد dry-run در ±۲۵٪ دفتر هزینه",
        title_en: "Dry-run estimate within ±25% of the ledger",
        status: "done",
        evidence_fa: "خلاصه‌ی نظرها +۳٪؛ خواندن ادعاها +۲۲٪ پس از شمارش درخواست تکراری.",
        evidence_en:
          "Review summaries +3%; claim reading +22% after counting repeated requests once.",
      },
    ],
  },
  {
    id: "M10",
    name_fa: "نظرها و «چرا این ویلا؟»",
    name_en: "Reviews & “why this villa?”",
    status: "done",
    date: "2026-10-05",
    summary_fa: "خلاصه‌ی با ارجاع، توضیح با اسلات و بررسی‌گر، و الگوی ثابت.",
    criteria: [
      {
        n: 1,
        title_fa: "تست‌های بررسی‌گر",
        title_en: "Verifier unit tests",
        status: "done",
        evidence_fa: "عدد بیرون از اسلات، اسلات ناشناخته، مقایسه‌ی خلاف واقع، نکته‌ی بی‌ارجاع.",
        evidence_en:
          "Digits outside slots, unknown slots, contradicting comparisons, uncited points.",
      },
      {
        n: 2,
        title_fa: "۱۰۰٪ متن‌های نمایش‌داده بررسی‌شده؛ نرخ الگو",
        title_en: "100% of displayed text verified; fallback rate",
        status: "done",
        evidence_fa: "الگو ۰٪ در ارزیابی توضیح؛ ۴۸ از ۴۸ خلاصه در تلاش اول؛ بدون مدل، الگو.",
        evidence_en:
          "0% template in the explanation eval; 48/48 summaries first try; without a model, the template.",
      },
      {
        n: 3,
        title_fa: "بازبینی کور مالک: ≥ ۱۸ از ۲۰ وفادار",
        title_en: "Owner's blind review ≥ 18/20 faithful",
        status: "done",
        evidence_fa: "۲۰ از ۲۰.",
        evidence_en: "20/20.",
      },
      {
        n: 4,
        title_fa: "p95 توضیح ≤ ۴ ثانیه بدون کش",
        title_en: "Explanation p95 ≤ 4 s uncached",
        status: "waived",
        evidence_fa:
          "مالک تأخیر را با کش پذیرفت (۱۳ مهر): بدون کش p95 ۶٫۱ تا ۱۰٫۶ ثانیه است، ولی نتیجه‌ها منتظر توضیح نمی‌مانند و مسیرهای کش‌شده فوری‌اند.",
        evidence_en:
          "The owner accepted the latency with the cache (2026-10-05): uncached p95 is 6.1–10.6 s, but results do not wait for the explanation and cached paths are instant.",
      },
    ],
  },
  {
    id: "M11",
    name_fa: "صیقل دمو",
    name_en: "Demo polish",
    status: "done",
    date: "2026-10-05",
    summary_fa: "دموی آفلاین، سناریوی ۵ دقیقه‌ای، پورتال مستندات و سنجه‌ها.",
    criteria: [
      {
        n: 1,
        title_fa: "make demo از بسته‌ی محلی بدون شبکه",
        title_en: "make demo from a local bundle, no network but cached LLM answers",
        status: "done",
        evidence_fa:
          "پروژه‌ی جدا روی ۳۴۰۰، فقط کش مدل، بدون درخواست بیرونی؛ عکس‌ها از سرور پلتفرم‌اند.",
        evidence_en:
          "Separate project on :3400, cached model answers only, no outbound request; photos stay hotlinked.",
      },
      {
        n: 2,
        title_fa: "هر عدد سناریوی دمو در یک گزارش تولیدشده",
        title_en: "Every number in the demo script in a generated report",
        status: "done",
        evidence_fa: "docs/demo-script.md و صفحه‌ی راهنمای دمو.",
        evidence_en: "docs/demo-script.md and the demo guide page.",
      },
      {
        n: 3,
        title_fa: "هزینه ≤ ۳۰ دلار و تطبیق با داشبورد",
        title_en: "LLM spend ≤ $30 and reconciled with the dashboard",
        status: "done",
        evidence_fa:
          "دفتر هزینه زیر سقف ۳۰ دلار است و مالک تطبیقش با داشبورد AvalAI را تأیید کرد (۱۳ مهر).",
        evidence_en:
          "The ledger is under the $30 cap and the owner confirmed it against the AvalAI dashboard (2026-10-05).",
      },
      {
        n: 4,
        title_fa: "E2E سبز برای مسیرهای سناریو",
        title_en: "E2E green for the storyboard paths",
        status: "done",
        evidence_fa: (e) => {
          const s = suite(e, "E2E");
          return s ? `${faInt(s.passed)} تست E2E، ${faInt(s.failed)} شکست.` : "make test-e2e.";
        },
        evidence_en: (e) => {
          const s = suite(e, "E2E");
          return s ? `${s.passed} E2E tests, ${s.failed} failed.` : "make test-e2e.";
        },
      },
    ],
  },
];

export function text(value: Text, evidence: Evidence): string {
  return typeof value === "function" ? value(evidence) : value;
}

export const STATUS_EN: Record<Status, string> = {
  done: "✅ done",
  waived: "☑️ closed by the owner",
  partial: "◐ partly done",
  provisional: "⚠️ provisional",
  blocked: "⛔ blocked",
  deferred: "⏸ deferred",
  owner_review: "👤 needs the owner",
  not_met: "❌ not met",
};

/** What is still open, and why: the honest list for /docs/limitations and the ROADMAP. */
export type OpenItem = { kind: "owner" | "avalai" | "blocked" | "not_met"; fa: string; en: string };

export const OPEN_ITEMS: OpenItem[] = [
  {
    kind: "owner",
    fa: "بازبینی مجموعه‌ی ۵۰ پرسش جستجو در /label/queries (M8 معیار ۱).",
    en: "Review the 50-query set at /label/queries (M8 crit. 1).",
  },
  {
    kind: "owner",
    fa: "داوری مرتبط‌بودن ۹۴۶ ویلای تجمیع‌شده برای ۳۰ پرسش در /label/relevance (M8 معیار ۲).",
    en: "Grade the 946 pooled villas of 30 queries at /label/relevance (M8 crit. 2).",
  },
  {
    kind: "owner",
    fa: "برچسب‌زدن صف er-human در /label?queue=er-human تا هر جا مفید است؛ اول ۸۳ پیشنهاد داور.",
    en: "Label the er-human queue at /label?queue=er-human as far as useful; the judge's 83 suggestions first.",
  },
  {
    kind: "owner",
    fa: "بازبینی تجربه‌ی کاربری صفحه‌ی ویلا (M7).",
    en: "Review the villa page UX (M7).",
  },
  {
    kind: "owner",
    fa: "اینکه دموی آفلاین نسخه‌ی محلی عکس‌ها را نشان بدهد یا نه.",
    en: "Whether the offline demo may serve local copies of photos.",
  },
  {
    kind: "avalai",
    fa: "پس از بازبینی مجموعه‌ی پرسش‌ها: اجرای دوباره‌ی ارزیابی فهم پرسش روی آن (حدود ۰٫۰۷ دلار).",
    en: "After the query-set review: re-run the understanding eval on it (about $0.07).",
  },
  {
    kind: "avalai",
    fa: "اختیاری: بررسی تصویری منظره‌ی دریا و شومینه با مدل بینایی (ساخته نشده؛ برآورد حدود ۱ دلار).",
    en: "Optional: VLM checks for sea view and fireplace (not built; about $1 estimated).",
  },
];
