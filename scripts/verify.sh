#!/usr/bin/env sh
# Compatibility wrapper. Use `uv run python -m scripts.workbench verify` on every OS.
set -eu
repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"
exec uv run python -m scripts.workbench verify "$@"
