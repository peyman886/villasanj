"use client";

import { Monitor, Smartphone, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import { t, type Locale } from "@/lib/i18n";
import { PHONE_SCREEN, VIEW_KEY } from "@/lib/theme";

type Kind = "hidden" | "phone" | "phone-desktop" | "wide";

function kindNow(): Kind {
  if (window.self !== window.top) return "hidden"; // inside the phone preview
  if (screen.width >= PHONE_SCREEN) return "wide";
  return document.documentElement.dataset.view === "desktop" ? "phone-desktop" : "phone";
}

/**
 * Switch between the phone and the web layout. On a phone it saves the choice and reloads (the
 * web version lays the page out at desktop width, like a browser's "desktop site"); on a wide
 * screen it shows the current page in a phone-sized frame, where the phone layout applies.
 */
export function ViewToggle({ locale = "fa", className }: { locale?: Locale; className?: string }) {
  const [kind, setKind] = useState<Kind>("hidden");
  const dialog = useRef<HTMLDialogElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => setKind(kindNow()), []);
  if (kind === "hidden") return null;

  const save = (view: "desktop" | "mobile") => {
    try {
      if (view === "desktop") localStorage.setItem(VIEW_KEY, "desktop");
      else localStorage.removeItem(VIEW_KEY);
    } catch {
      // storage blocked: nothing to remember
    }
    window.location.reload();
  };

  const button = (label: string, Icon: typeof Monitor, onClick: () => void) => (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      data-view-toggle=""
      className={cn(
        "focus-ring grid size-10 shrink-0 place-items-center rounded-control text-fg-muted transition-colors hover:bg-sunken hover:text-fg active:scale-[0.96]",
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-[1.125rem]" />
    </button>
  );

  if (kind === "phone")
    return button(t(locale, "نسخه‌ی وب", "Web version"), Monitor, () => save("desktop"));
  if (kind === "phone-desktop")
    return button(t(locale, "نسخه‌ی موبایل", "Mobile version"), Smartphone, () => save("mobile"));

  const close = () => {
    dialog.current?.close();
    setSrc(null);
  };
  return (
    <>
      {button(t(locale, "نمای موبایل", "Mobile view"), Smartphone, () => {
        setSrc(`${window.location.pathname}${window.location.search}`);
        dialog.current?.showModal();
      })}
      <dialog
        ref={dialog}
        aria-label={t(locale, "نمای موبایل", "Mobile view")}
        onClose={() => setSrc(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) close();
        }}
        className="m-auto overflow-visible bg-transparent p-0 backdrop:bg-scrim/60 open:animate-fade-in"
      >
        <div className="relative rounded-[2.75rem] border border-sand-700 bg-sand-950 p-3 shadow-overlay">
          {src ? (
            <iframe
              src={src}
              title={t(locale, "همین صفحه در عرض گوشی", "This page at phone width")}
              className="block h-[min(844px,calc(100dvh-6rem))] w-[390px] rounded-[2rem] bg-canvas"
            />
          ) : null}
          <button
            type="button"
            autoFocus
            onClick={close}
            aria-label={t(locale, "بستن نمای موبایل", "Close mobile view")}
            className="focus-ring absolute -top-3 -end-3 grid size-9 place-items-center rounded-full bg-surface text-fg shadow-float hover:bg-sunken"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
      </dialog>
    </>
  );
}
