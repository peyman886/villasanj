import { BarList } from "@/components/charts/bars";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { latest } from "@/lib/artifacts";
import { faDecimal, faInt, faPercent } from "@/lib/format";

const SUITE_FA: [RegExp, string][] = [
  [/^backend: unit/, "بک‌اند: واحد و معماری"],
  [/^backend: integration/, "بک‌اند: یکپارچگی (Postgres واقعی)"],
  [/^frontend: unit/, "فرانت‌اند: واحد (Vitest)"],
  [/^E2E/, "E2E (Playwright و axe)"],
  [/^smoke/, "smoke (صفحه‌های نمونه)"],
];

function suiteName(name: string): string {
  return SUITE_FA.find(([p]) => p.test(name))?.[1] ?? name;
}

function MissingQuality() {
  return (
    <Callout kind="caution" title="گزارش کیفیت هنوز تولید نشده">
      <code className="ltr font-mono">make quality-report</code> همه‌ی مجموعه‌ها را اجرا می‌کند و
      نتیجه را در <code className="ltr font-mono">reports/quality-&lt;date&gt;.json</code> می‌نویسد.
    </Callout>
  );
}

/** Every test suite's last result, from the quality report (never retyped). */
export async function TestSuites() {
  const a = await latest("quality");
  if (!a) return <MissingQuality />;
  const total = a.data.suites.reduce((n, s) => n + s.passed, 0);
  const failed = a.data.suites.reduce((n, s) => n + s.failed, 0);
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} />;
  return (
    <div className="space-y-4">
      <MetricGrid className="lg:grid-cols-2">
        <MetricCard
          tone={failed ? "danger" : "verified"}
          label="تست‌های پاس‌شده"
          value={faInt(total)}
          detail={failed ? `${faInt(failed)} شکست` : "بدون شکست"}
          source={source}
        />
        <MetricCard
          tone={a.data.lint.ok ? "verified" : "danger"}
          label="make lint"
          value={a.data.lint.ok ? "پاک" : "شکست"}
          detail="ruff، mypy strict، import-linter، tsc، eslint، prettier"
          source={source}
        />
        {a.data.coverage.slice(0, 2).map((c) => (
          <MetricCard
            key={c.name}
            label={`پوشش ${c.name === "domain" ? "لایه‌ی دامنه" : c.name === "pricing domain" ? "دامنه‌ی قیمت" : "کل بک‌اند"}`}
            value={faPercent(c.percent / 100)}
            source={source}
          />
        ))}
      </MetricGrid>
      <DataTable caption="نتیجه‌ی مجموعه‌های تست" minWidth="34rem">
        <thead>
          <tr>
            <th scope="col">مجموعه</th>
            <th scope="col">پاس</th>
            <th scope="col">شکست</th>
            <th scope="col">ردشده</th>
            <th scope="col">زمان</th>
          </tr>
        </thead>
        <tbody>
          {a.data.suites.map((s) => (
            <tr key={s.name}>
              <th scope="row" className="font-medium">
                {suiteName(s.name)}
                <span className="ltr block text-xs font-normal text-fg-muted">{s.name}</span>
              </th>
              <td>{faInt(s.passed)}</td>
              <td>{s.failed ? <Badge tone="danger">{faInt(s.failed)}</Badge> : faInt(0)}</td>
              <td>{faInt(s.skipped)}</td>
              <td>{faDecimal(s.seconds)} ثانیه</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <BarList
        label="سهم هر مجموعه از تست‌ها"
        bars={a.data.suites.map((s) => ({
          label: suiteName(s.name),
          value: s.passed,
          display: faInt(s.passed),
        }))}
      />
      {source}
    </div>
  );
}

/** API latency on the paths that have a target. */
export async function PerformanceTable() {
  const a = await latest("performance");
  if (!a) {
    return (
      <Callout kind="caution" title="گزارش کارایی هنوز تولید نشده">
        <code className="ltr font-mono">make perf-report</code>
      </Callout>
    );
  }
  const NAME: Record<string, string> = {
    "villa + offers": "ویلا و پیشنهادهایش",
    "listing + offer": "آگهی و پیشنهادش",
    "search (cached understanding)": "جستجو با فهم کش‌شده",
  };
  return (
    <div className="space-y-2">
      <DataTable caption="تأخیر API" minWidth="34rem">
        <thead>
          <tr>
            <th scope="col">مسیر</th>
            <th scope="col">نمونه</th>
            <th scope="col">میانه</th>
            <th scope="col">p95</th>
            <th scope="col">بیشینه</th>
            <th scope="col">هدف</th>
          </tr>
        </thead>
        <tbody>
          {a.data.measurements.map((m) => (
            <tr key={m.name}>
              <th scope="row" className="font-medium">
                {NAME[m.name] ?? m.name}
              </th>
              <td>{faInt(m.samples)}</td>
              <td>{faDecimal(m.p50_ms)} ms</td>
              <td>{faDecimal(m.p95_ms)} ms</td>
              <td>{faDecimal(m.max_ms)} ms</td>
              <td>
                {m.target_ms === null ? (
                  "—"
                ) : m.p95_ms <= m.target_ms ? (
                  <Badge tone="verified">≤ {faInt(m.target_ms)} ms</Badge>
                ) : (
                  <Badge tone="danger">بالای {faInt(m.target_ms)} ms</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="text-sm text-fg-muted">
        روی <span className="ltr font-mono text-xs">{String(a.provenance.api ?? "")}</span>،{" "}
        {faInt(Number(a.provenance.sample ?? 0))} ویلای نمونه، سناریوی{" "}
        {String(a.provenance.scenario ?? "")} با {faInt(Number(a.provenance.guests ?? 0))} نفر.
      </p>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}
