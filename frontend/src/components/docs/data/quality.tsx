import { BarList } from "@/components/charts/bars";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { latest } from "@/lib/artifacts";
import { formatFor } from "@/lib/format";
import { t, type Locale } from "@/lib/i18n";

const SUITE: [RegExp, string, string][] = [
  [/^backend: unit/, "بک‌اند: واحد و معماری", "Backend: unit and architecture"],
  [
    /^backend: integration/,
    "بک‌اند: یکپارچگی (Postgres واقعی)",
    "Backend: integration (real Postgres)",
  ],
  [/^frontend: unit/, "فرانت‌اند: واحد (Vitest)", "Frontend: unit (Vitest)"],
  [/^E2E/, "E2E (Playwright و axe)", "E2E (Playwright and axe)"],
  [/^smoke/, "smoke (صفحه‌های نمونه)", "Smoke (sampled pages)"],
];

function suiteName(name: string, locale: Locale): string {
  const hit = SUITE.find(([p]) => p.test(name));
  return hit ? t(locale, hit[1], hit[2]) : name;
}

const COVERAGE: Record<string, { fa: string; en: string }> = {
  domain: { fa: "لایه‌ی دامنه", en: "the domain layer" },
  "pricing domain": { fa: "دامنه‌ی قیمت", en: "the pricing domain" },
};

function coverageLabel(name: string, locale: Locale): string {
  const what = COVERAGE[name] ?? { fa: "کل بک‌اند", en: "the whole backend" };
  return t(locale, `پوشش ${what.fa}`, `Coverage of ${what.en}`);
}

function MissingQuality({ locale }: { locale: Locale }) {
  return (
    <Callout
      kind="caution"
      title={t(
        locale,
        "گزارش کیفیت هنوز تولید نشده",
        "The quality report has not been generated yet",
      )}
    >
      {locale === "en" ? (
        <>
          <code className="ltr font-mono">make quality-report</code> runs every suite and writes the
          result to <code className="ltr font-mono">reports/quality-&lt;date&gt;.json</code>.
        </>
      ) : (
        <>
          <code className="ltr font-mono">make quality-report</code> همه‌ی مجموعه‌ها را اجرا می‌کند
          و نتیجه را در <code className="ltr font-mono">reports/quality-&lt;date&gt;.json</code>{" "}
          می‌نویسد.
        </>
      )}
    </Callout>
  );
}

