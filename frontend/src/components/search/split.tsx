"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { OSM_RASTER, circleRing, loadMaplibre, localStyle } from "@/components/listing-map";
import { cn } from "@/lib/cn";

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
          <SearchMap pins={pins} basemap={basemap} active={active} onActive={setActive} />
        </div>
      </div>
    </div>
  );
}

function SearchMap({
  pins,
  basemap,
  active,
  onActive,
}: {
  pins: Pin[];
  basemap: string | null;
  active: string | null;
  onActive: (id: string | null) => void;
}) {
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
          "pointer-events-auto cursor-pointer rounded-full border border-line-strong bg-surface px-2 py-0.5 text-xs font-bold text-fg shadow-raised tabular-nums transition-transform duration-100 data-[active]:z-10 data-[active]:scale-110 data-[active]:border-brand-800 data-[active]:bg-brand-800 data-[active]:text-white";
        element.addEventListener("pointerenter", () => onActive(p.id));
        element.addEventListener("pointerleave", () => onActive(null));
        element.addEventListener("click", () => {
          document
            .querySelector(`[data-result="${CSS.escape(p.id)}"]`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" });
        });
        const marker = new maplibre.Marker({ element, anchor: "bottom" })
          .setLngLat([p.lon, p.lat])
          .addTo(instance);
        owned.set(p.id, { marker, element });
      }
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

  return (
    <div
      ref={container}
      role="region"
      aria-label="نقشه‌ی نتایج؛ همه‌ی نتایج در فهرست هم هستند"
      data-search-map=""
      className={cn("size-full overflow-hidden rounded-card border border-line bg-sunken")}
    />
  );
}
