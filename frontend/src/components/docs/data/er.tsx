import { ChevronDown } from "lucide-react";

import { BarList } from "@/components/charts/bars";
import { IntervalChart } from "@/components/charts/interval";
import { LineChart } from "@/components/charts/line";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { allOf, latest, type Artifact, type ErEval, type PolicyResult } from "@/lib/artifacts";
import { faDecimal, faInt, faInterval, faPercent, faRange } from "@/lib/format";

const POLICY_FA: Record<string, string> = {
  "rules alone": "فقط قواعد",
  "rules alone at the gold-set threshold": "فقط قواعد در آستانه‌ی برگزیده‌ی gold",
  "advisory judge": "داور مشورتی",
  "judge vetoes, a human merges": "داور رد می‌کند، انسان ادغام می‌کند",
  "judge merges and vetoes": "داور ادغام و رد می‌کند",
  "judge merges, no vetoes": "داور فقط ادغام می‌کند",
};

const STRATUM_FA: Record<string, string> = {
  same_platform: "هم‌پلتفرم",
  wide: "تور گسترده",
};

export function policyName(name: string): string {
  return POLICY_FA[name] ?? name;
}

function Missing({ what }: { what: string }) {
  return (
    <Callout kind="caution" title="گزارش پیدا نشد">
      {what} هنوز تولید نشده است؛ <code className="ltr font-mono">uv run villasanj er report</code>{" "}
      را اجرا کنید.
    </Callout>
  );
}

async function er(): Promise<Artifact<"er-eval"> | null> {
  return latest("er-eval");
}

function configured(data: ErEval): PolicyResult | undefined {
  return data.revised.policies.find((p) => p.configured);
}

/** The headline numbers of entity resolution. */
export async function ErHeadline() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const now = configured(a.data);
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} />;
  return (
    <MetricGrid className="lg:grid-cols-2">
      <MetricCard
        tone="verified"
        label="دقت سیاست فعلی"
        value={faPercent(now?.metrics.precision.estimate)}
        detail={`بازه‌ی ۹۵٪: ${faInterval(now?.metrics.precision).split("(")[1]?.replace(")", "") ?? "-"}`}
        source={source}
      />
      <MetricCard
        label="بازیابی سیاست فعلی"
        value={faPercent(now?.metrics.recall.estimate)}
        detail={`بازه‌ی ۹۵٪: ${faInterval(now?.metrics.recall).split("(")[1]?.replace(")", "") ?? "-"}`}
        source={source}
      />
      <MetricCard
        label="برچسب‌های مالک"
        value={faInt(a.data.revised.labelled)}
        detail={`نامطمئن ${faPercent(a.data.revised.unsure.estimate)} · ${faInt(a.data.revisions.length)} برچسب اصلاح‌شده`}
        source={source}
      />
      <MetricCard
        tone="verified"
        label="ویلاهای دوپلتفرمی"
        value={faInt(a.data.villas_now.multi_platform)}
        detail={`از ${faInt(a.data.villas_now.villas)} ویلای یکتا و ${faInt(a.data.villas_now.listings)} آگهی`}
        source={source}
      />
    </MetricGrid>
  );
}

