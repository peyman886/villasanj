import {
  CircleCheck,
  CircleDashed,
  CircleHelp,
  CircleSlash,
  CircleX,
  Clock,
  Hourglass,
  UserCheck,
} from "lucide-react";

import { Badge, type Tone } from "@/components/ui/badge";
import { CLAIM_VERDICT_TEXT } from "@/lib/listing";

export type Status =
  "done" | "partial" | "provisional" | "blocked" | "deferred" | "owner_review" | "not_met";

export const STATUS: Record<Status, { text: string; tone: Tone; Icon: typeof CircleCheck }> = {
  done: { text: "انجام شد", tone: "verified", Icon: CircleCheck },
  partial: { text: "بخشی انجام شد", tone: "info", Icon: CircleDashed },
  provisional: { text: "موقت", tone: "caution", Icon: Hourglass },
  blocked: { text: "مسدود", tone: "danger", Icon: CircleSlash },
  deferred: { text: "به تعویق افتاده", tone: "muted", Icon: Clock },
  owner_review: { text: "منتظر بازبینی مالک", tone: "info", Icon: UserCheck },
  not_met: { text: "پاس نشده", tone: "danger", Icon: CircleX },
};

/** Milestone or criterion status: icon + words, never colour alone. */
export function StatusBadge({ status }: { status: Status }) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone} icon={<s.Icon aria-hidden="true" className="size-3.5" />}>
      {s.text}
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
export function VerdictBadge({ verdict }: { verdict: string }) {
  const v = VERDICT[verdict as Verdict] ?? VERDICT.not_checked;
  return (
    <Badge tone={v.tone} icon={<v.Icon aria-hidden="true" className="size-3.5" />}>
      {CLAIM_VERDICT_TEXT[verdict] ?? verdict}
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
