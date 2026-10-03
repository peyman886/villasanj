#!/bin/sh
# Offline basemap for the listing maps (ADR-0003 amendment): a Protomaps extract of the
# Ramsar–Tonekabon box (OSM, ODbL) plus the glyph ranges and sprites its style needs, all in
# data/basemap (git-ignored). Measured 2026-10-03: 11 MB extract, z0–15.
#   BASEMAP_BUILD=20261003 infra/basemap/prepare.sh
set -eu

BUILD=${BASEMAP_BUILD:-$(date -u +%Y%m%d)}
BBOX=50.1,36.4,51.4,37.2
DIR="$(pwd)/data/basemap"
ASSETS=https://protomaps.github.io/basemaps-assets
mkdir -p "$DIR/fonts" "$DIR/sprites"

docker run --rm -v "$DIR:/data" protomaps/go-pmtiles:latest extract \
    "https://build.protomaps.com/$BUILD.pmtiles" "/data/region-$BUILD.pmtiles" \
    --bbox="$BBOX" --maxzoom=15

# Latin, punctuation (ZWNJ), Arabic script and its presentation forms: what Persian labels use.
for font in "Noto Sans Regular" "Noto Sans Medium" "Noto Sans Italic"; do
    mkdir -p "$DIR/fonts/$font"
    for range in 0-255 256-511 512-767 1536-1791 1792-2047 2048-2303 8192-8447 \
        64256-64511 64512-64767 64768-65023 65024-65279; do
        curl -fsS -o "$DIR/fonts/$font/$range.pbf" \
            "$ASSETS/fonts/$(printf %s "$font" | sed 's/ /%20/g')/$range.pbf"
    done
done
for sprite in light.json light.png light@2x.json light@2x.png; do
    curl -fsS -o "$DIR/sprites/$sprite" "$ASSETS/sprites/v4/$sprite"
done

printf '{"pmtiles": "region-%s.pmtiles", "build": "%s", "bbox": [%s]}\n' \
    "$BUILD" "$BUILD" "$BBOX" > "$DIR/basemap.json"
du -sh "$DIR"