/** Candidates, villas and who merged them: the size of the problem and of the answer. */
export async function ErCounts() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const v = a.data.villas_now;
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} />;
  const DECIDER: Record<string, string> = { human: "برچسب مالک", rule: "قواعد", judge: "داور" };
  return (
    <div className="space-y-4">
      <MetricGrid className="lg:grid-cols-2">
        <MetricCard
          label="جفت‌های نامزد"
          value={faInt(a.data.candidates?.total)}
          detail={`${faInt(a.data.candidates?.blocked)} از blocking تولید؛ بقیه تور گسترده برای سنجیدن آن`}
          source={source}
        />
        <MetricCard
          tone="verified"
          label="recall مرحله‌ی blocking"
          value={faPercent(a.data.revised.blocking_recall.estimate)}
          detail={`بازه‌ی ۹۵٪: ${faRange(a.data.revised.blocking_recall)}`}
          source={source}
        />
        <MetricCard
          label="آگهی ← ویلا"
          value={`${faInt(v.listings)} ← ${faInt(v.villas)}`}
          detail={`${faInt(v.multi_platform)} ویلا روی هر دو پلتفرم`}
          source={source}
        />
        <MetricCard
          tone="caution"
          label="ادغام‌های ردشده"
          value={faInt(Object.values(v.refused).reduce((x, y) => x + y, 0))}
          detail="دو آگهی از یک پلتفرم در یک ویلا (قاعده‌ی ۴ محصول)"
          source={source}
        />
      </MetricGrid>
      <BarList
        label="ادغام‌ها به تفکیک تصمیم‌گیرنده"
        bars={Object.entries(v.applied).map(([k, n]) => ({
          label: DECIDER[k] ?? k,
          value: n,
          display: faInt(n),
        }))}
      />
    </div>
  );
}

