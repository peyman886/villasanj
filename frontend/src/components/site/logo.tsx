import { cn } from "@/lib/cn";

/** The mark: a roof over a level line, a villa measured. Decorative; the name carries it. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn("size-8", className)}>
      <rect width="32" height="32" rx="9" className="fill-brand-700" />
      <path
        d="M8 15.5 16 9l8 6.5"
        fill="none"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M9.5 22.5h13" stroke="white" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="16" cy="18.25" r="1.9" className="fill-brand-200" />
    </svg>
  );
}
