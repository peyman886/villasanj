import { BarList } from "@/components/charts/bars";
import { IntervalChart } from "@/components/charts/interval";
import { Callout } from "@/components/ui/callout";
import { MetricCard, MetricGrid } from "@/components/ui/metric";
import { SourceChip } from "@/components/ui/source";
import { DataTable } from "@/components/ui/table";
import { latest } from "@/lib/artifacts";
import { formatFor } from "@/lib/format";
import { type Locale, t } from "@/lib/i18n";

type Names = Record<string, { fa: string; en: string }>;

const PLATFORM: Names = {
  jabama: { fa: "جاباما", en: "Jabama" },
  shab: { fa: "شب", en: "Shab" },
};
const SCENARIO: Names = {
  weekend: { fa: "آخر هفته", en: "Weekend" },
  midweek: { fa: "وسط هفته", en: "Midweek" },
  holiday: { fa: "تعطیلات", en: "Holiday" },
};

function name(names: Names, key: string, locale: Locale): string {
  return names[key]?.[locale] ?? key;
}

function Missing({ locale }: { locale: Locale }) {
  return (
    <Callout
      kind="caution"
      title={t(locale, "گزارش فرضیه‌ها پیدا نشد", "Hypotheses report not found")}
    >
      {t(locale, "", "Run ")}
      <code className="ltr font-mono">uv run villasanj er hypotheses</code>
      {t(locale, " را اجرا کنید.", ".")}
    </Callout>
  );
}

