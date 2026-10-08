"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef } from "react";

import { OSM_RASTER, loadMaplibre, localStyle } from "@/components/listing-map";

/**
 * The hero visual (decisions.md D8.2): the Ramsar–Tonekabon coast from the offline OpenStreetMap
 * basemap, with the approximate points of the villas shown below. No stock or listing photo.
 * Decorative and still: no drag, zoom or focus; the attribution stays visible (ODbL).
 */
export function HeroMap({
  basemap,
  points,
}: {
  basemap: string | null;
  points: { lat: number; lon: number }[];
}) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let removed = false;
    let map: { remove: () => void } | null = null;
    void loadMaplibre(basemap).then(({ Map }) => {
      if (removed || !container.current) return;
      const instance = new Map({
        container: container.current,
        style: basemap ? localStyle(window.location.origin, basemap) : OSM_RASTER,
        center: [50.78, 36.85],
        zoom: 9.6,
        interactive: false,
        attributionControl: { compact: false },
      });
      map = instance;
      instance.on("load", () => {
        instance.addSource("villas", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: points.map((p) => ({
              type: "Feature",
              properties: {},
              geometry: { type: "Point", coordinates: [p.lon, p.lat] },
            })),
          },
        });
        instance.addLayer({
          id: "villas",
          type: "circle",
          source: "villas",
          paint: {
            "circle-radius": 6,
            "circle-color": "#0d5b56",
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
          },
        });
      });
    });
    return () => {
      removed = true;
      map?.remove();
    };
  }, [basemap, points]);
  return (
    <div
      ref={container}
      aria-hidden="true"
      className="size-full overflow-hidden rounded-modal border border-line bg-sunken"
    />
  );
}
