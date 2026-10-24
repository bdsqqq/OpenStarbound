#!/bin/sh
# Checking must never regenerate: stale catalogs should fail the validation gate.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "${1:-}" = "--self-test" ]; then
  shift
  exec python3 -B "$root/source/lab/migration/test_inventory.py" "$@"
fi
exec python3 -B "$root/source/lab/migration/inventory.py" "$@"
