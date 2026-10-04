import { BarList } from "@/components/charts/bars";
import { IntervalChart } from "@/components/charts/interval";
import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { latest } from "@/lib/artifacts";
import { faInt, faInterval, faPercent, faRatio } from "@/lib/format";

const PLATFORM_FA: Record<string, string> = { jabama: "جاباما", shab: "شب" };
const SCENARIO_FA: Record<string, string> = {
  weekend: "آخر هفته",
  midweek: "وسط هفته",
  holiday: "تعطیلات",
};

function Missing() {
  return (
    <Callout kind="caution" title="گزارش فرضیه‌ها پیدا نشد">
      <code className="ltr font-mono">uv run villasanj er hypotheses</code> را اجرا کنید.
    </Callout>
  );
}

export async function HypothesesHeadline() {
  const a = await latest("hypotheses");
  if (!a) return <Missing />;
  const { h1, h3, h2_flips } = a.data;
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} />;
  const holiday = a.data.h2.find((g) => g.scenario === "holiday");
  return (
    <MetricGrid className="lg:grid-cols-2">
      <MetricCard
        label="H1 · جفت‌های تطبیق‌خورده"
        value={faInt(h1.pairs)}
        detail={
          h1.corrected_pairs
            ? `اصلاح‌شده برای دقت و بازیابی: حدود ${faInt(Math.round(h1.corrected_pairs.estimate ?? 0))}`
            : undefined
        }
        source={source}
      />
      <MetricCard
        label="H1 · ویلاهای روی هر دو پلتفرم"
        value={faPercent(h1.villas_on_both_share?.estimate)}
        detail={
          h1.villas_on_both_share
            ? `بازه: ${faPercent(h1.villas_on_both_share.low)} تا ${faPercent(h1.villas_on_both_share.high)}`
            : undefined
        }
        source={source}
      />
      <MetricCard
        label="H2 · میانه‌ی اختلاف در تعطیلات"
        value={faRatio(holiday?.median_ratio)}
        detail={`پلتفرم ارزان‌تر برای ${faInt(h2_flips.flips)} از ${faInt(h2_flips.pairs)} جفت عوض می‌شود`}
        source={source}
      />
      <MetricCard
        tone="verified"
        label="H3 · شب‌های پنهان"
        value={faPercent(h3.hidden_nights / Math.max(1, h3.nights_compared))}
        detail={`در ${faInt(h3.pairs_with_hidden_night)} جفت از ${faInt(h3.pairs)}`}
        source={source}
      />
    </MetricGrid>
  );
}

