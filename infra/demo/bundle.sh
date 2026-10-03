#!/bin/sh
# Dump the database (catalog, villas, evidence, labels, LLM cache and ledger) into data/demo for
# the offline demo. Zero network. The dev stack's db must be up (make up).
set -eu
out=data/demo
mkdir -p "$out"
stamp=$(date -u +%Y%m%dT%H%MZ)
file="$out/villasanj-$stamp.dump"
docker compose exec -T db pg_dump -U villasanj -d villasanj --format=custom --no-owner >"$file.part"
mv "$file.part" "$file"
(cd "$out" && shasum -a 256 "$(basename "$file")" >"$(basename "$file").sha256" && ln -sf "$(basename "$file")" latest.dump)
echo "bundle: $file ($(du -h "$file" | cut -f1)); sha256 in $file.sha256"
