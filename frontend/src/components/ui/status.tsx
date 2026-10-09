import {
  CircleCheck,
  CircleCheckBig,
  CircleDashed,
  CircleHelp,
  CircleSlash,
  CircleX,
  Clock,
  Hourglass,
  UserCheck,
} from "lucide-react";

import { Badge, type Tone } from "@/components/ui/badge";
import type { Locale } from "@/lib/i18n";
import { CLAIM_VERDICT_TEXT } from "@/lib/listing";

export type Status =
  | "done"
  | "waived"
  | "partial"
  | "provisional"
  | "blocked"
  | "deferred"
  | "owner_review"
  | "not_met";

export const STATUS: Record<
  Status,
  { text: string; en: string; tone: Tone; Icon: typeof CircleCheck }
> = {
  done: { text: "انجام شد", en: "Done", tone: "verified", Icon: CircleCheck },
  // Closed by the owner's decision: not achieved as written, and no longer required (said so).
  waived: {
    text: "بسته به تصمیم مالک",
    en: "Closed by the owner",
    tone: "muted",
    Icon: CircleCheckBig,
  },
  partial: { text: "بخشی انجام شد", en: "Partly done", tone: "info", Icon: CircleDashed },
  provisional: { text: "موقت", en: "Provisional", tone: "caution", Icon: Hourglass },
  blocked: { text: "مسدود", en: "Blocked", tone: "danger", Icon: CircleSlash },
  deferred: { text: "به تعویق افتاده", en: "Deferred", tone: "muted", Icon: Clock },
  owner_review: {
    text: "منتظر بازبینی مالک",
    en: "Awaiting the owner's review",
    tone: "info",
    Icon: UserCheck,
  },
  not_met: { text: "پاس نشده", en: "Not met", tone: "danger", Icon: CircleX },
};

/** Milestone or criterion status: icon + words, never colour alone. */
export function StatusBadge({ status, locale = "fa" }: { status: Status; locale?: Locale }) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone} icon={<s.Icon aria-hidden="true" className="size-3.5" />}>
      {locale === "en" ? s.en : s.text}
    </Badge>
  );
}

export type Verdict =
  | "supported"
  | "consistent"
  | "shared"
  | "not_confirmed"
  | "contradicted"
  | "inconsistent"
  | "not_checked";

const VERDICT: Record<Verdict, { tone: Tone; Icon: typeof CircleCheck }> = {
  supported: { tone: "verified", Icon: CircleCheck },
  consistent: { tone: "brand", Icon: CircleCheck },
  shared: { tone: "info", Icon: CircleHelp },
  not_confirmed: { tone: "neutral", Icon: CircleHelp },
  contradicted: { tone: "danger", Icon: CircleX },
  inconsistent: { tone: "caution", Icon: CircleHelp },
  not_checked: { tone: "muted", Icon: CircleDashed },
};

/** A truth-check verdict; «تأیید نشد» is the default tone, never an accusation (rule 5). */
const VERDICT_EN: Record<Verdict, string> = {
  supported: "Confirmed",
  consistent: "Matches the amenity list",
  shared: "Shared amenity",
  not_confirmed: "Not confirmed",
  contradicted: "Disagrees with the map",
  inconsistent: "Disagrees with the amenity list",
  not_checked: "Not checked",
};

export function VerdictBadge({ verdict, locale = "fa" }: { verdict: string; locale?: Locale }) {
  const v = VERDICT[verdict as Verdict] ?? VERDICT.not_checked;
  const text =
    locale === "en"
      ? (VERDICT_EN[verdict as Verdict] ?? verdict)
      : (CLAIM_VERDICT_TEXT[verdict] ?? verdict);
  return (
    <Badge tone={v.tone} icon={<v.Icon aria-hidden="true" className="size-3.5" />}>
      {text}
    </Badge>
  );
}

export const VERDICT_BAR: Record<string, string> = {
  supported: "bg-brand-600",
  consistent: "bg-brand-300",
  shared: "bg-sky-400",
  not_confirmed: "bg-sand-400",
  contradicted: "bg-rose-500",
  inconsistent: "bg-amber-400",
  not_checked: "bg-sand-200",
};
