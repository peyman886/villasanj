#!/bin/sh
# Bring up the offline demo from data/demo/latest.dump: a separate compose project
# (villasanj-demo) on its own ports, restored once into its own volume, LLM answers from cache.
set -eu
dump=data/demo/latest.dump
if [ ! -f "$dump" ]; then
  echo "no bundle in data/demo: run make demo-bundle first" >&2
  exit 1
fi
(cd data/demo && shasum -a 256 -c "$(readlink latest.dump).sha256" >/dev/null) || {
  echo "the bundle does not match its checksum" >&2
  exit 1
}
mkdir -p data/demo/blobs
export VILLASANJ_WEB_PORT="${VILLASANJ_DEMO_WEB_PORT:-3400}"
export VILLASANJ_API_PORT="${VILLASANJ_DEMO_API_PORT:-8900}"
export VILLASANJ_DB_PORT="${VILLASANJ_DEMO_DB_PORT:-5434}"
compose="docker compose -p villasanj-demo -f docker-compose.yml -f infra/demo/compose.demo.yml"
$compose up -d --wait db
restored=$($compose exec -T db psql -U villasanj -d villasanj -tAc \
  "select count(*) from information_schema.tables where table_schema = 'catalog'")
if [ "$restored" = "0" ]; then
  echo "restoring $(readlink "$dump") into the demo database..."
  $compose exec -T db pg_restore -U villasanj -d villasanj --no-owner --exit-on-error <"$dump"
fi
$compose up -d --wait api web
echo "demo: http://localhost:${VILLASANJ_WEB_PORT} (api ${VILLASANJ_API_PORT}); stop with make demo-down"
