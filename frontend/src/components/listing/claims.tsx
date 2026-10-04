import { ChevronDown, MapPinned } from "lucide-react";
import type { ReactNode } from "react";

import { Sourced } from "@/components/sourced";
import { Section } from "@/components/ui/card";
import { VERDICT_BAR, VerdictBadge } from "@/components/ui/status";
import type { Claims, Listing } from "@/lib/api/client";
import { CLAIM_VERDICT_ORDER, CLAIM_VERDICT_TEXT, faNumber } from "@/lib/listing";
import { FEATURE_TEXT } from "@/lib/search";

type ClaimRow = {
  key: string;
  verdict: string;
  claim: ReactNode;
  evidence: string;
  evidenceProvenance: Claims["distances"][number]["evidence_provenance"];
  radiusAssumed: boolean;
};

function ClaimItem({ row, now }: { row: ClaimRow; now: Date }) {
  return (
    <li className="grid gap-2 p-4 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <div>
        <VerdictBadge verdict={row.verdict} />
      </div>
      <div className="min-w-0 text-sm">
        <p className="font-medium text-pretty">{row.claim}</p>
        <p className="mt-1 flex gap-1.5 text-pretty text-fg-muted">
          <MapPinned aria-hidden="true" className="mt-1 size-3.5 shrink-0" />
          <span>
            {row.evidenceProvenance ? (
              <Sourced
                id={`claim-evidence-${row.key}`}
                label="شاهد"
                value={row.evidence}
                provenance={row.evidenceProvenance}
                now={now}
              >
                {row.evidence}
              </Sourced>
            ) : (
              row.evidence
            )}
          </span>
        </p>
        {row.radiusAssumed ? (
          <p className="mt-1 text-xs text-fg-subtle">
            پلتفرم دقت نقطه را اعلام نکرده؛ تا ۵۰۰ متر خطا فرض شده.
          </p>
        ) : null}
      </div>
    </li>
  );
}

/** «پارکینگ ندارد: »; nothing when the quoted words already name the feature. */
function featureLabel(feature: string, span: string, polarity: string): string {
  const label = FEATURE_TEXT[feature] ?? feature;
  if (polarity === "has_not") return `${label} ندارد: `;
  return span.includes(label) ? "" : `${label}: `;
}

/** The listing's own claims beside their evidence (M9 truth check, listing level). */
export function ClaimsSection({
  listing,
  claims,
  now,
  idPrefix = "",
}: {
  listing: Listing;
  claims: Claims | null;
  now: Date;
  idPrefix?: string; // several sections on one page (a villa) need distinct ids
}) {
  if (!claims || claims.distances.length + claims.features.length === 0) return null;
  const rows: ClaimRow[] = [
    ...claims.distances.map((c, index) => ({
      key: `${idPrefix}d${index}`,
      verdict: c.verdict,
      claim: (
        <Sourced
          id={`${idPrefix}claim-d${index}`}
          label="ادعای آگهی"
          provenance={c.provenance}
          now={now}
        >
          {c.text}
        </Sourced>
      ),
      evidence: c.evidence,
      evidenceProvenance: c.evidence_provenance,
      radiusAssumed: c.radius_assumed && c.evidence_provenance !== null,
    })),
    ...claims.features.map((c, index) => ({
      key: `${idPrefix}f${index}`,
      verdict: c.verdict,
      claim: (
        <>
          {featureLabel(c.feature, c.span, c.polarity)}
          <Sourced
            id={`${idPrefix}claim-f${index}`}
            label="ادعای آگهی"
            provenance={c.provenance}
            now={now}
          >
            «{c.span}»
          </Sourced>
        </>
      ),
      evidence: c.evidence,
      evidenceProvenance: c.evidence_provenance,
      radiusAssumed: false,
    })),
  ].sort((a, b) => CLAIM_VERDICT_ORDER.indexOf(a.verdict) - CLAIM_VERDICT_ORDER.indexOf(b.verdict));
  const checked = rows.filter((r) => r.verdict !== "not_checked");
  const unchecked = rows.filter((r) => r.verdict === "not_checked");
  const counts = CLAIM_VERDICT_ORDER.map(
    (verdict) => [verdict, rows.filter((r) => r.verdict === verdict).length] as const,
  ).filter(([, count]) => count > 0);
  return (
    <Section
      id={`${idPrefix}claims`}
      title={`حقیقت‌سنجی ادعاها${idPrefix ? ` در ${listing.platform_name}` : ""}`}
      description={
        <>
          ادعاهای خود آگهی در {listing.platform_name}، هر کدام کنار شاهدش. «تأیید نشد» یعنی شاهد
          کافی نداریم، نه اینکه ادعا نادرست است.
        </>
      }
    >
      <div className="rounded-card border border-line bg-surface p-4">
        <div className="flex h-2.5 overflow-hidden rounded-full bg-sand-100" aria-hidden="true">
          {counts.map(([verdict, count]) => (
            <div
              key={verdict}
              className={VERDICT_BAR[verdict] ?? "bg-sand-300"}
              style={{ width: `${(count / rows.length) * 100}%` }}
            />
          ))}
        </div>
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-fg-muted tabular-nums">
          {counts.map(([verdict, count]) => (
            <li key={verdict} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className={`size-2.5 rounded-full ${VERDICT_BAR[verdict] ?? "bg-sand-300"}`}
              />
              {CLAIM_VERDICT_TEXT[verdict]}: {faNumber(count)}
            </li>
          ))}
        </ul>
      </div>
      {checked.length > 0 ? (
        <ul className="mt-3 divide-y divide-line rounded-card border border-line bg-surface">
          {checked.map((row) => (
            <ClaimItem key={row.key} row={row} now={now} />
          ))}
        </ul>
      ) : null}
      {unchecked.length > 0 ? (
        <details className="group mt-3 rounded-card border border-line bg-surface">
          <summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 rounded-card p-4 text-sm text-fg-muted hover:text-fg [&::-webkit-details-marker]:hidden">
            ادعاهای بررسی‌نشده ({faNumber(unchecked.length)})
            <ChevronDown
              aria-hidden="true"
              className="size-4 transition-transform group-open:rotate-180"
            />
          </summary>
          <ul className="divide-y divide-line border-t border-line">
            {unchecked.map((row) => (
              <ClaimItem key={row.key} row={row} now={now} />
            ))}
          </ul>
        </details>
      ) : null}
    </Section>
  );
}