/** Every test suite's last result, from the quality report (never retyped). */
export async function TestSuites({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("quality");
  if (!a) return <MissingQuality locale={locale} />;
  const f = formatFor(locale);
  const total = a.data.suites.reduce((n, s) => n + s.passed, 0);
  const failed = a.data.suites.reduce((n, s) => n + s.failed, 0);
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />;
  return (
    <div className="space-y-4">
      <MetricGrid className="lg:grid-cols-2">
        <MetricCard
          tone={failed ? "danger" : "verified"}
          label={t(locale, "تست‌های پاس‌شده", "Tests passed")}
          value={f.int(total)}
          detail={
            failed
              ? `${f.int(failed)} ${t(locale, "شکست", "failed")}`
              : t(locale, "بدون شکست", "No failures")
          }
          source={source}
        />
        <MetricCard
          tone={a.data.lint.ok ? "verified" : "danger"}
          label="make lint"
          value={a.data.lint.ok ? t(locale, "پاک", "Clean") : t(locale, "شکست", "Failed")}
          detail={t(
            locale,
            "ruff، mypy strict، import-linter، tsc، eslint، prettier",
            "ruff, mypy strict, import-linter, tsc, eslint, prettier",
          )}
          source={source}
        />
        {a.data.coverage.slice(0, 2).map((c) => (
          <MetricCard
            key={c.name}
            label={coverageLabel(c.name, locale)}
            value={f.percent(c.percent / 100)}
            source={source}
          />
        ))}
      </MetricGrid>
      <DataTable
        caption={t(locale, "نتیجه‌ی مجموعه‌های تست", "Test suite results")}
        minWidth="34rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "مجموعه", "Suite")}</th>
            <th scope="col">{t(locale, "پاس", "Passed")}</th>
            <th scope="col">{t(locale, "شکست", "Failed")}</th>
            <th scope="col">{t(locale, "ردشده", "Skipped")}</th>
            <th scope="col">{t(locale, "زمان", "Time")}</th>
          </tr>
        </thead>
        <tbody>
          {a.data.suites.map((s) => (
            <tr key={s.name}>
              <th scope="row" className="font-medium">
                {suiteName(s.name, locale)}
                <span className="ltr block text-xs font-normal text-fg-muted">{s.name}</span>
              </th>
              <td>{f.int(s.passed)}</td>
              <td>{s.failed ? <Badge tone="danger">{f.int(s.failed)}</Badge> : f.int(0)}</td>
              <td>{f.int(s.skipped)}</td>
              <td>
                {f.decimal(s.seconds)} {t(locale, "ثانیه", "s")}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <BarList
        label={t(locale, "سهم هر مجموعه از تست‌ها", "Each suite's share of the tests")}
        bars={a.data.suites.map((s) => ({
          label: suiteName(s.name, locale),
          value: s.passed,
          display: f.int(s.passed),
        }))}
      />
      {source}
    </div>
  );
}

const PATH_NAME: Record<string, { fa: string; en: string }> = {
  "villa + offers": { fa: "ویلا و پیشنهادهایش", en: "Villa and its offers" },
  "listing + offer": { fa: "آگهی و پیشنهادش", en: "Listing and its offer" },
  "search (cached understanding)": {
    fa: "جستجو با فهم کش‌شده",
    en: "Search with cached understanding",
  },
};

/** API latency on the paths that have a target. */
export async function PerformanceTable({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("performance");
  if (!a) {
    return (
      <Callout
        kind="caution"
        title={t(
          locale,
          "گزارش کارایی هنوز تولید نشده",
          "The performance report has not been generated yet",
        )}
      >
        <code className="ltr font-mono">make perf-report</code>
      </Callout>
    );
  }
  const f = formatFor(locale);
  const pathName = (name: string) => {
    const hit = PATH_NAME[name];
    return hit ? t(locale, hit.fa, hit.en) : name;
  };
  const api = <span className="ltr font-mono text-xs">{String(a.provenance.api ?? "")}</span>;
  const sample = f.int(Number(a.provenance.sample ?? 0));
  const scenario = String(a.provenance.scenario ?? "");
  const guests = f.int(Number(a.provenance.guests ?? 0));
  return (
    <div className="space-y-2">
      <DataTable caption={t(locale, "تأخیر API", "API latency")} minWidth="34rem">
        <thead>
          <tr>
            <th scope="col">{t(locale, "مسیر", "Path")}</th>
            <th scope="col">{t(locale, "نمونه", "Samples")}</th>
            <th scope="col">{t(locale, "میانه", "Median")}</th>
            <th scope="col">p95</th>
            <th scope="col">{t(locale, "بیشینه", "Max")}</th>
            <th scope="col">{t(locale, "هدف", "Target")}</th>
          </tr>
        </thead>
        <tbody>
          {a.data.measurements.map((m) => (
            <tr key={m.name}>
              <th scope="row" className="font-medium">
                {pathName(m.name)}
              </th>
              <td>{f.int(m.samples)}</td>
              <td>{f.decimal(m.p50_ms)} ms</td>
              <td>{f.decimal(m.p95_ms)} ms</td>
              <td>{f.decimal(m.max_ms)} ms</td>
              <td>
                {m.target_ms === null ? (
                  "-"
                ) : m.p95_ms <= m.target_ms ? (
                  <Badge tone="verified">≤ {f.int(m.target_ms)} ms</Badge>
                ) : (
                  <Badge tone="danger">
                    {t(locale, "بالای", "Above")} {f.int(m.target_ms)} ms
                  </Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="text-sm text-fg-muted">
        {locale === "en" ? (
          <>
            Measured on {api} with {sample} sampled villas, the {scenario} scenario, {guests}{" "}
            guests.
          </>
        ) : (
          <>
            روی {api}، {sample} ویلای نمونه، سناریوی {scenario} با {guests} نفر.
          </>
        )}
      </p>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}
