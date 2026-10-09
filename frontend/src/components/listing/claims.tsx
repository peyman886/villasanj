import { ChevronDown, MapPinned } from "lucide-react";
import type { ReactNode } from "react";

import { Sourced } from "@/components/sourced";
import { Section } from "@/components/ui/card";
import { VerdictBadge } from "@/components/ui/status";
import type { Claims, Listing } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { faNum } from "@/lib/numbers";
import { FEATURE_TEXT } from "@/lib/search";
import { GROUP_ORDER, GROUP_TEXT, groupOf, type Group } from "@/lib/truth";

type ClaimRow = {
  key: string;
  verdict: string;
  platform: string | null; // shown when the claims come from several listings
  claim: ReactNode;
  evidence: string;
  evidenceProvenance: Claims["distances"][number]["evidence_provenance"];
  radiusAssumed: boolean;
};

function ClaimItem({ row, now }: { row: ClaimRow; now: Date }) {
  return (
    <li className="grid gap-2 p-4 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <div className="flex flex-wrap items-start gap-1.5">
        <VerdictBadge verdict={row.verdict} />
      </div>
      <div className="min-w-0 text-sm">
        <p className="font-medium text-pretty">
          {row.platform ? <span className="me-1.5 text-fg-muted">{row.platform}:</span> : null}
          {row.claim}
        </p>
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

function rowsOf(listing: Listing, claims: Claims, now: Date, idPrefix: string, named: boolean) {
  const platform = named ? listing.platform_name : null;
  return [
    ...claims.distances.map((c, index) => ({
      key: `${idPrefix}d${index}`,
      verdict: c.verdict,
      platform,
      claim: (
        <Sourced
          id={`${idPrefix}claim-d${index}`}
          label="ادعای آگهی"
          provenance={c.provenance}
          sourceName={listing.platform_name}
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
      platform,
      claim: (
        <>
          {featureLabel(c.feature, c.span, c.polarity)}
          <Sourced
            id={`${idPrefix}claim-f${index}`}
            label="ادعای آگهی"
            provenance={c.provenance}
            sourceName={listing.platform_name}
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
  ];
}

const GROUP_HINT: Partial<Record<Group, string>> = {
  not_verified: "شاهد کافی نداریم؛ یعنی نمی‌دانیم، نه اینکه ادعا نادرست است.",
  map_disagrees: "حتی در خوش‌بینانه‌ترین حالت، فاصله بیش از ادعاست.",
};

/**
 * Claims grouped as «تأیید شد» / «تأیید نشد» / «با نقشه نمی‌خواند» (M12 2.1), each beside its
 * evidence; claims we have no evidence type for are folded away. The blur note is said once per
 * group, not under every claim. No score bar: a truth check is not an exam.
 */
export function ClaimGroups({
  sources,
  now,
}: {
  sources: { listing: Listing; claims: Claims | null; idPrefix: string }[];
  now: Date;
}) {
  const named = sources.length > 1;
  const rows: ClaimRow[] = sources.flatMap(({ listing, claims, idPrefix }) =>
    claims ? rowsOf(listing, claims, now, idPrefix, named) : [],
  );
  if (rows.length === 0) {
    return <p className="text-sm text-fg-muted">آگهی‌ها ادعایی نکرده‌اند که بشود سنجید.</p>;
  }
  return (
    <div className="space-y-4" data-truth-groups="">
      {GROUP_ORDER.map((group) => {
        const items = rows.filter((r) => groupOf(r.verdict) === group);
        if (items.length === 0) return null;
        const blurred = items.some((r) => r.radiusAssumed);
        const list = (
          <ul className="divide-y divide-line border-t border-line">
            {items.map((row) => (
              <ClaimItem key={row.key} row={row} now={now} />
            ))}
          </ul>
        );
        const note = (
          <>
            {GROUP_HINT[group] ? <span>{GROUP_HINT[group]} </span> : null}
            {blurred ? (
              <span>جای دقیق بعضی آگهی‌ها اعلام نشده؛ تا ۵۰۰ متر خطا فرض شده.</span>
            ) : null}
          </>
        );
        if (group === "not_checked") {
          return (
            <details
              key={group}
              data-group={group}
              className="group rounded-card border border-line bg-surface"
            >
              <summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 rounded-card p-4 text-sm text-fg-muted hover:text-fg [&::-webkit-details-marker]:hidden">
                {GROUP_TEXT[group]}: برای این مقصدها داده‌ی نقشه نداریم ({faNum(items.length)})
                <ChevronDown
                  aria-hidden="true"
                  className="size-4 transition-transform group-open:rotate-180"
                />
              </summary>
              {list}
            </details>
          );
        }
        return (
          <section
            key={group}
            data-group={group}
            aria-label={GROUP_TEXT[group]}
            className="rounded-card border border-line bg-surface"
          >
            <header className="px-4 py-3">
              <h3
                className={cn(
                  "font-semibold",
                  group === "verified" && "text-verified",
                  group === "map_disagrees" && "text-contradicted",
                )}
              >
                {GROUP_TEXT[group]}{" "}
                <span className="font-normal text-fg-muted">({faNum(items.length)})</span>
              </h3>
              {GROUP_HINT[group] || blurred ? (
                <p className="mt-0.5 text-xs text-fg-muted">{note}</p>
              ) : null}
            </header>
            {list}
          </section>
        );
      })}
    </div>
  );
}

/** The listing page's truth check (one listing). */
export function ClaimsSection({
  listing,
  claims,
  now,
}: {
  listing: Listing;
  claims: Claims | null;
  now: Date;
}) {
  if (!claims || claims.distances.length + claims.features.length === 0) return null;
  return (
    <Section
      id="claims"
      title="راستی‌آزمایی ادعاها"
      description={`ادعاهای خود آگهی در ${listing.platform_name}، هر کدام کنار شاهدش.`}
    >
      <ClaimGroups sources={[{ listing, claims, idPrefix: "" }]} now={now} />
    </Section>
  );
}
