import { Sourced } from "@/components/sourced";
import type { Listing, Villa } from "@/lib/api/client";
import { COPY } from "@/lib/copy";
import { faPropertyType } from "@/lib/labeling";
import { faNum } from "@/lib/numbers";
import { platformRank } from "@/lib/platforms";

type Field =
  "property_type" | "bedrooms" | "bathrooms" | "area_m2" | "base_capacity" | "max_capacity";

const FIELDS: { key: Field; label: string; text: (v: number | string) => string }[] = [
  { key: "property_type", label: "نوع", text: (v) => faPropertyType(String(v)) },
  { key: "bedrooms", label: "اتاق خواب", text: (v) => `${faNum(Number(v))} خوابه` },
  { key: "bathrooms", label: "سرویس بهداشتی", text: (v) => `${faNum(Number(v))} سرویس` },
  { key: "base_capacity", label: "ظرفیت پایه", text: (v) => `ظرفیت پایه ${faNum(Number(v))} نفر` },
  { key: "max_capacity", label: "حداکثر ظرفیت", text: (v) => `تا ${faNum(Number(v))} مهمان` },
  { key: "area_m2", label: "متراژ", text: (v) => `${faNum(Number(v))} متر` },
];

/**
 * What the listings agree on, as one line; a small table only for the fields they state
 * differently, labelled «دو عدد متفاوت» (V12). Each value keeps its source; none is averaged.
 */
export function Specs({ villa, now }: { villa: Villa; now: Date }) {
  const members = [...villa.members].sort(
    (a, b) => platformRank(a.platform) - platformRank(b.platform),
  );
  const differing = new Set(villa.conflicts.map((c) => c.field));
  const agreed = FIELDS.filter((f) => !differing.has(f.key))
    .map((f) => {
      const source = members.find((m) => m[f.key] !== null && m[f.key] !== undefined);
      return source ? { field: f, member: source, value: source[f.key] as number | string } : null;
    })
    .filter(
      (x): x is { field: (typeof FIELDS)[number]; member: Listing; value: number | string } =>
        x !== null,
    );
  const rows = FIELDS.filter((f) => differing.has(f.key));
  return (
    <section id="stay" aria-labelledby="stay-title" className="scroll-mt-28">
      <h2 id="stay-title" className="text-xl font-bold">
        اقامت
      </h2>
      {agreed.length ? (
        <p className="mt-2 text-base tabular-nums">
          {agreed.map((a, i) => (
            <span key={a.field.key}>
              {i > 0 ? (
                <span aria-hidden="true" className="text-fg-subtle">
                  {" "}
                  ∙{" "}
                </span>
              ) : null}
              <Sourced
                quiet
                id={`spec-${a.field.key}`}
                label={`${a.field.label} به گفته‌ی ${a.member.platform_name}`}
                provenance={a.member.provenance}
                sourceName={a.member.platform_name}
                now={now}
              >
                {a.field.text(a.value)}
              </Sourced>
            </span>
          ))}
        </p>
      ) : null}
      {rows.length ? (
        <table className="mt-4 w-full max-w-lg text-sm">
          <caption className="sr-only">مشخصاتی که آگهی‌ها متفاوت گفته‌اند</caption>
          <thead>
            <tr className="text-fg-muted">
              <th scope="col" className="py-1 text-start font-normal">
                <span className="sr-only">مشخصه</span>
              </th>
              {members.map((m) => (
                <th key={m.id} scope="col" className="py-1 text-start font-normal">
                  {m.platform_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.key} className="border-t border-line">
                <th scope="row" className="py-2 text-start font-medium">
                  {f.label}
                  <span className="ms-2 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-caution ring-1 ring-amber-200">
                    {COPY.twoValues}
                  </span>
                </th>
                {members.map((m) => {
                  const value = m[f.key];
                  return (
                    <td key={m.id} className="py-2 tabular-nums">
                      {value === null || value === undefined ? (
                        <span className="text-fg-subtle">منتشر نشده</span>
                      ) : (
                        <Sourced
                          id={`diff-${f.key}-${m.platform}`}
                          label={`${f.label} در ${m.platform_name}`}
                          provenance={m.provenance}
                          sourceName={m.platform_name}
                          now={now}
                        >
                          {f.key === "property_type"
                            ? faPropertyType(String(value))
                            : f.key === "area_m2"
                              ? `${faNum(Number(value))} متر`
                              : faNum(Number(value))}
                        </Sourced>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