/** Before and after the owner's label revision, every number computed from the same data. */
export async function ErWhatChanged() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const after = configured(a.data);
  const before = a.data.original.policies.find((p) => p.name === "advisory judge");
  const rows: [string, string, string][] = [
    ["سیاست", a.provenance.previous_policy as string, a.provenance.policy as string],
    ["دقت", faInterval(before?.metrics.precision), faInterval(after?.metrics.precision)],
    ["بازیابی", faInterval(before?.metrics.recall), faInterval(after?.metrics.recall)],
    [
      "آستانه‌ای که gold برای «فقط قواعد» برمی‌گزیند",
      faDecimal(a.data.original.gold_threshold?.threshold),
      faDecimal(a.data.revised.gold_threshold?.threshold),
    ],
    [
      "دقت «فقط قواعد» در ۰٫۲۵−",
      faInterval(a.data.original.policies.find((p) => p.name === "rules alone")?.metrics.precision),
      faInterval(a.data.revised.policies.find((p) => p.name === "rules alone")?.metrics.precision),
    ],
    [
      "نرخ «نامطمئن»",
      faPercent(a.data.original.unsure.estimate),
      faPercent(a.data.revised.unsure.estimate),
    ],
    [
      "ویلاها (دوپلتفرمی)",
      `${faInt(a.data.villas_before.villas)} (${faInt(a.data.villas_before.multi_platform)})`,
      `${faInt(a.data.villas_now.villas)} (${faInt(a.data.villas_now.multi_platform)})`,
    ],
  ];
  return (
    <div className="space-y-2">
      <DataTable caption="اثر اصلاح برچسب‌ها" minWidth="34rem">
        <thead>
          <tr>
            <th scope="col" />
            <th scope="col">پیش از اصلاح (برچسب‌های اولیه، سیاست ۱۱ مهر)</th>
            <th scope="col">پس از اصلاح (برچسب‌های اصلاح‌شده، سیاست فعلی)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, b, c]) => (
            <tr key={label}>
              <th scope="row" className="font-medium">
                {label}
              </th>
              <td className={label === "سیاست" ? "ltr text-xs" : undefined}>{b}</td>
              <td className={label === "سیاست" ? "ltr text-xs" : "font-medium"}>{c}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

/** Every policy end to end on the revised labels (or the originals, for history). */
export async function ErPolicies({ labels = "revised" }: { labels?: "revised" | "original" }) {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const policies = a.data[labels].policies;
  return (
    <div className="space-y-4">
      <IntervalChart
        label="دقت هر سیاست با بازه‌ی ۹۵٪"
        min={0.5}
        bar={0.92}
        barLabel="خط‌چین: کران پایین لازم برای دقت (۹۲٪)"
        rows={policies.map((p) => ({
          label: policyName(p.name),
          interval: p.metrics.precision,
          highlight: p.configured,
        }))}
      />
      <DataTable caption="سیاست‌های تصمیم، سرتاسری" minWidth="46rem">
        <thead>
          <tr>
            <th scope="col">سیاست</th>
            <th scope="col">دقت</th>
            <th scope="col">بازیابی</th>
            <th scope="col">F1</th>
            <th scope="col">TP/FP/FN</th>
            <th scope="col">منتظر انسان</th>
            <th scope="col">B-cubed F1</th>
            <th scope="col">معیار</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.name} className={p.configured ? "bg-brand-50/60" : undefined}>
              <th scope="row" className="font-medium">
                {policyName(p.name)}
                {p.configured ? (
                  <Badge tone="brand" className="ms-2">
                    در حال اجرا
                  </Badge>
                ) : null}
                <span className="ltr mt-0.5 block text-xs font-normal text-fg-muted">{p.rule}</span>
              </th>
              <td>{faInterval(p.metrics.precision)}</td>
              <td>{faInterval(p.metrics.recall)}</td>
              <td>{faDecimal(p.metrics.f1, 3)}</td>
              <td>
                {faInt(p.metrics.tp)}/{faInt(p.metrics.fp)}/{faInt(p.metrics.fn)}
              </td>
              <td>{faInt(p.waiting)}</td>
              <td>{faDecimal(p.bcubed?.f1, 3)}</td>
              <td>
                {p.meets_bar ? (
                  <Badge tone="verified">پاس</Badge>
                ) : (
                  <Badge tone="danger">پاس نشد</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function ErCurve() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const curve = a.data.revised.curve;
  const gold = a.data.revised.gold_threshold;
  return (
    <div className="space-y-2">
      <LineChart
        label="دقت و بازیابی امتیاز قاعده‌ای در برابر آستانه"
        xLabel="آستانه‌ی امتیاز قاعده‌ای"
        formatX={(x) => String(x)}
        series={[
          {
            label: "دقت (وزن‌دار)",
            tone: "brand",
            points: curve.map((c) => ({
              x: c.threshold,
              y: c.precision.estimate,
              low: c.precision.low,
              high: c.precision.high,
            })),
          },
          {
            label: "بازیابی (وزن‌دار)",
            tone: "amber",
            points: curve.map((c) => ({
              x: c.threshold,
              y: c.recall.estimate,
              low: c.recall.low,
              high: c.recall.high,
            })),
          },
        ]}
        {...(gold ? { marker: { x: gold.threshold, label: `gold: ${gold.threshold}` } } : {})}
      />
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function ErStrata() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const strata = Object.entries(a.data.revised.labels_by_stratum);
  return (
    <div className="space-y-2">
      <DataTable caption="برچسب‌ها در هر لایه‌ی نمونه‌گیری" minWidth="28rem">
        <thead>
          <tr>
            <th scope="col">لایه</th>
            <th scope="col">یکی است</th>
            <th scope="col">یکی نیست</th>
            <th scope="col">نامطمئن</th>
          </tr>
        </thead>
        <tbody>
          {strata.map(([stratum, counts]) => (
            <tr key={stratum}>
              <th scope="row" className="font-normal">
                <span className="ltr font-mono text-xs">{STRATUM_FA[stratum] ?? stratum}</span>
              </th>
              <td>{faInt(counts.match ?? 0)}</td>
              <td>{faInt(counts.non_match ?? 0)}</td>
              <td>{faInt(counts.unsure ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function ErRevisions() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const revisions = a.data.revisions;
  const groups = new Map<string, number>();
  for (const r of revisions) {
    const key = `${r.kind.split(" (")[0]}|${r.before}|${r.after}`;
    groups.set(key, (groups.get(key) ?? 0) + 1);
  }
  const LABEL: Record<string, string> = {
    match: "یکی است",
    non_match: "یکی نیست",
    unsure: "نامطمئن",
  };
  return (
    <div className="space-y-3">
      <DataTable caption="خلاصه‌ی اصلاح برچسب‌ها" minWidth="26rem">
        <thead>
          <tr>
            <th scope="col">جفت‌ها</th>
            <th scope="col">از</th>
            <th scope="col">به</th>
            <th scope="col">تعداد</th>
          </tr>
        </thead>
        <tbody>
          {[...groups.entries()].map(([key, count]) => {
            const [side, before, after] = key.split("|");
            return (
              <tr key={key}>
                <td>{side === "same platform" ? "هم‌پلتفرم" : "بین‌پلتفرمی"}</td>
                <td>{LABEL[before ?? ""] ?? before}</td>
                <td>{LABEL[after ?? ""] ?? after}</td>
                <td>{faInt(count)}</td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <details className="group rounded-card border border-line bg-surface">
        <summary className="focus-ring flex cursor-pointer list-none items-center justify-between rounded-card p-4 text-sm font-medium [&::-webkit-details-marker]:hidden">
          همه‌ی {faInt(revisions.length)} اصلاح، هر کدام با دلیلش
          <ChevronDown
            aria-hidden="true"
            className="size-4 transition-transform group-open:rotate-180"
          />
        </summary>
        <ul className="divide-y divide-line border-t border-line text-sm">
          {revisions.map((r) => (
            <li key={r.pair} className="p-3">
              <p className="flex flex-wrap items-center gap-2">
                <span className="ltr font-mono text-xs text-fg-muted">{r.pair}</span>
                <Badge tone="muted">
                  {LABEL[r.before]} ← {LABEL[r.after]}
                </Badge>
              </p>
              <p className="ltr mt-1 text-xs text-pretty text-fg-muted">{r.reason}</p>
            </li>
          ))}
        </ul>
      </details>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function ErAblations() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const NAME: Record<string, string> = {
    photos: "فقط عکس",
    "other evidence": "فقط شواهد دیگر",
    full: "امتیاز کامل",
  };
  return (
    <div className="space-y-2">
      <DataTable caption="ablation: هر بخش شواهد به‌تنهایی" minWidth="34rem">
        <thead>
          <tr>
            <th scope="col">شواهد</th>
            <th scope="col">در معیار دقت</th>
            <th scope="col">بهترین F1</th>
          </tr>
        </thead>
        <tbody>
          {a.data.ablations.map((x) => (
            <tr key={x.name}>
              <th scope="row" className="font-medium">
                {NAME[x.name] ?? x.name}
              </th>
              <td>
                {x.at_bar
                  ? `آستانه‌ی ${faDecimal(x.at_bar.threshold)}: دقت ${faInterval(x.at_bar.precision)}، بازیابی ${faInterval(x.at_bar.recall)}`
                  : "هیچ آستانه‌ای به آن نمی‌رسد"}
              </td>
              <td>
                {x.best_f1
                  ? `${faDecimal(x.best_f1.f1, 3)} (دقت ${faPercent(x.best_f1.precision.estimate)}، بازیابی ${faPercent(x.best_f1.recall.estimate)})`
                  : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function JudgeVerdicts() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const VERDICT: Record<string, string> = {
    match: "یکی است",
    non_match: "یکی نیست",
    unsure: "نامطمئن",
  };
  const queue = Object.entries(a.data.human_queue);
  return (
    <div className="space-y-3">
      <DataTable caption="رأی‌های داور روی نامزدهای تولید" minWidth="28rem">
        <thead>
          <tr>
            <th scope="col">بازه‌ی امتیاز</th>
            <th scope="col">رأی</th>
            <th scope="col">مطمئن</th>
            <th scope="col">جفت</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(a.data.judge_verdicts).map(([key, count]) => {
            const [band, verdict, sure] = key.split(":");
            return (
              <tr key={key}>
                <td>{band === "above" ? "بالای آستانه" : "زیر آستانه"}</td>
                <td>{VERDICT[verdict ?? ""] ?? verdict}</td>
                <td>{sure === "confident" ? "بله" : "نه"}</td>
                <td>{faInt(count)}</td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <p className="text-sm text-fg-muted">
        صف انسانی <span className="ltr font-mono">er-human</span>:{" "}
        {queue.map(([k, v]) => `${k.replace("judge:", "")} ${faInt(v)}`).join("، ")}
      </p>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

/** The judge bake-off, re-scored from the cache on the revised labels. */
export async function JudgeBakeoff() {
  const runs = await allOf("judge-eval");
  const latestByModel = new Map<string, Artifact<"judge-eval">>();
  for (const run of runs) {
    const model = String(run.provenance.model);
    if (!latestByModel.has(model)) latestByModel.set(model, run);
  }
  if (latestByModel.size === 0) return <Missing what="ارزیابی داور" />;
  return (
    <div className="space-y-2">
      <DataTable caption="مقایسه‌ی مدل‌های داور" minWidth="38rem">
        <thead>
          <tr>
            <th scope="col">مدل</th>
            <th scope="col">ادغام نادرست</th>
            <th scope="col">دقت «یکی است» (≥ ۰٫۸)</th>
            <th scope="col">بازیابی (≥ ۰٫۸)</th>
            <th scope="col">نامطمئن</th>
            <th scope="col">منبع</th>
          </tr>
        </thead>
        <tbody>
          {[...latestByModel.entries()].map(([model, run]) => {
            const at = run.data.by_confidence["0.8"];
            return (
              <tr key={model}>
                <th scope="row" className="font-medium">
                  <span className="ltr font-mono text-xs">{model}</span>
                  {model === "gemini-3.8-flash" ? (
                    <Badge tone="brand" className="ms-2">
                      برگزیده
                    </Badge>
                  ) : null}
                </th>
                <td className={run.data.false_matches > 0 ? "text-rose-700" : undefined}>
                  {faInt(run.data.false_matches)}
                </td>
                <td>{faInterval(at?.precision)}</td>
                <td>{faInterval(at?.recall)}</td>
                <td>{faPercent(run.data.unsure_rate)}</td>
                <td>
                  <SourceChip file={run.file} generatedAt={run.generated_at} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
    </div>
  );
}

/** The owner's labels on the queue the judge ordered: how its suggestions and vetoes held up. */
export async function ErHumanQueue() {
  const a = await er();
  if (!a) return <Missing what="ارزیابی تطبیق" />;
  const labels = a.data.human_queue_labels;
  const judged = a.data.judge_on_human_queue;
  if (!labels || !judged) {
    return <Callout kind="info" title="هنوز برچسبی روی صف انسانی نیست" />;
  }
  const REASON: Record<string, string> = {
    "judge:suggested": "داور گفت یکی است (زیر آستانه)",
    "judge:disputed": "داور ادغام قواعد را رد کرد",
    "judge:unsure": "داور مطمئن نبود",
  };
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} />;
  return (
    <div className="space-y-4">
      <MetricGrid className="lg:grid-cols-2">
        <MetricCard
          tone="verified"
          label="پیشنهادهای «یکی است» داور که مالک تأیید کرد"
          value={faPercent(judged.suggested_match_precision?.estimate)}
          detail={`بازه‌ی ۹۵٪: ${faRange(judged.suggested_match_precision)}`}
          source={source}
        />
        <MetricCard
          tone="verified"
          label="ردهای داور که مالک تأیید کرد"
          value={faPercent(judged.veto_precision?.estimate)}
          detail={`بازه‌ی ۹۵٪: ${faRange(judged.veto_precision)}`}
          source={source}
        />
      </MetricGrid>
      <DataTable caption="برچسب‌های مالک روی صف er-human" minWidth="30rem">
        <thead>
          <tr>
            <th scope="col">چرا در صف آمد</th>
            <th scope="col">یکی است</th>
            <th scope="col">یکی نیست</th>
            <th scope="col">نامطمئن</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(labels).map(([reason, c]) => (
            <tr key={reason}>
              <th scope="row" className="font-medium">
                {REASON[reason] ?? reason}
              </th>
              <td>{faInt(c.match ?? 0)}</td>
              <td>{faInt(c.non_match ?? 0)}</td>
              <td>{faInt(c.unsure ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {source}
    </div>
  );
}
