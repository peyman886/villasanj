import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { latest } from "@/lib/artifacts";
import { faDecimal, faInt, faPercent } from "@/lib/format";

const SYSTEM_FA: Record<string, string> = {
  ranking: "رتبه‌بندی فعلی",
  price: "ارزان‌ترین اول",
  rating: "بهترین امتیاز اول",
};

/** M8 criterion 1 on the owner-reviewed query set, uncached. */
export async function UnderstandingResults() {
  const a = await latest("understanding");
  if (!a) {
    return (
      <Callout kind="caution" title="گزارش فهم پرسش پیدا نشد">
        <code className="ltr font-mono">discovery eval-understanding --fresh --out</code>
      </Callout>
    );
  }
  const u = a.data;
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} />;
  return (
    <MetricGrid className="lg:grid-cols-2">
      <MetricCard
        tone="verified"
        label="اسلات درست"
        value={faPercent(u.slot_accuracy)}
        detail={`کاملاً درست ${faPercent(u.exact_match)} از ${faInt(u.cases)} پرسش بازبینی‌شده`}
        source={source}
      />
      <MetricCard
        tone="verified"
        label="عدد ساختگی"
        value={faInt(u.invented)}
        detail={`${faInt(u.failures)} پرسش بی‌پاسخ`}
        source={source}
      />
      {u.latency.map((l) => (
        <MetricCard
          key={l.model}
          label={`تأخیر بدون کش · ${l.model}`}
          value={`${faInt(l.p95_ms)} ms`}
          detail={`p95 روی ${faInt(l.uncached)} فراخوانی؛ میانه ${faInt(l.p50_ms)} ms؛ هدف ≤ ۳۰۰۰ ms`}
          source={source}
        />
      ))}
    </MetricGrid>
  );
}

/** M8 criterion 2: nDCG@10 and Recall@20 per order on the owner's relevance grades. */
export async function RelevanceResults() {
  const a = await latest("relevance");
  if (!a) {
    return (
      <Callout kind="caution" title="گزارش مرتبط‌بودن پیدا نشد">
        <code className="ltr font-mono">discovery relevance-eval --out</code>
      </Callout>
    );
  }
  const r = a.data;
  return (
    <div className="space-y-2">
      <DataTable caption="ارزیابی ترتیب نتیجه‌ها روی داوری مالک" minWidth="30rem">
        <thead>
          <tr>
            <th scope="col">ترتیب</th>
            <th scope="col">nDCG@10</th>
            <th scope="col">Recall@20</th>
            <th scope="col">پرسش</th>
          </tr>
        </thead>
        <tbody>
          {r.systems.map((x) => (
            <tr key={x.system} className={x.system === "ranking" ? "bg-brand-50/60" : undefined}>
              <th scope="row" className="font-medium">
                {SYSTEM_FA[x.system] ?? x.system}
              </th>
              <td>{x.ndcg_at_10 === null ? "-" : faDecimal(x.ndcg_at_10, 3)}</td>
              <td>{x.recall_at_20 === null ? "-" : faDecimal(x.recall_at_20, 3)}</td>
              <td>{faInt(x.queries)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="text-sm text-pretty text-fg-muted">
        {faInt(r.judged)} پرسش از {faInt(r.total)} کامل داوری شده‌اند ({faInt(r.judgements)} داوری).
        Recall@20 دو baseline کران پایین است، چون جایگاه‌های ۱۱ تا ۲۰ آن‌ها تجمیع نشده بود؛ nDCG@10
        مقایسه‌ی منصفانه است.
      </p>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}
