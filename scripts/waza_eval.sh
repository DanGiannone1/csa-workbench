#!/usr/bin/env sh
# Compatibility wrapper. Native binaries are the default; pass --wsl on Windows to opt into WSL.
set -eu
repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"
exec uv run python -m scripts.workbench eval waza "$@"
