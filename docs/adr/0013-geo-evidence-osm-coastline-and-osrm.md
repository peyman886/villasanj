# ADR-0013 — Geo evidence: OSM coastline in PostGIS and free-flow OSRM drive times

Status: Accepted (2026-10-02) · Refines ADR-0003 decision 5 · Owner approved the OSM download on
2026-10-02 · Reproduce with `make osm-download osm-prepare routing-up geo`

## Context

- M9 judges published distance-to-the-sea claims, and M8 shows "drive time from Tehran" and filters
  by it. Both need geography the platforms do not provide: the Caspian coastline and a road graph.
- Listing locations are blurred. jabama publishes a 400 m radius; shab publishes none
  (`location_radius_m = None`). A verdict must hold for every possible position of the villa
  (product rule 5: CONTRADICTED only when the best case contradicts).
- External routing APIs (Google, Neshan) would mean third-party terms, keys and sending every
  listing's coordinates out. OSM data is open (ODbL) and works offline.

## Decision

1. **Data.** Geofabrik's Iran extract, snapshot `iran-260930` (230 MB; MD5 checked against
   Geofabrik's file), stored in the git-ignored `data/osm/`. The snapshot name is written to
   `data/osm/SNAPSHOT` and stored on every derived row as `dataset`.
2. **Clip.** `osmium extract --strategy complete_ways -b 49.4,35.4,52.6,37.6`: Tehran, the
   Chalus, Haraz and Qazvin–Rasht corridors, and the coast from Rasht to Amol. All jabama listings and
   597 of 601 shab listings fall inside (the other four are outliers far from the region). osmium
   runs in a small Debian image (`infra/docker/osmium`, `osmium-tool=1.15.0-1`), so nothing is
   installed on the host.
3. **Coastline.** The 55 `natural=coastline` ways in the box go into `enrichment.coastline` as
   PostGIS `geography(LineString)` with a GiST index. The Caspian shore is tagged
   `natural=coastline` in OSM (the export confirmed it). Distances are geodesic (`ST_Distance` on
   geography).
