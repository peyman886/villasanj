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
import { formatFor } from "@/lib/format";
import { t, type Locale } from "@/lib/i18n";

const POLICY_FA: Record<string, string> = {
  "rules alone": "فقط قواعد",
  "rules alone at the gold-set threshold": "فقط قواعد در آستانه‌ی برگزیده‌ی gold",
  "advisory judge": "داور مشورتی",
  "judge vetoes, a human merges": "داور رد می‌کند، انسان ادغام می‌کند",
  "judge merges and vetoes": "داور ادغام و رد می‌کند",
  "judge merges, no vetoes": "داور فقط ادغام می‌کند",
};

const STRATUM: Record<string, [string, string]> = {
  same_platform: ["هم‌پلتفرم", "same platform"],
  wide: ["تور گسترده", "wide net"],
};

const LABEL: Record<string, [string, string]> = {
  match: ["یکی است", "match"],
  non_match: ["یکی نیست", "non-match"],
  unsure: ["نامطمئن", "unsure"],
};

/** The name for a key in a [Persian, English] table, or the key itself. */
function pick(table: Record<string, [string, string]>, key: string, locale: Locale): string {
  const pair = table[key];
  return pair ? t(locale, pair[0], pair[1]) : key;
}

function labelName(label: string | undefined, locale: Locale): string {
  return pick(LABEL, label ?? "", locale);
}

/** A policy's display name: Persian from the table, English as the report names it. */
export function policyName(name: string, locale: Locale = "fa"): string {
  return locale === "en" ? name : (POLICY_FA[name] ?? name);
}

/** The interval part of "98.1% (93.0 to 99.5%)": "93.0 to 99.5%". */
function intervalOnly(f: ReturnType<typeof formatFor>, i: Parameters<typeof f.interval>[0]) {
  return f.interval(i).split("(")[1]?.replace(")", "") ?? "-";
}

function Missing({ what, locale }: { what: string; locale: Locale }) {
  return locale === "en" ? (
    <Callout kind="caution" title="Report not found">
      The {what} has not been generated yet; run{" "}
      <code className="ltr font-mono">uv run villasanj er report</code>.
    </Callout>
  ) : (
    <Callout kind="caution" title="گزارش پیدا نشد">
      {what} هنوز تولید نشده است؛ <code className="ltr font-mono">uv run villasanj er report</code>{" "}
      را اجرا کنید.
    </Callout>
  );
}

function missingEr(locale: Locale) {
  return (
    <Missing what={t(locale, "ارزیابی تطبیق", "entity resolution evaluation")} locale={locale} />
  );
}

async function er(): Promise<Artifact<"er-eval"> | null> {
  return latest("er-eval");
}

function configured(data: ErEval): PolicyResult | undefined {
  return data.revised.policies.find((p) => p.configured);
}

