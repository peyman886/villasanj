"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { List, Map as MapIcon, Search, X } from "lucide-react";
import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { OSM_RASTER, circleRing, loadMaplibre, localStyle } from "@/components/listing-map";
import { cn } from "@/lib/cn";
import { smoothScroll } from "@/lib/motion";
import { useTheme } from "@/lib/theme";

export type Pin = {
  id: string; // the result's listing id (the card carries it as data-result)
  label: string; // «۸٫۵»: the cheaper platform's own lower bound, in millions of toman
  title: string;
  lat: number;
  lon: number;
  radiusM: number; // the published blur radius (or the assumed one)
  // The phone preview card (the list is under the map there).
  price: string; // «از ۸٫۵ میلیون تومان»
  facts: string; // «۳ خوابه ∙ تا ۸ مهمان»
  photo: string | null;
  href: string;
};

const ASSUMED_RADIUS_M = 500;
const CIRCLE = "active-area";
const MAP_LEGEND = "قیمت‌ها به میلیون تومان";

/** Pin looks, as classes on the pill inside MapLibre's marker element (see makePin). */
const PILL =
  "relative block rounded-full border px-2.5 py-1 text-[0.8125rem] leading-none font-bold whitespace-nowrap tabular-nums shadow-raised transition-[scale,background-color,color,border-color] duration-150 ease-out " +
  "border-line-strong bg-surface text-fg hover:scale-110 " +
  "group-data-[active]:scale-110 group-data-[active]:border-brand-600 group-data-[active]:text-brand-900 " +
  "group-data-[selected]:scale-110 group-data-[selected]:border-accent-solid group-data-[selected]:bg-accent-solid group-data-[selected]:text-white " +
  "after:absolute after:top-full after:left-1/2 after:-ml-[5px] after:size-2.5 after:-translate-y-[5px] after:rotate-45 after:border-r after:border-b after:border-inherit after:bg-inherit after:content-['']";

/**
 * Results on the right, a sticky map on the left (RTL). Two kinds of link between them:
 * - preview (hover or focus): a card lights its pin and draws the area the villa can be in; a
 *   hovered pin outlines its card. It follows the pointer and clears when it leaves.
 * - selection (a click or tap on a pin): it stays until another pin, the map's background or
 *   Escape. On a wide screen the list scrolls to the selected card; on a phone a preview card
 *   opens over the map, with the villa's link and «نمایش در فهرست».
 * The map never moves on its own: hovering, selecting and switching the theme keep its camera.
 * Pins sit on the point the platform published, never anywhere more precise. Everything on the
 * map is also in the list.
 */