4. **Blur ranges.** For a distance to a fixed shape, the range over the blur circle is exact:
   any point within r of the pin is between d − r and d + r away (stored as `low_m`, `high_m`).
   When a platform publishes no radius, **500 m is assumed** (jabama's 400 m plus a margin) and the
   row says `radius_assumed = true`, so a UI can say so. Entity resolution keeps its own reading
   (a missing radius is an exact pin) because there it only affects recall.
5. **Drive times.** OSRM `v6.0.0` (the image has linux/arm64), car profile, MLD, served by the
   compose profile `routing` (`docker compose --profile routing up -d osrm`; 287 MB of RAM).
   The origin is Azadi Square, Tehran (`config/routing.toml`). Each listing's pin and 8 points
   on its blur circle are routed with the table service; min, pin and max are stored in
   `discovery.drive_time`. Times are **free-flow** (no traffic data) and must be labelled so
   (assumption A10). The table is per listing, not per villa as ARCHITECTURE first sketched; a
   villa's range after M5 is the union of its members' ranges.
6. **Reading published distance claims.** Three rules came from reading the first verdicts by
   hand (each is a unit test now):
   - the sea is a whole word: «دریاسر» (a plain) and «ساحلی» (as in «پیاده راه ساحلی») are not
     the sea, and a value given for two places («جنگل و دریا») is not judged;
   - a stated value is a rounded choice from a short list (jabama: «زیر ۵، ۵، ۱۰، … ۳۰، بیشتر از
     ۳۰»; shab: 5, 15, 30, 60), so «N دقیقه» means up to N + max(5, N/2) minutes, enough for
     nearest-option rounding on both lists (metres: max(50 m, N/2));
   - only "farther than claimed" can contradict: a villa closer than its claim, or one that
     understates («بیشتر از ۳۰ دقیقه»), is at most «تأیید نشد».
   Travel times become straight-line distances with generous speeds (walk 40–100 m/min, drive
   150–1000 m/min, assumption A13); an unknown mode is judged under both readings.

## Results (2026-10-02, OSM snapshot iran-260930)

- Coast distance for 2,985 of 2,985 jabama listings and 598 of 601 shab listings (the other three
  are more than 100 km away). Median 2.2 km (jabama) and 1.6 km (shab). Listings titled «ساحلی» are
  1–5 m from the line; «جنگلی» ones up to 26 km.
- Drive time for 100% of the 3,586 listings with coordinates (M8 criterion 3 at listing level).
  Median 261 min from Azadi Square; mean blur spread 3.3 min, p95 6.5 min, none above 30 min.
  Tehran → Ramsar: 261 min, 217 km.
- Sea claims (`villasanj enrichment truth-sea`): jabama 2,733 supported, 402 «تأیید نشد», 175
  contradicted; **170 of 1,909 listings with a sea claim (8.9%) have one contradicted**. shab
  (radius assumed): 268 / 33 / 12; 11 of 175 listings (6.3%). The contradicted samples are clear
  overclaims, e.g. «زیر ۵ دقیقه پیاده تا دریا» with the whole blur circle 6.3–7.1 km from the coast.

## Alternatives considered

- **Full Iran OSRM graph.** More memory and preprocessing for routes we never ask for (ADR-0003).
- **osmcoastline land polygons.** A global product, far larger than the 55 lines we need.
- **pyosmium in the backend.** Another native dependency in the Python environment for a one-off
  file job; the osmium CLI in a container keeps the backend unchanged.
- **External routing APIs.** Terms, keys, cost, and every coordinate leaves the machine.
- **Traffic-aware times.** No data source; we do not invent a "holiday traffic" factor.

## Consequences

- (+) Every value has a dataset name, a method and a range; verdicts never rest on an exact pin
  we do not have.
- (+) Offline and reproducible from one 230 MB download; the core stack is untouched.
- (−) Free-flow times are optimistic on busy weekends; the UI must label them.
- (−) The 500 m assumption for shab is a judgement; it is visible on every affected row.
- (−) Only the sea is judged so far. Other targets (supermarket, bakery, city centre) need OSM POIs
  and are not judged yet. (Superseded by the amendment below.)


## Amendment (2026-10-02): places from the same snapshot judge the other distance claims

Jabama and shab publish distances to supermarkets, bakeries, restaurants, medical centres, town
centres and forests as often as to the sea (≈ 15,000 claims). `infra/osm/prepare.sh` now also
exports those places from the clipped snapshot (shops `supermarket|convenience|grocery|general|
bakery`, amenities `restaurant|fast_food|hospital|clinic|doctors`, `place=city|town|village`,
`landuse=forest`, `natural=wood`); `enrichment places-load` keeps 16,708 of them in
`enrichment.place` and `enrichment places` stores each listing's nearest one per kind with the
blur range (`enrichment.place_distance`, migration 0011).

Rules, because an absent shop on the map is not an absent shop:

1. **Partial maps support, never contradict.** For shops, restaurants, medical centres and woods
   the nearest *mapped* place is an upper bound on the nearest real one: a claim is SUPPORTED
   when that place is within the claim from every point of the blur circle, otherwise «تأیید نشد».
2. **Town centres are complete and can contradict.** Every gazetteer city has an OSM centre; a
   village counts only if platforms call it a city (Javaherdeh is `place=village` in OSM; without
   it Javaherdeh listings were wrongly contradicted against Chaboksar, 15 km away). A centre is
   an area: anything within 1.5 km of the town's point counts as the centre (A20).
3. Targets without a kind («مراکز تفریحی», shrines, named sights) stay «بررسی نشد». «مراکز خرید»
   was added the same day as a partial-map kind (`shop=mall|department_store`,
   `amenity=marketplace`): jabama 1,337 supported, 871 not confirmed; 18,003 places in all.

First run (2026-10-02, snapshot iran-260930): jabama city-centre claims 2,126 supported, 189 not
confirmed, 46 contradicted (all walking claims, e.g. «۵ دقیقه پیاده» 3.5 km from Katalom's
centre); listings with at least one contradicted distance claim, any target: jabama 198 of 2,137
judged (9.3%, 95% CI 8.1–10.6%), shab 11 of 572 (1.9%, 1.1–3.4%). Before rule 2's area the count
was 210 city-centre contradictions; checking them by hand is what produced the 1.5 km extent.