/** The headline numbers of entity resolution. */
export async function ErHeadline({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const now = configured(a.data);
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />;
  return (
    <MetricGrid className="lg:grid-cols-2">
      <MetricCard
        tone="verified"
        label={t(locale, "دقت سیاست فعلی", "Precision of the current policy")}
        value={f.percent(now?.metrics.precision.estimate)}
        detail={`${t(locale, "بازه‌ی ۹۵٪", "95% CI")}: ${intervalOnly(f, now?.metrics.precision)}`}
        source={source}
      />
      <MetricCard
        label={t(locale, "بازیابی سیاست فعلی", "Recall of the current policy")}
        value={f.percent(now?.metrics.recall.estimate)}
        detail={`${t(locale, "بازه‌ی ۹۵٪", "95% CI")}: ${intervalOnly(f, now?.metrics.recall)}`}
        source={source}
      />
      <MetricCard
        label={t(locale, "برچسب‌های مالک", "The owner's labels")}
        value={f.int(a.data.revised.labelled)}
        detail={t(
          locale,
          `نامطمئن ${f.percent(a.data.revised.unsure.estimate)} · ${f.int(a.data.revisions.length)} برچسب اصلاح‌شده`,
          `${f.percent(a.data.revised.unsure.estimate)} unsure · ${f.int(a.data.revisions.length)} labels revised`,
        )}
        source={source}
      />
      <MetricCard
        tone="verified"
        label={t(locale, "ویلاهای دوپلتفرمی", "Villas on both platforms")}
        value={f.int(a.data.villas_now.multi_platform)}
        detail={t(
          locale,
          `از ${f.int(a.data.villas_now.villas)} ویلای یکتا و ${f.int(a.data.villas_now.listings)} آگهی`,
          `of ${f.int(a.data.villas_now.villas)} distinct villas and ${f.int(a.data.villas_now.listings)} listings`,
        )}
        source={source}
      />
    </MetricGrid>
  );
}

/** Candidates, villas and who merged them: the size of the problem and of the answer. */
export async function ErCounts({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const v = a.data.villas_now;
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />;
  const DECIDER: Record<string, [string, string]> = {
    human: ["برچسب مالک", "owner's label"],
    rule: ["قواعد", "rules"],
    judge: ["داور", "judge"],
  };
  return (
    <div className="space-y-4">
      <MetricGrid className="lg:grid-cols-2">
        <MetricCard
          label={t(locale, "جفت‌های نامزد", "Candidate pairs")}
          value={f.int(a.data.candidates?.total)}
          detail={t(
            locale,
            `${f.int(a.data.candidates?.blocked)} از blocking تولید؛ بقیه تور گسترده برای سنجیدن آن`,
            `${f.int(a.data.candidates?.blocked)} from production blocking; the rest is the wide net that measures it`,
          )}
          source={source}
        />
        <MetricCard
          tone="verified"
          label={t(locale, "recall مرحله‌ی blocking", "Blocking recall")}
          value={f.percent(a.data.revised.blocking_recall.estimate)}
          detail={`${t(locale, "بازه‌ی ۹۵٪", "95% CI")}: ${f.range(a.data.revised.blocking_recall)}`}
          source={source}
        />
        <MetricCard
          label={t(locale, "آگهی ← ویلا", "Listings → villas")}
          value={`${f.int(v.listings)} ${t(locale, "←", "→")} ${f.int(v.villas)}`}
          detail={t(
            locale,
            `${f.int(v.multi_platform)} ویلا روی هر دو پلتفرم`,
            `${f.int(v.multi_platform)} villas on both platforms`,
          )}
          source={source}
        />
        <MetricCard
          tone="caution"
          label={t(locale, "ادغام‌های ردشده", "Merges refused")}
          value={f.int(Object.values(v.refused).reduce((x, y) => x + y, 0))}
          detail={t(
            locale,
            "دو آگهی از یک پلتفرم در یک ویلا (قاعده‌ی ۴ محصول)",
            "two listings from one platform in one villa (product rule 4)",
          )}
          source={source}
        />
      </MetricGrid>
      <BarList
        label={t(locale, "ادغام‌ها به تفکیک تصمیم‌گیرنده", "Merges by decider")}
        bars={Object.entries(v.applied).map(([k, n]) => ({
          label: pick(DECIDER, k, locale),
          value: n,
          display: f.int(n),
        }))}
      />
    </div>
  );
}

/** Before and after the owner's label revision, every number computed from the same data. */
export async function ErWhatChanged({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const after = configured(a.data);
  const before = a.data.original.policies.find((p) => p.name === "advisory judge");
  const rows: [string, string, string][] = [
    [
      t(locale, "سیاست", "Policy"),
      a.provenance.previous_policy as string,
      a.provenance.policy as string,
    ],
    [
      t(locale, "دقت", "Precision"),
      f.interval(before?.metrics.precision),
      f.interval(after?.metrics.precision),
    ],
    [
      t(locale, "بازیابی", "Recall"),
      f.interval(before?.metrics.recall),
      f.interval(after?.metrics.recall),
    ],
    [
      t(
        locale,
        "آستانه‌ای که gold برای «فقط قواعد» برمی‌گزیند",
        'Threshold the gold set picks for "rules alone"',
      ),
      f.decimal(a.data.original.gold_threshold?.threshold),
      f.decimal(a.data.revised.gold_threshold?.threshold),
    ],
    [
      t(locale, "دقت «فقط قواعد» در ۰٫۲۵−", 'Precision of "rules alone" at −0.25'),
      f.interval(a.data.original.policies.find((p) => p.name === "rules alone")?.metrics.precision),
      f.interval(a.data.revised.policies.find((p) => p.name === "rules alone")?.metrics.precision),
    ],
    [
      t(locale, "نرخ «نامطمئن»", '"Unsure" rate'),
      f.percent(a.data.original.unsure.estimate),
      f.percent(a.data.revised.unsure.estimate),
    ],
    [
      t(locale, "ویلاها (دوپلتفرمی)", "Villas (on both platforms)"),
      `${f.int(a.data.villas_before.villas)} (${f.int(a.data.villas_before.multi_platform)})`,
      `${f.int(a.data.villas_now.villas)} (${f.int(a.data.villas_now.multi_platform)})`,
    ],
  ];
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(locale, "اثر اصلاح برچسب‌ها", "Effect of the label revision")}
        minWidth="34rem"
      >
        <thead>
          <tr>
            <th scope="col" />
            <th scope="col">
              {t(
                locale,
                "پیش از اصلاح (برچسب‌های اولیه، سیاست ۱۱ مهر)",
                "Before the revision (original labels, policy of 3 Oct)",
              )}
            </th>
            <th scope="col">
              {t(
                locale,
                "پس از اصلاح (برچسب‌های اصلاح‌شده، سیاست فعلی)",
                "After the revision (revised labels, current policy)",
              )}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, b, c], i) => (
            <tr key={label}>
              <th scope="row" className="font-medium">
                {label}
              </th>
              <td className={i === 0 ? "ltr text-xs" : undefined}>{b}</td>
              <td className={i === 0 ? "ltr text-xs" : "font-medium"}>{c}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

/** Every policy end to end on the revised labels (or the originals, for history). */
export async function ErPolicies({
  labels = "revised",
  locale = "fa",
}: {
  labels?: "revised" | "original";
  locale?: Locale;
}) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const policies = a.data[labels].policies;
  return (
    <div className="space-y-4">
      <IntervalChart
        label={t(locale, "دقت هر سیاست با بازه‌ی ۹۵٪", "Precision of each policy with its 95% CI")}
        min={0.5}
        bar={0.92}
        barLabel={t(
          locale,
          "خط‌چین: کران پایین لازم برای دقت (۹۲٪)",
          "Dashed line: the required lower bound for precision (92%)",
        )}
        locale={locale}
        rows={policies.map((p) => ({
          label: policyName(p.name, locale),
          interval: p.metrics.precision,
          highlight: p.configured,
        }))}
      />
      <DataTable
        caption={t(locale, "سیاست‌های تصمیم، سرتاسری", "Decision policies, end to end")}
        minWidth="46rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "سیاست", "Policy")}</th>
            <th scope="col">{t(locale, "دقت", "Precision")}</th>
            <th scope="col">{t(locale, "بازیابی", "Recall")}</th>
            <th scope="col">F1</th>
            <th scope="col">TP/FP/FN</th>
            <th scope="col">{t(locale, "منتظر انسان", "Waiting for a human")}</th>
            <th scope="col">B-cubed F1</th>
            <th scope="col">{t(locale, "معیار", "Bar")}</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.name} className={p.configured ? "bg-brand-50/60" : undefined}>
              <th scope="row" className="font-medium">
                {policyName(p.name, locale)}
                {p.configured ? (
                  <Badge tone="brand" className="ms-2">
                    {t(locale, "در حال اجرا", "running")}
                  </Badge>
                ) : null}
                <span className="ltr mt-0.5 block text-xs font-normal text-fg-muted">{p.rule}</span>
              </th>
              <td>{f.interval(p.metrics.precision)}</td>
              <td>{f.interval(p.metrics.recall)}</td>
              <td>{f.decimal(p.metrics.f1, 3)}</td>
              <td>
                {f.int(p.metrics.tp)}/{f.int(p.metrics.fp)}/{f.int(p.metrics.fn)}
              </td>
              <td>{f.int(p.waiting)}</td>
              <td>{f.decimal(p.bcubed?.f1, 3)}</td>
              <td>
                {p.meets_bar ? (
                  <Badge tone="verified">{t(locale, "پاس", "passes")}</Badge>
                ) : (
                  <Badge tone="danger">{t(locale, "پاس نشد", "fails")}</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function ErCurve({ locale = "fa" }: { locale?: Locale }) {
  const a = await er();
  if (!a) return missingEr(locale);
  const curve = a.data.revised.curve;
  const gold = a.data.revised.gold_threshold;
  return (
    <div className="space-y-2">
      <LineChart
        label={t(
          locale,
          "دقت و بازیابی امتیاز قاعده‌ای در برابر آستانه",
          "Precision and recall of the rule score against the threshold",
        )}
        locale={locale}
        xLabel={t(locale, "آستانه‌ی امتیاز قاعده‌ای", "Rule score threshold")}
        formatX={(x) => String(x)}
        series={[
          {
            label: t(locale, "دقت (وزن‌دار)", "Precision (weighted)"),
            tone: "brand",
            points: curve.map((c) => ({
              x: c.threshold,
              y: c.precision.estimate,
              low: c.precision.low,
              high: c.precision.high,
            })),
          },
          {
            label: t(locale, "بازیابی (وزن‌دار)", "Recall (weighted)"),
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
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function ErStrata({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const strata = Object.entries(a.data.revised.labels_by_stratum);
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(locale, "برچسب‌ها در هر لایه‌ی نمونه‌گیری", "Labels per sampling stratum")}
        minWidth="28rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "لایه", "Stratum")}</th>
            <th scope="col">{labelName("match", locale)}</th>
            <th scope="col">{labelName("non_match", locale)}</th>
            <th scope="col">{labelName("unsure", locale)}</th>
          </tr>
        </thead>
        <tbody>
          {strata.map(([stratum, counts]) => (
            <tr key={stratum}>
              <th scope="row" className="font-normal">
                <span className="ltr font-mono text-xs">{pick(STRATUM, stratum, locale)}</span>
              </th>
              <td>{f.int(counts.match ?? 0)}</td>
              <td>{f.int(counts.non_match ?? 0)}</td>
              <td>{f.int(counts.unsure ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function ErRevisions({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const revisions = a.data.revisions;
  const groups = new Map<string, number>();
  for (const r of revisions) {
    const key = `${r.kind.split(" (")[0]}|${r.before}|${r.after}`;
    groups.set(key, (groups.get(key) ?? 0) + 1);
  }
  return (
    <div className="space-y-3">
      <DataTable
        caption={t(locale, "خلاصه‌ی اصلاح برچسب‌ها", "Label revisions in brief")}
        minWidth="26rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "جفت‌ها", "Pairs")}</th>
            <th scope="col">{t(locale, "از", "From")}</th>
            <th scope="col">{t(locale, "به", "To")}</th>
            <th scope="col">{t(locale, "تعداد", "Count")}</th>
          </tr>
        </thead>
        <tbody>
          {[...groups.entries()].map(([key, count]) => {
            const [side, before, after] = key.split("|");
            return (
              <tr key={key}>
                <td>
                  {side === "same platform"
                    ? t(locale, "هم‌پلتفرم", "same platform")
                    : t(locale, "بین‌پلتفرمی", "cross-platform")}
                </td>
                <td>{labelName(before, locale)}</td>
                <td>{labelName(after, locale)}</td>
                <td>{f.int(count)}</td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <details className="group rounded-card border border-line bg-surface">
        <summary className="focus-ring flex cursor-pointer list-none items-center justify-between rounded-card p-4 text-sm font-medium [&::-webkit-details-marker]:hidden">
          {t(
            locale,
            `همه‌ی ${f.int(revisions.length)} اصلاح، هر کدام با دلیلش`,
            `All ${f.int(revisions.length)} revisions, each with its reason`,
          )}
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
                  {labelName(r.before, locale)} {t(locale, "←", "→")} {labelName(r.after, locale)}
                </Badge>
              </p>
              <p className="ltr mt-1 text-xs text-pretty text-fg-muted">{r.reason}</p>
            </li>
          ))}
        </ul>
      </details>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function ErAblations({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const NAME: Record<string, [string, string]> = {
    photos: ["فقط عکس", "photos only"],
    "other evidence": ["فقط شواهد دیگر", "other evidence only"],
    full: ["امتیاز کامل", "full score"],
  };
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(
          locale,
          "ablation: هر بخش شواهد به‌تنهایی",
          "Ablation: each part of the evidence alone",
        )}
        minWidth="34rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "شواهد", "Evidence")}</th>
            <th scope="col">{t(locale, "در معیار دقت", "At the precision bar")}</th>
            <th scope="col">{t(locale, "بهترین F1", "Best F1")}</th>
          </tr>
        </thead>
        <tbody>
          {a.data.ablations.map((x) => (
            <tr key={x.name}>
              <th scope="row" className="font-medium">
                {pick(NAME, x.name, locale)}
              </th>
              <td>
                {x.at_bar
                  ? t(
                      locale,
                      `آستانه‌ی ${f.decimal(x.at_bar.threshold)}: دقت ${f.interval(x.at_bar.precision)}، بازیابی ${f.interval(x.at_bar.recall)}`,
                      `threshold ${f.decimal(x.at_bar.threshold)}: precision ${f.interval(x.at_bar.precision)}, recall ${f.interval(x.at_bar.recall)}`,
                    )
                  : t(locale, "هیچ آستانه‌ای به آن نمی‌رسد", "no threshold reaches it")}
              </td>
              <td>
                {x.best_f1
                  ? t(
                      locale,
                      `${f.decimal(x.best_f1.f1, 3)} (دقت ${f.percent(x.best_f1.precision.estimate)}، بازیابی ${f.percent(x.best_f1.recall.estimate)})`,
                      `${f.decimal(x.best_f1.f1, 3)} (precision ${f.percent(x.best_f1.precision.estimate)}, recall ${f.percent(x.best_f1.recall.estimate)})`,
                    )
                  : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function JudgeVerdicts({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const queue = Object.entries(a.data.human_queue);
  return (
    <div className="space-y-3">
      <DataTable
        caption={t(
          locale,
          "رأی‌های داور روی نامزدهای تولید",
          "Judge verdicts on production candidates",
        )}
        minWidth="28rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "بازه‌ی امتیاز", "Score band")}</th>
            <th scope="col">{t(locale, "رأی", "Verdict")}</th>
            <th scope="col">{t(locale, "مطمئن", "Confident")}</th>
            <th scope="col">{t(locale, "جفت", "Pairs")}</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(a.data.judge_verdicts).map(([key, count]) => {
            const [band, verdict, sure] = key.split(":");
            return (
              <tr key={key}>
                <td>
                  {band === "above"
                    ? t(locale, "بالای آستانه", "above the threshold")
                    : t(locale, "زیر آستانه", "below the threshold")}
                </td>
                <td>{labelName(verdict, locale)}</td>
                <td>{sure === "confident" ? t(locale, "بله", "yes") : t(locale, "نه", "no")}</td>
                <td>{f.int(count)}</td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <p className="text-sm text-fg-muted">
        {t(locale, "صف انسانی", "Human queue")} <span className="ltr font-mono">er-human</span>:{" "}
        {queue
          .map(([k, v]) => `${k.replace("judge:", "")} ${f.int(v)}`)
          .join(t(locale, "، ", ", "))}
      </p>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

/** The judge bake-off, re-scored from the cache on the revised labels. */
export async function JudgeBakeoff({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const runs = await allOf("judge-eval");
  const latestByModel = new Map<string, Artifact<"judge-eval">>();
  for (const run of runs) {
    const model = String(run.provenance.model);
    if (!latestByModel.has(model)) latestByModel.set(model, run);
  }
  if (latestByModel.size === 0)
    return <Missing what={t(locale, "ارزیابی داور", "judge evaluation")} locale={locale} />;
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(locale, "مقایسه‌ی مدل‌های داور", "Judge model comparison")}
        minWidth="38rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "مدل", "Model")}</th>
            <th scope="col">{t(locale, "ادغام نادرست", "False merges")}</th>
            <th scope="col">{t(locale, "دقت «یکی است» (≥ ۰٫۸)", '"Match" precision (≥ 0.8)')}</th>
            <th scope="col">{t(locale, "بازیابی (≥ ۰٫۸)", "Recall (≥ 0.8)")}</th>
            <th scope="col">{t(locale, "نامطمئن", "Unsure")}</th>
            <th scope="col">{t(locale, "منبع", "Source")}</th>
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
                      {t(locale, "برگزیده", "chosen")}
                    </Badge>
                  ) : null}
                </th>
                <td className={run.data.false_matches > 0 ? "text-rose-700" : undefined}>
                  {f.int(run.data.false_matches)}
                </td>
                <td>{f.interval(at?.precision)}</td>
                <td>{f.interval(at?.recall)}</td>
                <td>{f.percent(run.data.unsure_rate)}</td>
                <td>
                  <SourceChip file={run.file} generatedAt={run.generated_at} locale={locale} />
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
export async function ErHumanQueue({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const a = await er();
  if (!a) return missingEr(locale);
  const labels = a.data.human_queue_labels;
  const judged = a.data.judge_on_human_queue;
  if (!labels || !judged) {
    return (
      <Callout
        kind="info"
        title={t(locale, "هنوز برچسبی روی صف انسانی نیست", "No labels on the human queue yet")}
      />
    );
  }
  const REASON: Record<string, [string, string]> = {
    "judge:suggested": [
      "داور گفت یکی است (زیر آستانه)",
      "the judge said match (below the threshold)",
    ],
    "judge:disputed": ["داور ادغام قواعد را رد کرد", "the judge vetoed a rule merge"],
    "judge:unsure": ["داور مطمئن نبود", "the judge was unsure"],
  };
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />;
  return (
    <div className="space-y-4">
      <MetricGrid className="lg:grid-cols-2">
        <MetricCard
          tone="verified"
          label={t(
            locale,
            "پیشنهادهای «یکی است» داور که مالک تأیید کرد",
            'The judge\'s "match" suggestions the owner confirmed',
          )}
          value={f.percent(judged.suggested_match_precision?.estimate)}
          detail={`${t(locale, "بازه‌ی ۹۵٪", "95% CI")}: ${f.range(judged.suggested_match_precision)}`}
          source={source}
        />
        <MetricCard
          tone="verified"
          label={t(
            locale,
            "ردهای داور که مالک تأیید کرد",
            "The judge's vetoes the owner confirmed",
          )}
          value={f.percent(judged.veto_precision?.estimate)}
          detail={`${t(locale, "بازه‌ی ۹۵٪", "95% CI")}: ${f.range(judged.veto_precision)}`}
          source={source}
        />
      </MetricGrid>
      <DataTable
        caption={t(
          locale,
          "برچسب‌های مالک روی صف er-human",
          "The owner's labels on the er-human queue",
        )}
        minWidth="30rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "چرا در صف آمد", "Why it was queued")}</th>
            <th scope="col">{labelName("match", locale)}</th>
            <th scope="col">{labelName("non_match", locale)}</th>
            <th scope="col">{labelName("unsure", locale)}</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(labels).map(([reason, c]) => (
            <tr key={reason}>
              <th scope="row" className="font-medium">
                {pick(REASON, reason, locale)}
              </th>
              <td>{f.int(c.match ?? 0)}</td>
              <td>{f.int(c.non_match ?? 0)}</td>
              <td>{f.int(c.unsure ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {source}
    </div>
  );
}
