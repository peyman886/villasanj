"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { List, Map as MapIcon, Search } from "lucide-react";
import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { OSM_RASTER, circleRing, loadMaplibre, localStyle } from "@/components/listing-map";
import { cn } from "@/lib/cn";
import { smoothScroll } from "@/lib/motion";

export type Pin = {
  id: string; // the result's listing id (the card carries it as data-result)
  label: string; // «۸٫۵م»: the cheaper platform's own lower bound
  title: string;
  lat: number;
  lon: number;
  radiusM: number; // the published blur radius (or the assumed one)
};

const ASSUMED_RADIUS_M = 500;
const CIRCLE = "active-area";

/**
 * Results on the right, a sticky map on the left (RTL). Hovering or focusing card n highlights
 * pin n and draws its approximate area; hovering pin n outlines card n. Pins sit on the point the
 * platform published, never anywhere more precise, and the circle shows how far the villa can be
 * from it. The map is a visual aid: everything on it is also in the list.
 */
export function SearchSplit({
  pins,
  basemap,
  children,
}: {
  pins: Pin[];
  basemap: string | null;
  children: ReactNode;
}) {
  const [active, setActive] = useState<string | null>(null);
  const list = useRef<HTMLDivElement>(null);

  const fromCard = useCallback((target: EventTarget | null) => {
    const card = (target as HTMLElement | null)?.closest<HTMLElement>("[data-result]");
    setActive(card?.dataset.result ?? null);
  }, []);

  useEffect(() => {
    for (const card of list.current?.querySelectorAll<HTMLElement>("[data-result]") ?? []) {
      card.toggleAttribute("data-active", card.dataset.result === active);
    }
  }, [active]);

  // «جست‌وجو در همین محدوده»: the map's bounds become the «محدوده‌ی نقشه» chip (M12 3.2).
  const [mapOpen, setMapOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const searchArea = useCallback(
    (bounds: [number, number, number, number]) => {
      const next = new URLSearchParams(params.toString());
      next.set("area", bounds.map((x) => x.toFixed(4)).join(","));
      setMapOpen(false);
      router.push(`${pathname}?${next}`, { scroll: false });
    },
    [params, pathname, router],
  );

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

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,11fr)_minmax(0,9fr)] lg:gap-6">
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
          <SearchMap
            pins={pins}
            basemap={basemap}
            active={active}
            onActive={setActive}
            onSearchArea={searchArea}
          />
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
            onActive={setActive}
            onSearchArea={searchArea}
            onPin={() => setMapOpen(false)}
          />
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
        </div>
      ) : null}
    </div>
  );
}

function SearchMap({
  pins,
  basemap,
  active,
  onActive,
  onSearchArea,
  onPin,
}: {
  pins: Pin[];
  basemap: string | null;
  active: string | null;
  onActive: (id: string | null) => void;
  onSearchArea: (bounds: [number, number, number, number]) => void;
  onPin?: () => void; // phones: a tapped pin closes the map and shows its card
}) {
  const [moved, setMoved] = useState(false);
  const pinTapped = useRef(onPin);
  useEffect(() => {
    pinTapped.current = onPin;
  }, [onPin]);
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef(new Map<string, { marker: Marker; element: HTMLElement }>());
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let removed = false;
    const owned = markers.current;
    void loadMaplibre(basemap).then((maplibre) => {
      if (removed || !container.current || pins.length === 0) return;
      const bounds = new maplibre.LngLatBounds();
      for (const p of pins) bounds.extend([p.lon, p.lat]);
      const instance = new maplibre.Map({
        container: container.current,
        style: basemap ? localStyle(window.location.origin, basemap) : OSM_RASTER,
        bounds,
        fitBoundsOptions: { padding: 56, maxZoom: 13 },
        attributionControl: { compact: false },
        dragRotate: false,
        pitchWithRotate: false,
      });
      instance.touchZoomRotate.disableRotation();
      instance.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-left");
      map.current = instance;
      for (const p of pins) {
        const element = document.createElement("div");
        element.dataset.pin = p.id;
        element.textContent = p.label;
        element.title = p.title;
        element.className =
          "pointer-events-auto cursor-pointer rounded-full border border-line-strong bg-surface px-2 py-0.5 text-xs font-bold text-fg shadow-raised tabular-nums transition-transform duration-100 data-[active]:z-10 data-[active]:scale-110 data-[active]:border-accent-solid data-[active]:bg-accent-solid data-[active]:text-white";
        element.addEventListener("pointerenter", () => onActive(p.id));
        element.addEventListener("pointerleave", () => onActive(null));
        element.addEventListener("click", () => {
          pinTapped.current?.();
          document
            .querySelector(`[data-result="${CSS.escape(p.id)}"]`)
            ?.scrollIntoView({ behavior: smoothScroll(), block: "center" });
        });
        const marker = new maplibre.Marker({ element, anchor: "bottom" })
          .setLngLat([p.lon, p.lat])
          .addTo(instance);
        owned.set(p.id, { marker, element });
      }
      // Only a move the user made offers «جست‌وجو در همین محدوده» (not the initial fit).
      instance.on("moveend", (event: { originalEvent?: unknown }) => {
        if (event.originalEvent) setMoved(true);
      });
      instance.on("load", () => {
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
        setReady(true);
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
  }, [pins, basemap, onActive]);

  useEffect(() => {
    for (const [id, { element }] of markers.current) {
      element.toggleAttribute("data-active", id === active);
    }
    const instance = map.current;
    if (!instance || !ready) return;
    const pin = pins.find((p) => p.id === active);
    const source = instance.getSource<GeoJSONSource>(CIRCLE);
    source?.setData({
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
  }, [active, pins, ready]);

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
        className={cn(
          "size-full overflow-hidden bg-sunken lg:rounded-card lg:border lg:border-line",
        )}
      />
      {moved ? (
        <button
          type="button"
          onClick={searchHere}
          data-search-area=""
          className="focus-ring absolute top-3 left-1/2 z-10 inline-flex h-10 -translate-x-1/2 items-center gap-2 rounded-full bg-surface px-4 text-sm font-semibold shadow-float animate-fade-in active:scale-[0.98]"
        >
          <Search aria-hidden="true" className="size-4" />
          جست‌وجو در همین محدوده
        </button>
      ) : null}
    </div>
  );
}
