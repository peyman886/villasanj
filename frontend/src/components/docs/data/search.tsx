import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { latest } from "@/lib/artifacts";
import { formatFor } from "@/lib/format";
import { type Locale, t } from "@/lib/i18n";

const SYSTEM: Record<string, { fa: string; en: string }> = {
  ranking: { fa: "رتبه‌بندی فعلی", en: "Current ranking" },
  price: { fa: "ارزان‌ترین اول", en: "Cheapest first" },
  rating: { fa: "بهترین امتیاز اول", en: "Best rated first" },
};

/** M8 criterion 1 on the owner-reviewed query set, uncached. */
export async function UnderstandingResults({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("understanding");
  if (!a) {
    return (
      <Callout
        kind="caution"
        title={t(locale, "گزارش فهم پرسش پیدا نشد", "Query understanding report not found")}
      >
        <code className="ltr font-mono">discovery eval-understanding --fresh --out</code>
      </Callout>
    );
  }
  const f = formatFor(locale);
  const u = a.data;
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />;
  return (
    <MetricGrid className="lg:grid-cols-2">
      <MetricCard
        tone="verified"
        label={t(locale, "اسلات درست", "Slots correct")}
        value={f.percent(u.slot_accuracy)}
        detail={t(
          locale,
          `کاملاً درست ${f.percent(u.exact_match)} از ${f.int(u.cases)} پرسش بازبینی‌شده`,
          `Exact match ${f.percent(u.exact_match)} of ${f.int(u.cases)} reviewed queries`,
        )}
        source={source}
      />
      <MetricCard
        tone="verified"
        label={t(locale, "عدد ساختگی", "Invented numbers")}
        value={f.int(u.invented)}
        detail={t(
          locale,
          `${f.int(u.failures)} پرسش بی‌پاسخ`,
          `${f.int(u.failures)} queries without an answer`,
        )}
        source={source}
      />
      {u.latency.map((l) => (
        <MetricCard
          key={l.model}
          label={t(locale, `تأخیر بدون کش · ${l.model}`, `Uncached latency · ${l.model}`)}
          value={`${f.int(l.p95_ms)} ms`}
          detail={t(
            locale,
            `p95 روی ${f.int(l.uncached)} فراخوانی؛ میانه ${f.int(l.p50_ms)} ms؛ هدف ≤ ۳۰۰۰ ms`,
            `p95 over ${f.int(l.uncached)} calls; median ${f.int(l.p50_ms)} ms; target ≤ 3,000 ms`,
          )}
          source={source}
        />
      ))}
    </MetricGrid>
  );
}

/** M8 criterion 2: nDCG@10 and Recall@20 per order on the owner's relevance grades. */
export async function RelevanceResults({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("relevance");
  if (!a) {
    return (
      <Callout
        kind="caution"
        title={t(locale, "گزارش مرتبط‌بودن پیدا نشد", "Relevance report not found")}
      >
        <code className="ltr font-mono">discovery relevance-eval --out</code>
      </Callout>
    );
  }
  const f = formatFor(locale);
  const r = a.data;
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(
          locale,
          "ارزیابی ترتیب نتیجه‌ها روی داوری مالک",
          "Result orders evaluated on the owner's grades",
        )}
        minWidth="30rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "ترتیب", "Order")}</th>
            <th scope="col">nDCG@10</th>
            <th scope="col">Recall@20</th>
            <th scope="col">{t(locale, "پرسش", "Queries")}</th>
          </tr>
        </thead>
        <tbody>
          {r.systems.map((x) => (
            <tr key={x.system} className={x.system === "ranking" ? "bg-brand-50/60" : undefined}>
              <th scope="row" className="font-medium">
                {SYSTEM[x.system]?.[locale] ?? x.system}
              </th>
              <td>{x.ndcg_at_10 === null ? "-" : f.decimal(x.ndcg_at_10, 3)}</td>
              <td>{x.recall_at_20 === null ? "-" : f.decimal(x.recall_at_20, 3)}</td>
              <td>{f.int(x.queries)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="text-sm text-pretty text-fg-muted">
        {locale === "en" ? (
          <>
            {f.int(r.judged)} of {f.int(r.total)} queries are fully graded ({f.int(r.judgements)}{" "}
            grades). Recall@20 for the two baselines is a lower bound, because their positions 11 to
            20 were not pooled; nDCG@10 is the fair comparison.
          </>
        ) : (
          <>
            {f.int(r.judged)} پرسش از {f.int(r.total)} کامل داوری شده‌اند ({f.int(r.judgements)}{" "}
            داوری). Recall@20 دو baseline کران پایین است، چون جایگاه‌های ۱۱ تا ۲۰ آن‌ها در مجموعه‌ی
            داوری نیامده بود؛ مقایسه‌ی منصفانه nDCG@10 است.
          </>
        )}
      </p>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}
