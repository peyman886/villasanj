"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { layers, namedFlavor } from "@protomaps/basemaps";
import type { StyleSpecification } from "maplibre-gl";
import { useEffect, useRef } from "react";

import { faNumber } from "@/lib/listing";

/**
 * Where the listing can be: its published pin and blur circle on OpenStreetMap (ROADMAP M7).
 * Static on purpose (no drag or zoom): it gives context, never steals scroll or keyboard focus.
 * With a prepared local basemap (a Protomaps extract served by /basemap, ADR-0003 amendment) it
 * needs no network and labels places in Persian; otherwise it uses OSM's raster tiles with
 * attribution (ADR-0003 decision 6).
 */
export const OSM_RASTER = {
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

let pmtilesRegistered = false;

/** Load MapLibre with its worker and, for the local basemap, the pmtiles protocol (once). */
export async function loadMaplibre(basemap: string | null) {
  const [maplibre, pmtiles] = await Promise.all([import("maplibre-gl"), import("pmtiles")]);
  maplibre.setWorkerUrl(WORKER_URL);
  if (basemap && !pmtilesRegistered) {
    maplibre.addProtocol("pmtiles", new pmtiles.Protocol().tile);
    pmtilesRegistered = true;
  }
  return maplibre;
}

/** The local Protomaps style (absolute URLs: MapLibre fetches glyphs from its workers). */
export function localStyle(origin: string, pmtiles: string): StyleSpecification {
  return {
    version: 8,
    glyphs: `${origin}/basemap/fonts/{fontstack}/{range}.pbf`,
    sprite: `${origin}/basemap/sprites/light`,
    sources: {
      protomaps: {
        type: "vector",
        url: `pmtiles://${origin}/basemap/${pmtiles}`,
        attribution: "© مشارکت‌کنندگان OpenStreetMap · Protomaps",
      },
    },
    layers: layers("protomaps", namedFlavor("light"), { lang: "fa" }),
  };
}

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
  basemap,
}: {
  lat: number;
  lon: number;
  radiusM: number;
  assumed: boolean; // the platform publishes no radius: the circle is our assumption
  basemap: string | null; // the local PMTiles file name, or null for OSM's raster tiles
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
          paint: { "fill-color": "#147a72", "fill-opacity": 0.16 },
        });
        instance.addLayer({
          id: "blur-line",
          type: "line",
          source: "blur",
          paint: {
            "line-color": "#0d5b56",
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
  }, [lat, lon, radiusM, assumed, basemap]);

  return (
    <figure>
      <div
        ref={container}
        aria-hidden="true"
        className="h-64 w-full overflow-hidden rounded-card border border-line bg-sunken sm:h-80"
      />
      <figcaption className="mt-2 text-xs text-pretty text-fg-muted">
        نقطه‌ای که پلتفرم منتشر کرده و دایره‌ای به شعاع {faNumber(radiusM)} متر که ویلا در آن است
        {assumed ? " (پلتفرم شعاع را اعلام نکرده؛ این شعاع فرض ماست)" : ""}. جای دقیق ویلا را
        پلتفرم‌ها پنهان می‌کنند.
      </figcaption>
    </figure>
  );
}
