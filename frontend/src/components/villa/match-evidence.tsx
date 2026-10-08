import { Check, Minus, X } from "lucide-react";
import Link from "next/link";

import type { components } from "@/lib/api/schema";
import { cn } from "@/lib/cn";
import { distance, faNum } from "@/lib/numbers";
import { platformRank } from "@/lib/platforms";

export type MatchPair = components["schemas"]["MatchPairOut"];
type Member = { id: string; platform: string; platform_name: string; url: string };

/** The judge's cited evidence codes, in words (entity_resolution judge prompt). */
export const JUDGE_CODE_TEXT: Record<string, string> = {
  same_photos: "عکس‌های یکسان",
  same_interior: "فضای داخلی یکسان",
  same_exterior: "نمای بیرونی یکسان",
  same_view: "منظره‌ی یکسان",
  same_structure: "ساختمان یکسان",
  same_location: "موقعیت یکسان",
  shared_complex_photos: "عکس‌های مشترک مجتمع",
  different_photos: "عکس‌های متفاوت",
  different_interior: "فضای داخلی متفاوت",
  different_structure: "ساختمان متفاوت",
  different_location: "موقعیت متفاوت",
  insufficient_photos: "عکس کافی نبود",
};

const VERDICT_TEXT: Record<string, string> = {
  match: "همان ویلاست",
  non_match: "ویلای دیگری است",
  unsure: "مطمئن نبود",
};

type Line = { key: string; text: string };

/**
 * The non-photo evidence recorded for this pair, at most three lines. Each maps
 * to one stored field of the pair (the test checks the mapping); nothing is written that the
 * pipeline did not record (decisions.md D2).
 */
export function evidenceLines(pair: MatchPair): Line[] {
  const lines: Line[] = [];
  if (pair.distance_min_m !== null) {
    lines.push({
      key: "distance",
      text:
        pair.distance_min_m === 0
          ? "محدوده‌ی تقریبی دو آگهی روی نقشه روی هم می‌افتد"
          : `محدوده‌ی تقریبی دو آگهی دست‌کم ${distance(pair.distance_min_m, "lower")} از هم فاصله دارد`,
    });
  }
  const [a, b] = pair.bedrooms;
  if (a !== null && a !== undefined && b !== null && b !== undefined) {
    lines.push({
      key: "bedrooms",
      text: a === b ? `هر دو آگهی: ${faNum(a)} خوابه` : `تعداد خواب: ${faNum(a)} و ${faNum(b)}`,
    });
  }
  const [c, d] = pair.max_capacity;
  if (lines.length < 3 && c !== null && c !== undefined && d !== null && d !== undefined) {
    lines.push({ key: "capacity", text: `ظرفیت: ${faNum(c)} و ${faNum(d)} نفر` });
  }
  return lines.slice(0, 3);
}

type Step = { key: string; label: string; state: "yes" | "no" | "none"; detail: string };

/** Who decided: the rules, the language-model judge, a human label (only what is stored). */
export function decisionTrail(pair: MatchPair): Step[] {
  const judge = pair.judge;
  return [
    {
      key: "rules",
      label: "قواعد تطبیق",
      state: pair.rule_score === null ? "none" : pair.rules_match ? "yes" : "no",
      detail:
        pair.rule_score === null
          ? "این جفت امتیاز قاعده نگرفت"
          : pair.rules_match
            ? "امتیاز از آستانه‌ی تطبیق بالاتر است"
            : "امتیاز زیر آستانه‌ی تطبیق است",
    },
    {
      key: "judge",
      label: "داور مدل زبانی",
      state: !judge
        ? "none"
        : judge.verdict === "match"
          ? "yes"
          : judge.verdict === "non_match"
            ? "no"
            : "none",
      detail: judge
        ? `${VERDICT_TEXT[judge.verdict] ?? judge.verdict}${
            judge.evidence.length
              ? `: ${judge.evidence.map((code) => JUDGE_CODE_TEXT[code] ?? code).join("، ")}`
              : ""
          }`
        : "این جفت را ندید",
    },
    {
      key: "human",
      label: "برچسب انسانی",
      state: pair.human === "match" ? "yes" : pair.human === "non_match" ? "no" : "none",
      detail:
        pair.human === "match"
          ? "مالک پروژه تأیید کرد"
          : pair.human === "non_match"
            ? "مالک پروژه رد کرد"
            : pair.human === "unsure"
              ? "مالک پروژه مطمئن نبود"
              : "برچسب انسانی ندارد",
    },
  ];
}

const STEP_ICON = { yes: Check, no: X, none: Minus } as const;

/**
 * «چرا مطمئنیم این دو آگهی یک ویلاست؟» (M12 1.9): the shared photos side by side, two or three
 * recorded facts, and who decided. Opened from the header badge; the photo pairs slide together
 * when the section is the page's target (reduced motion: no movement).
 */
