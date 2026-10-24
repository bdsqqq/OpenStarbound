#!/usr/bin/env bash
# No global installs: use an existing Pillow Python or an isolated Nix shell.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if python3 -c 'from PIL import Image' >/dev/null 2>&1; then
  exec python3 "$root/source/lab/behavior/behavior_lab.py" "$@"
fi
if ! command -v nix-shell >/dev/null 2>&1; then
  printf '%s\n' 'Pillow required: install via your environment, or provide nix-shell (python3Packages.pillow); no pip install is performed.' >&2
  exit 2
fi
# Quote each argument for nix-shell --run rather than interpolating raw paths.
printf -v invocation '%q ' python3 "$root/source/lab/behavior/behavior_lab.py" "$@"
exec nix-shell -p python3 python3Packages.pillow --run "$invocation"
