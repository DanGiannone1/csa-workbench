#!/usr/bin/env sh
# Compatibility wrapper. Native Windows dispatches the Python command through WSL.
set -eu
repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"
exec uv run python -m scripts.workbench eval waza "$@"
