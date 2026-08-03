#!/usr/bin/env sh
# Compatibility wrapper. The portable implementation lives in scripts/workbench.py.
set -eu
repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"
exec uv run python -m scripts.workbench deploy "$@"