export function MatchEvidence({ pairs, members }: { pairs: MatchPair[]; members: Member[] }) {
  const byId = new Map(members.map((m) => [m.id, m]));
  return (
    <section id="match" aria-labelledby="match-title" className="scroll-mt-28 group/match">
      <h2 id="match-title" tabIndex={-1} className="focus-ring text-xl font-bold text-balance">
        چرا مطمئنیم این آگهی‌ها یک ویلاست؟
      </h2>
      {pairs.map((pair) => {
        const sides = [byId.get(pair.left), byId.get(pair.right)];
        const flip =
          platformRank(sides[0]?.platform ?? "") > platformRank(sides[1]?.platform ?? "");
        const [first, second] = flip ? [sides[1], sides[0]] : sides;
        const photos = pair.photo_pairs.map((p) =>
          flip
            ? { a: p.right_url, b: p.left_url, strong: p.strong }
            : { a: p.left_url, b: p.right_url, strong: p.strong },
        );
        const lines = evidenceLines(pair);
        const total = pair.strong_photo_matches + pair.weak_photo_matches;
        return (
          <div key={`${pair.left}|${pair.right}`} className="mt-4 space-y-5">
            {photos.length > 0 ? (
              <div>
                <p className="text-sm text-fg-muted">
                  {faNum(total)} عکس از {faNum(Math.min(...pair.photos_compared))} عکسِ مقایسه‌شده
                  در {first?.platform_name} و {second?.platform_name} یکی است:
                </p>
                <ul className="mt-3 grid gap-4 sm:grid-cols-2">
                  {photos.map((p, i) => (
                    <li
                      key={p.a}
                      data-match-pair=""
                      className="rounded-card border border-line bg-surface p-2"
                    >
                      <div className="grid grid-cols-2 gap-1.5">
                        {[
                          { url: p.a, name: first?.platform_name, side: "start" },
                          { url: p.b, name: second?.platform_name, side: "end" },
                        ].map((side) => (
                          <figure
                            key={side.url}
                            className={cn(
                              "relative aspect-[4/3] overflow-hidden rounded-control bg-sunken",
                              side.side === "start"
                                ? "group-target/match:animate-lock-start"
                                : "group-target/match:animate-lock-end",
                            )}
                            style={{ animationDelay: `${i * 90}ms` }}
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose */}
                            <img
                              src={side.url}
                              alt={`عکس در ${side.name}`}
                              loading="lazy"
                              decoding="async"
                              referrerPolicy="no-referrer"
                              className="size-full object-cover"
                            />
                            <figcaption className="absolute start-1.5 bottom-1.5 rounded-full bg-surface/95 px-2 text-xs font-medium">
                              {side.name}
                            </figcaption>
                          </figure>
                        ))}
                      </div>
                      <p className="mt-1.5 text-center text-xs text-fg-muted">
                        {p.strong ? "تقریباً همان عکس" : "عکس بسیار شبیه"}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-sm text-fg-muted">
                برای این دو آگهی عکس مشترکی ثبت نشده است؛ تطبیق بر پایه‌ی شواهد زیر است.
              </p>
            )}
            {lines.length ? (
              <ul className="space-y-1.5">
                {lines.map((line) => (
                  <li
                    key={line.key}
                    data-evidence={line.key}
                    className="flex items-center gap-2 text-sm"
                  >
                    <Check aria-hidden="true" className="size-4 text-verified" />
                    {line.text}
                  </li>
                ))}
              </ul>
            ) : null}
            <ol className="flex flex-wrap gap-2" aria-label="چه کسی تصمیم گرفت">
              {decisionTrail(pair).map((step) => {
                const Icon = STEP_ICON[step.state];
                return (
                  <li
                    key={step.key}
                    data-decision={step.key}
                    className="flex items-start gap-2 rounded-card border border-line bg-surface px-3 py-2 text-sm"
                  >
                    <Icon
                      aria-hidden="true"
                      className={cn(
                        "mt-1 size-4 shrink-0",
                        step.state === "yes" ? "text-verified" : "text-fg-subtle",
                      )}
                    />
                    <span>
                      <span className="font-semibold">{step.label}</span>
                      <span className="block text-xs text-fg-muted">{step.detail}</span>
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>
        );
      })}
      <p className="mt-4 text-sm text-fg-muted">
        آگهی‌ها:{" "}
        {members.map((m, i) => (
          <span key={m.id}>
            {i > 0 ? "، " : ""}
            <Link
              href={`/listings/${m.platform}/${m.id.split(":")[1]}`}
              className="focus-ring rounded-sm text-accent underline underline-offset-4"
            >
              {m.platform_name}
            </Link>
          </span>
        ))}
        {" · "}
        <Link
          href="/docs/entity-resolution"
          className="focus-ring rounded-sm text-accent underline underline-offset-4"
        >
          روش تطبیق
        </Link>
      </p>
    </section>
  );
}
