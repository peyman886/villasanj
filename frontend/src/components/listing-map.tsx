"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef } from "react";

import { faNumber } from "@/lib/listing";

/**
 * Where the listing can be: its published pin and blur circle on OpenStreetMap (ROADMAP M7).
 * Static on purpose (no drag or zoom): it gives context, never steals scroll or keyboard focus.
 * The basemap is OSM's raster tiles with attribution (ADR-0003 decision 6); the offline demo
 * (M11) swaps in a local style through NEXT_PUBLIC_MAP_STYLE_URL.
 */
const OSM_RASTER = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© مشارکت‌کنندگان OpenStreetMap",
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
};

const EARTH_RADIUS_M = 6_371_008.8;
const WORKER_URL = "/maplibre/maplibre-gl-worker.mjs"; // copied by scripts/copy-maplibre-worker.mjs

/** A ring of ``steps`` points ``radiusM`` around the pin, as [lon, lat] pairs. */
export function circleRing(lat: number, lon: number, radiusM: number, steps = 64): number[][] {
  const angular = radiusM / EARTH_RADIUS_M;
  const lat1 = (lat * Math.PI) / 180;
  const lon1 = (lon * Math.PI) / 180;
  const ring: number[][] = [];
  for (let i = 0; i <= steps; i += 1) {
    const bearing = (2 * Math.PI * i) / steps;
    const lat2 = Math.asin(
      Math.sin(lat1) * Math.cos(angular) + Math.cos(lat1) * Math.sin(angular) * Math.cos(bearing),
    );
    const lon2 =
      lon1 +
      Math.atan2(
        Math.sin(bearing) * Math.sin(angular) * Math.cos(lat1),
        Math.cos(angular) - Math.sin(lat1) * Math.sin(lat2),
      );
    ring.push([(lon2 * 180) / Math.PI, (lat2 * 180) / Math.PI]);
  }
  return ring;
}

export function ListingMap({
  lat,
  lon,
  radiusM,
  assumed,
}: {
  lat: number;
  lon: number;
  radiusM: number;
  assumed: boolean; // the platform publishes no radius: the circle is our assumption
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let removed = false;
    let map: { remove: () => void } | null = null;
    void import("maplibre-gl").then(({ Map, setWorkerUrl }) => {
      if (removed || !container.current) return;
      setWorkerUrl(WORKER_URL);
      const instance = new Map({
        container: container.current,
        style: process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? OSM_RASTER,
        center: [lon, lat],
        zoom: radiusM > 600 ? 13.5 : 14.3,
        interactive: false,
        attributionControl: { compact: false },
      });
      map = instance;
      instance.on("load", () => {
        instance.addSource("blur", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "Polygon", coordinates: [circleRing(lat, lon, radiusM)] },
          },
        });
        instance.addSource("pin", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "Point", coordinates: [lon, lat] },
          },
        });
        instance.addLayer({
          id: "blur-fill",
          type: "fill",
          source: "blur",
          paint: { "fill-color": "#047857", "fill-opacity": 0.15 },
        });
        instance.addLayer({
          id: "blur-line",
          type: "line",
          source: "blur",
          paint: {
            "line-color": "#065f46",
            "line-width": 2,
            ...(assumed ? { "line-dasharray": [2, 2] } : {}),
          },
        });
        instance.addLayer({
          id: "pin",
          type: "circle",
          source: "pin",
          paint: {
            "circle-radius": 5,
            "circle-color": "#065f46",
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
  }, [lat, lon, radiusM, assumed]);

  return (
    <figure className="mt-6">
      <div
        ref={container}
        aria-hidden="true"
        className="h-64 w-full overflow-hidden rounded-lg border border-stone-200 bg-stone-100 sm:h-80"
      />
      <figcaption className="mt-2 text-xs text-pretty text-stone-600">
        نقطه‌ای که پلتفرم منتشر کرده و دایره‌ای به شعاع {faNumber(radiusM)} متر که ویلا در آن است
        {assumed ? " (پلتفرم شعاع را اعلام نکرده؛ این شعاع فرض ماست)" : ""}. جای دقیق ویلا را
        پلتفرم‌ها پنهان می‌کنند.
      </figcaption>
    </figure>
  );
}