export async function HypothesesHeadline({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("hypotheses");
  if (!a) return <Missing locale={locale} />;
  const f = formatFor(locale);
  const { h1, h3, h2_flips } = a.data;
  const source = <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />;
  const holiday = a.data.h2.find((g) => g.scenario === "holiday");
  return (
    <MetricGrid className="lg:grid-cols-2">
      <MetricCard
        label={t(locale, "H1 · جفت‌های تطبیق‌خورده", "H1 · Matched pairs")}
        value={f.int(h1.pairs)}
        detail={
          h1.corrected_pairs
            ? t(
                locale,
                `اصلاح‌شده برای دقت و بازیابی: حدود ${f.int(Math.round(h1.corrected_pairs.estimate ?? 0))}`,
                `Corrected for precision and recall: about ${f.int(Math.round(h1.corrected_pairs.estimate ?? 0))}`,
              )
            : undefined
        }
        source={source}
      />
      <MetricCard
        label={t(locale, "H1 · ویلاهای روی هر دو پلتفرم", "H1 · Villas on both platforms")}
        value={f.percent(h1.villas_on_both_share?.estimate)}
        detail={
          h1.villas_on_both_share
            ? t(
                locale,
                `بازه: ${f.percent(h1.villas_on_both_share.low)} تا ${f.percent(h1.villas_on_both_share.high)}`,
                `Interval: ${f.percent(h1.villas_on_both_share.low)} to ${f.percent(h1.villas_on_both_share.high)}`,
              )
            : undefined
        }
        source={source}
      />
      <MetricCard
        label={t(locale, "H2 · میانه‌ی اختلاف در تعطیلات", "H2 · Median gap on holidays")}
        value={f.ratio(holiday?.median_ratio)}
        detail={t(
          locale,
          `پلتفرم ارزان‌تر برای ${f.int(h2_flips.flips)} از ${f.int(h2_flips.pairs)} جفت عوض می‌شود`,
          `The cheaper platform flips for ${f.int(h2_flips.flips)} of ${f.int(h2_flips.pairs)} pairs`,
        )}
        source={source}
      />
      <MetricCard
        tone="verified"
        label={t(locale, "H3 · شب‌های پنهان", "H3 · Hidden nights")}
        value={f.percent(h3.hidden_nights / Math.max(1, h3.nights_compared))}
        detail={t(
          locale,
          `در ${f.int(h3.pairs_with_hidden_night)} جفت از ${f.int(h3.pairs)}`,
          `In ${f.int(h3.pairs_with_hidden_night)} of ${f.int(h3.pairs)} pairs`,
        )}
        source={source}
      />
    </MetricGrid>
  );
}

export async function H2Table({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("hypotheses");
  if (!a) return <Missing locale={locale} />;
  const f = formatFor(locale);
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(
          locale,
          "H2: اختلاف جمع قیمت یک ویلا بین دو پلتفرم",
          "H2: gap in a villa's total price between the two platforms",
        )}
        minWidth="36rem"
      >
        <thead>
          <tr>
            <th scope="col">{t(locale, "سناریو", "Scenario")}</th>
            <th scope="col">{t(locale, "نفر", "Guests")}</th>
            <th scope="col">{t(locale, "جفت قابل رزرو در هر دو", "Pairs bookable on both")}</th>
            <th scope="col">{t(locale, "میانه‌ی گران‌تر/ارزان‌تر", "Median dearer/cheaper")}</th>
            <th scope="col">{t(locale, "صدک ۹۰", "90th percentile")}</th>
            <th scope="col">{t(locale, "ارزان‌تر در", "Cheaper on")}</th>
          </tr>
        </thead>
        <tbody>
          {a.data.h2.map((g) => (
            <tr key={`${g.scenario}-${g.guests}`}>
              <td>{name(SCENARIO, g.scenario, locale)}</td>
              <td>{f.int(g.guests)}</td>
              <td>{f.int(g.pairs)}</td>
              <td>{f.ratio(g.median_ratio)}</td>
              <td>{f.ratio(g.p90_ratio)}</td>
              <td>
                {Object.entries(g.cheaper)
                  .map(([p, n]) => `${name(PLATFORM, p, locale)} ${f.int(n)}`)
                  .join(t(locale, "، ", ", "))}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function H1Table({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("hypotheses");
  if (!a) return <Missing locale={locale} />;
  const f = formatFor(locale);
  return (
    <div className="space-y-2">
      <BarList
        label={t(
          locale,
          "سهم آگهی‌های هر پلتفرم با همتا",
          "Share of each platform's listings with a counterpart",
        )}
        max={1}
        bars={Object.entries(a.data.h1.listings).map(([platform, total]) => {
          const matched = a.data.h1.matched[platform] ?? 0;
          const share = f.percent(matched / Math.max(1, total));
          return {
            label: t(
              locale,
              `${name(PLATFORM, platform, locale)} (${f.int(total)} آگهی)`,
              `${name(PLATFORM, platform, locale)} (${f.int(total)} listings)`,
            ),
            value: matched / Math.max(1, total),
            display: t(
              locale,
              `${f.int(matched)} آگهی · ${share}`,
              `${f.int(matched)} listings · ${share}`,
            ),
          };
        })}
      />
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function H4Table({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("h4");
  if (!a) {
    return (
      <Callout kind="caution" title={t(locale, "گزارش H4 پیدا نشد", "H4 report not found")}>
        <code className="ltr font-mono">
          uv run villasanj enrichment h4 --out reports/h4-&lt;date&gt;.md
        </code>
      </Callout>
    );
  }
  const f = formatFor(locale);
  return (
    <div className="space-y-3">
      <IntervalChart
        label={t(locale, "سهم H4 با بازه‌ی ۹۵٪", "H4 share with its 95% interval")}
        max={0.3}
        bar={0.25}
        barLabel={t(
          locale,
          "خط‌چین: فرضیه‌ی گزارش پژوهشی، دست‌کم ۲۵٪",
          "Dashed line: the research report's hypothesis, at least 25%",
        )}
        locale={locale}
        rows={a.data.platforms.map((p) => ({
          label: name(PLATFORM, p.platform, locale),
          interval: p.share,
          highlight: true,
        }))}
      />
      <DataTable caption={t(locale, "H4 به تفکیک پلتفرم", "H4 by platform")} minWidth="40rem">
        <thead>
          <tr>
            <th scope="col">{t(locale, "پلتفرم", "Platform")}</th>
            <th scope="col">{t(locale, "آگهی", "Listings")}</th>
            <th scope="col">{t(locale, "سنجیده‌شده", "Judged")}</th>
            <th scope="col">{t(locale, "ناسازگار با نقشه", "Contradicted by the map")}</th>
            <th scope="col">
              {t(locale, "ناهمخوان بین پلتفرم‌ها", "Inconsistent across platforms")}
            </th>
            <th scope="col">{t(locale, "هر کدام", "Either")}</th>
            <th scope="col">{t(locale, "سهم", "Share")}</th>
          </tr>
        </thead>
        <tbody>
          {a.data.platforms.map((p) => (
            <tr key={p.platform}>
              <th scope="row" className="font-medium">
                {name(PLATFORM, p.platform, locale)}
              </th>
              <td>{f.int(p.listings)}</td>
              <td>{f.int(p.judged)}</td>
              <td>{f.int(p.contradicted)}</td>
              <td>{f.int(p.inconsistent)}</td>
              <td>{f.int(p.either)}</td>
              <td>{f.interval(p.share)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}

export async function H3Table({ locale = "fa" }: { locale?: Locale }) {
  const a = await latest("hypotheses");
  if (!a) return <Missing locale={locale} />;
  const f = formatFor(locale);
  const h3 = a.data.h3;
  const window = a.provenance.window as string[] | undefined;
  return (
    <div className="space-y-2">
      <DataTable
        caption={t(
          locale,
          "H3: شب‌هایی که روی یک پلتفرم آزاد و روی دیگری پر است",
          "H3: nights free on one platform and taken on the other",
        )}
        minWidth="30rem"
      >
        <tbody>
          <tr>
            <th scope="row" className="font-medium">
              {t(
                locale,
                `شب‌های مقایسه‌شده (هر دو پلتفرم با کمتر از ${f.int(h3.max_gap_hours)} ساعت فاصله)`,
                `Nights compared (both platforms seen less than ${f.int(h3.max_gap_hours)} hours apart)`,
              )}
            </th>
            <td>{f.int(h3.nights_compared)}</td>
          </tr>
          <tr>
            <th scope="row" className="font-medium">
              {t(locale, "شب‌های پنهان", "Hidden nights")}
            </th>
            <td>
              {f.int(h3.hidden_nights)} (
              {f.percent(h3.hidden_nights / Math.max(1, h3.nights_compared))})
            </td>
          </tr>
          <tr>
            <th scope="row" className="font-medium">
              {t(
                locale,
                "جفت‌هایی که دست‌کم یک شب پنهان دارند",
                "Pairs with at least one hidden night",
              )}
            </th>
            <td>
              {t(
                locale,
                `${f.int(h3.pairs_with_hidden_night)} از ${f.int(h3.pairs)}`,
                `${f.int(h3.pairs_with_hidden_night)} of ${f.int(h3.pairs)}`,
              )}
            </td>
          </tr>
          {window ? (
            <tr>
              <th scope="row" className="font-medium">
                {t(locale, "بازه‌ی تقویم", "Calendar window")}
              </th>
              <td className="ltr">{window.join(" → ")}</td>
            </tr>
          ) : null}
        </tbody>
      </DataTable>
      <SourceChip file={a.file} generatedAt={a.generated_at} locale={locale} />
    </div>
  );
}