export function SearchSplit({
  pins: pinsProp,
  basemap,
  children,
}: {
  pins: Pin[];
  basemap: string | null;
  children: ReactNode;
}) {
  // A server re-render sends an equal list as a new array; the map must not rebuild for it.
  const pinsKey = pinsProp.map((p) => `${p.id}:${p.label}`).join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed on the content, not the array
  const pins = useMemo(() => pinsProp, [pinsKey]);
  const [active, setActive] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useRef<HTMLDivElement>(null);

  const fromCard = useCallback((target: EventTarget | null) => {
    const card = (target as HTMLElement | null)?.closest<HTMLElement>("[data-result]");
    setActive(card?.dataset.result ?? null);
  }, []);

  useEffect(() => {
    for (const card of list.current?.querySelectorAll<HTMLElement>("[data-result]") ?? []) {
      card.toggleAttribute("data-active", card.dataset.result === active);
      card.toggleAttribute("data-selected", card.dataset.result === selected);
    }
  }, [active, selected, pinsKey]);

  // «جستجو در همین محدوده»: the map's bounds become the «محدوده‌ی نقشه» chip (M12 3.2).
  const [mapOpen, setMapOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const searchArea = useCallback(
    (bounds: [number, number, number, number]) => {
      const next = new URLSearchParams(params.toString());
      next.set("area", bounds.map((x) => x.toFixed(4)).join(","));
      setMapOpen(false);
      setSelected(null);
      router.push(`${pathname}?${next}`, { scroll: false });
    },
    [params, pathname, router],
  );

  const showInList = useCallback((id: string) => {
    setMapOpen(false);
    // After the overlay closes, so the list is the scrolling surface again.
    requestAnimationFrame(() =>
      document
        .querySelector(`[data-result="${CSS.escape(id)}"]`)
        ?.scrollIntoView({ behavior: smoothScroll(), block: "center" }),
    );
  }, []);

  const select = useCallback(
    (id: string | null) => {
      setSelected(id);
      if (!id || mapOpen) return; // phones: the preview card shows it
      document
        .querySelector(`[data-result="${CSS.escape(id)}"]`)
        ?.scrollIntoView({ behavior: smoothScroll(), block: "center" });
    },
    [mapOpen],
  );

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  // Phones: the list is the page; a floating «نقشه» button opens the map over it and «فهرست»
  // closes it. The list stays mounted underneath, so its scroll position and filters remain.
  useEffect(() => {
    if (!mapOpen) return;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [mapOpen]);

  const preview = mapOpen ? pins.find((p) => p.id === selected) : undefined;

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-6">
      <div
        ref={list}
        className="min-w-0"
        onPointerOver={(e) => fromCard(e.target)}
        onPointerLeave={() => setActive(null)}
        onFocus={(e) => fromCard(e.target)}
      >
        {children}
      </div>
      <div className="hidden lg:block">
        <div className="sticky top-20 h-[calc(100dvh-6rem)]">
          {mapOpen ? null : (
            <SearchMap
              pins={pins}
              basemap={basemap}
              active={active}
              selected={selected}
              onActive={setActive}
              onSelect={select}
              onSearchArea={searchArea}
            />
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={() => setMapOpen(true)}
        data-map-button=""
        className="focus-ring fixed bottom-[max(1.25rem,env(safe-area-inset-bottom))] left-1/2 z-30 inline-flex h-12 -translate-x-1/2 items-center gap-2 rounded-full bg-fg px-6 font-semibold text-surface shadow-overlay active:scale-[0.98] lg:hidden"
      >
        <MapIcon aria-hidden="true" className="size-5" />
        نقشه
      </button>
      {mapOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="نقشه‌ی نتایج"
          className="fixed inset-0 z-40 bg-surface lg:hidden"
        >
          <SearchMap
            pins={pins}
            basemap={basemap}
            active={active}
            selected={selected}
            onActive={setActive}
            onSelect={select}
            onSearchArea={searchArea}
          />
          {preview ? (
            <PinPreview
              pin={preview}
              onClose={() => setSelected(null)}
              onShowInList={() => showInList(preview.id)}
            />
          ) : (
            <button
              type="button"
              autoFocus
              onClick={() => setMapOpen(false)}
              data-list-button=""
              className="focus-ring fixed bottom-[max(1.25rem,env(safe-area-inset-bottom))] left-1/2 z-50 inline-flex h-12 -translate-x-1/2 items-center gap-2 rounded-full bg-fg px-6 font-semibold text-surface shadow-overlay active:scale-[0.98]"
            >
              <List aria-hidden="true" className="size-5" />
              فهرست
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Phones: the tapped pin's villa, over the bottom of the map. */
function PinPreview({
  pin,
  onClose,
  onShowInList,
}: {
  pin: Pin;
  onClose: () => void;
  onShowInList: () => void;
}) {
  return (
    <div
      data-pin-preview=""
      className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-50 animate-fade-in overflow-hidden rounded-card border border-line bg-surface shadow-overlay"
    >
      <div className="flex gap-3 p-2">
        <div className="relative aspect-square w-24 shrink-0 overflow-hidden rounded-control bg-sunken">
          {pin.photo ? (
            // eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server
            <img
              src={pin.photo}
              alt=""
              referrerPolicy="no-referrer"
              className="size-full object-cover"
            />
          ) : null}
        </div>
        <div className="min-w-0 flex-1 py-0.5">
          <Link
            href={pin.href}
            className="focus-ring line-clamp-1 rounded-sm font-bold underline-offset-4 hover:underline"
          >
            {pin.title}
          </Link>
          <p className="truncate text-xs text-fg-muted tabular-nums">{pin.facts}</p>
          <p className="mt-1.5 font-bold tabular-nums">{pin.price}</p>
          <button
            type="button"
            onClick={onShowInList}
            className="focus-ring mt-0.5 rounded-sm text-sm font-medium text-accent"
          >
            نمایش در فهرست
          </button>
        </div>
        <button
          type="button"
          autoFocus
          onClick={onClose}
          aria-label="بستن"
          className="focus-ring grid size-9 shrink-0 place-items-center rounded-full text-fg-muted hover:bg-sunken"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      </div>
    </div>
  );
}

function makePin(p: Pin): HTMLElement {
  // MapLibre positions this element with `transform` on every frame: it must not transition.
  const element = document.createElement("div");
  // The pin being looked at sits above its neighbours (pins overlap along the coast).
  element.className = "group cursor-pointer data-[active]:z-10 data-[selected]:z-20";
  element.dataset.pin = p.id;
  element.title = p.title;
  const pill = document.createElement("span");
  pill.className = PILL;
  pill.textContent = p.label;
  element.append(pill);
  return element;
}

function SearchMap({
  pins,
  basemap,
  active,
  selected,
  onActive,
  onSelect,
  onSearchArea,
}: {
  pins: Pin[];
  basemap: string | null;
  active: string | null;
  selected: string | null;
  onActive: (id: string | null) => void;
  onSelect: (id: string | null) => void;
  onSearchArea: (bounds: [number, number, number, number]) => void;
}) {
  const theme = useTheme();
  const [moved, setMoved] = useState(false);
  // Latest callbacks for listeners attached once per map.
  const handlers = useRef({ onActive, onSelect });
  useEffect(() => {
    handlers.current = { onActive, onSelect };
  }, [onActive, onSelect]);
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef(new Map<string, { marker: Marker; element: HTMLElement }>());
  const [ready, setReady] = useState(false);
  const themeAtBuild = useRef(theme);

  useEffect(() => {
    let removed = false;
    const owned = markers.current;
    void loadMaplibre(basemap).then((maplibre) => {
      if (removed || !container.current || pins.length === 0) return;
      const bounds = new maplibre.LngLatBounds();
      for (const p of pins) bounds.extend([p.lon, p.lat]);
      const instance = new maplibre.Map({
        container: container.current,
        style: basemap
          ? localStyle(window.location.origin, basemap, themeAtBuild.current)
          : OSM_RASTER,
        bounds,
        fitBoundsOptions: { padding: 64, maxZoom: 13 },
        attributionControl: { compact: false },
        dragRotate: false,
        pitchWithRotate: false,
      });
      instance.touchZoomRotate.disableRotation();
      instance.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-left");
      map.current = instance;
      for (const p of pins) {
        const element = makePin(p);
        element.addEventListener("pointerenter", () => handlers.current.onActive(p.id));
        element.addEventListener("pointerleave", () => handlers.current.onActive(null));
        element.addEventListener("click", (event) => {
          event.stopPropagation(); // not a click on the map's background
          handlers.current.onSelect(p.id);
        });
        const marker = new maplibre.Marker({ element, anchor: "bottom", offset: [0, -6] })
          .setLngLat([p.lon, p.lat])
          .addTo(instance);
        owned.set(p.id, { marker, element });
      }
      // A tap on a pin reaches the map too (MapLibre builds clicks from pointer events).
      instance.on("click", (event: { originalEvent: Event }) => {
        const target = event.originalEvent.target as Element | null;
        if (!target?.closest("[data-pin]")) handlers.current.onSelect(null);
      });
      // Only a move the user made offers «جستجو در همین محدوده» (not the initial fit).
      instance.on("moveend", (event: { originalEvent?: unknown }) => {
        if (event.originalEvent) setMoved(true);
      });
      // Runs for the first style and again after a theme switch replaces it.
      instance.on("style.load", () => {
        if (instance.getSource(CIRCLE)) return;
        instance.addSource(CIRCLE, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        instance.addLayer({
          id: `${CIRCLE}-fill`,
          type: "fill",
          source: CIRCLE,
          paint: { "fill-color": "#147a72", "fill-opacity": 0.14 },
        });
        instance.addLayer({
          id: `${CIRCLE}-line`,
          type: "line",
          source: CIRCLE,
          paint: { "line-color": "#0d5b56", "line-width": 1.5 },
        });
        setReady(false);
        requestAnimationFrame(() => setReady(true));
      });
    });
    return () => {
      removed = true;
      for (const { marker } of owned.values()) marker.remove();
      owned.clear();
      map.current?.remove();
      map.current = null;
      setReady(false);
    };
  }, [pins, basemap]);

  // A theme switch swaps the style in place: the camera and the markers stay.
  useEffect(() => {
    if (themeAtBuild.current === theme) return;
    themeAtBuild.current = theme;
    if (basemap) map.current?.setStyle(localStyle(window.location.origin, basemap, theme));
  }, [theme, basemap]);

  useEffect(() => {
    for (const [id, { element }] of markers.current) {
      const isActive = id === active;
      const isSelected = id === selected;
      element.toggleAttribute("data-active", isActive);
      element.toggleAttribute("data-selected", isSelected);
    }
    const instance = map.current;
    if (!instance || !ready) return;
    const pin = pins.find((p) => p.id === (active ?? selected));
    instance.getSource<GeoJSONSource>(CIRCLE)?.setData({
      type: "FeatureCollection",
      features: pin
        ? [
            {
              type: "Feature",
              properties: {},
              geometry: {
                type: "Polygon",
                coordinates: [circleRing(pin.lat, pin.lon, pin.radiusM || ASSUMED_RADIUS_M)],
              },
            },
          ]
        : [],
    });
  }, [active, selected, pins, ready]);

  const searchHere = () => {
    const b = map.current?.getBounds();
    if (!b) return;
    setMoved(false);
    onSearchArea([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
  };

  return (
    <div className="relative size-full">
      <div
        ref={container}
        role="region"
        aria-label="نقشه‌ی نتایج؛ همه‌ی نتایج در فهرست هم هستند"
        data-search-map=""
        className="size-full overflow-hidden bg-sunken lg:rounded-card lg:border lg:border-line"
      />
      <p
        aria-hidden="true"
        className="pointer-events-none absolute start-3 top-3 z-10 rounded-full bg-surface/90 px-3 py-1 text-xs text-fg-muted shadow-raised backdrop-blur-sm"
      >
        {MAP_LEGEND}
      </p>
      {moved ? (
        <button
          type="button"
          onClick={searchHere}
          data-search-area=""
          className={cn(
            "focus-ring absolute top-14 left-1/2 z-10 inline-flex h-10 -translate-x-1/2 items-center gap-2 rounded-full bg-accent-solid px-4 text-sm font-semibold text-white shadow-float animate-fade-in hover:bg-accent-solid-hover active:scale-[0.98] lg:top-3",
          )}
        >
          <Search aria-hidden="true" className="size-4" />
          جستجو در همین محدوده
        </button>
      ) : null}
    </div>
  );
}