export async function H2Table() {
  const a = await latest("hypotheses");
  if (!a) return <Missing />;
  return (
    <div className="space-y-2">
      <DataTable caption="H2: اختلاف جمع قیمت یک ویلا بین دو پلتفرم" minWidth="36rem">
        <thead>
          <tr>
            <th scope="col">سناریو</th>
            <th scope="col">نفر</th>
            <th scope="col">جفت قابل رزرو در هر دو</th>
            <th scope="col">میانه‌ی گران‌تر/ارزان‌تر</th>
            <th scope="col">صدک ۹۰</th>
            <th scope="col">ارزان‌تر در</th>
          </tr>
        </thead>
        <tbody>
          {a.data.h2.map((g) => (
            <tr key={`${g.scenario}-${g.guests}`}>
              <td>{SCENARIO_FA[g.scenario] ?? g.scenario}</td>
              <td>{faInt(g.guests)}</td>
              <td>{faInt(g.pairs)}</td>
              <td>{faRatio(g.median_ratio)}</td>
              <td>{faRatio(g.p90_ratio)}</td>
              <td>
                {Object.entries(g.cheaper)
                  .map(([p, n]) => `${PLATFORM_FA[p] ?? p} ${faInt(n)}`)
                  .join("، ")}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function H1Table() {
  const a = await latest("hypotheses");
  if (!a) return <Missing />;
  return (
    <div className="space-y-2">
      <BarList
        label="سهم آگهی‌های هر پلتفرم با همتا"
        max={1}
        bars={Object.entries(a.data.h1.listings).map(([platform, total]) => ({
          label: `${PLATFORM_FA[platform] ?? platform} (${faInt(total)} آگهی)`,
          value: (a.data.h1.matched[platform] ?? 0) / Math.max(1, total),
          display: `${faInt(a.data.h1.matched[platform] ?? 0)} آگهی · ${faPercent((a.data.h1.matched[platform] ?? 0) / Math.max(1, total))}`,
        }))}
      />
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function H4Table() {
  const a = await latest("h4");
  if (!a) {
    return (
      <Callout kind="caution" title="گزارش H4 پیدا نشد">
        <code className="ltr font-mono">
          uv run villasanj enrichment h4 --out reports/h4-&lt;date&gt;.md
        </code>
      </Callout>
    );
  }
  return (
    <div className="space-y-3">
      <IntervalChart
        label="سهم H4 با بازه‌ی ۹۵٪"
        max={0.3}
        bar={0.25}
        barLabel="خط‌چین: فرضیه‌ی گزارش پژوهشی، دست‌کم ۲۵٪"
        rows={a.data.platforms.map((p) => ({
          label: PLATFORM_FA[p.platform] ?? p.platform,
          interval: p.share,
          highlight: true,
        }))}
      />
      <DataTable caption="H4 به تفکیک پلتفرم" minWidth="40rem">
        <thead>
          <tr>
            <th scope="col">پلتفرم</th>
            <th scope="col">آگهی</th>
            <th scope="col">سنجیده‌شده</th>
            <th scope="col">ناسازگار با نقشه</th>
            <th scope="col">ناهمخوان بین پلتفرم‌ها</th>
            <th scope="col">هر کدام</th>
            <th scope="col">سهم</th>
          </tr>
        </thead>
        <tbody>
          {a.data.platforms.map((p) => (
            <tr key={p.platform}>
              <th scope="row" className="font-medium">
                {PLATFORM_FA[p.platform] ?? p.platform}
              </th>
              <td>{faInt(p.listings)}</td>
              <td>{faInt(p.judged)}</td>
              <td>{faInt(p.contradicted)}</td>
              <td>{faInt(p.inconsistent)}</td>
              <td>{faInt(p.either)}</td>
              <td>{faInterval(p.share)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}

export async function H3Table() {
  const a = await latest("hypotheses");
  if (!a) return <Missing />;
  const h3 = a.data.h3;
  const window = a.provenance.window as string[] | undefined;
  return (
    <div className="space-y-2">
      <DataTable caption="H3: شب‌هایی که روی یک پلتفرم آزاد و روی دیگری پر است" minWidth="30rem">
        <tbody>
          <tr>
            <th scope="row" className="font-medium">
              شب‌های مقایسه‌شده (هر دو پلتفرم با کمتر از {faInt(h3.max_gap_hours)} ساعت فاصله)
            </th>
            <td>{faInt(h3.nights_compared)}</td>
          </tr>
          <tr>
            <th scope="row" className="font-medium">
              شب‌های پنهان
            </th>
            <td>
              {faInt(h3.hidden_nights)} (
              {faPercent(h3.hidden_nights / Math.max(1, h3.nights_compared))})
            </td>
          </tr>
          <tr>
            <th scope="row" className="font-medium">
              جفت‌هایی که دست‌کم یک شب پنهان دارند
            </th>
            <td>
              {faInt(h3.pairs_with_hidden_night)} از {faInt(h3.pairs)}
            </td>
          </tr>
          {window ? (
            <tr>
              <th scope="row" className="font-medium">
                بازه‌ی تقویم
              </th>
              <td className="ltr">{window.join(" → ")}</td>
            </tr>
          ) : null}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} />
    </div>
  );
}
