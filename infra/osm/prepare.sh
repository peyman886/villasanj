#!/bin/sh
# Clip the Geofabrik Iran extract to the Tehran–Caspian box, export its coastline and places, build the OSRM
# graph (ADR-0003 decision 5, ADR-0013). Zero requests to platforms; everything stays in data/osm.
#   OSM_SNAPSHOT=iran-260930 infra/osm/prepare.sh
set -eu

SNAPSHOT=${OSM_SNAPSHOT:-iran-260930}
DIR="$(pwd)/data/osm"
# Tehran, the Chalus, Haraz and Qazvin–Rasht corridors, and the Ramsar–Tonekabon coast.
BBOX=49.4,35.4,52.6,37.6
OSMIUM="docker run --rm -v $DIR:/data villasanj-osmium:local"
OSRM="docker run --rm -v $DIR:/data ghcr.io/project-osrm/osrm-backend:v6.0.0"

test -f "$DIR/$SNAPSHOT.osm.pbf" || { echo "missing $DIR/$SNAPSHOT.osm.pbf (make osm-download)"; exit 1; }

$OSMIUM extract --overwrite -b "$BBOX" --strategy complete_ways \
    -o /data/north.osm.pbf "/data/$SNAPSHOT.osm.pbf"
$OSMIUM tags-filter --overwrite -o /data/coastline.osm.pbf /data/north.osm.pbf w/natural=coastline
$OSMIUM export --overwrite --add-unique-id=type_id -f geojsonseq \
    -o /data/coastline.geojsonseq /data/coastline.osm.pbf

# Places distance claims name (M9): shops, bakeries, restaurants, medical, town centres (villages
# too: the loader keeps only those platforms call a city) and woods.
$OSMIUM tags-filter --overwrite -o /data/poi.osm.pbf /data/north.osm.pbf \
    nwr/shop=supermarket,convenience,grocery,general,bakery,mall,department_store \
    nwr/amenity=restaurant,fast_food,hospital,clinic,doctors,marketplace \
    n/place=city,town,village wr/landuse=forest wr/natural=wood
$OSMIUM export --overwrite --add-unique-id=type_id -f geojsonseq \
    -o /data/poi.geojsonseq /data/poi.osm.pbf

$OSRM osrm-extract -p /opt/car.lua /data/north.osm.pbf
$OSRM osrm-partition /data/north.osrm
$OSRM osrm-customize /data/north.osrm

echo "$SNAPSHOT" > "$DIR/SNAPSHOT"
ls -la "$DIR"
