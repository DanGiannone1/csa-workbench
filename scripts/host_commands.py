"""Resolve Windows command shims without shell parsing."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import PureWindowsPath
from typing import Sequence


def _is_windows_host() -> bool:
    return os.name == "nt"


def _is_file(path: PureWindowsPath) -> bool:
    return os.path.isfile(str(path))


def command_for_host(command: Sequence[str]) -> list[str]:
    values = list(command)
    if not _is_windows_host() or not values:
        return values
    resolved = shutil.which(values[0])
    if resolved is None:
        return values
    shim = PureWindowsPath(resolved)
    if values[0] == "az" and shim.suffix.lower() in {".cmd", ".bat"}:
        azure_python = shim.parent.parent / "python.exe"
        if _is_file(azure_python):
            return [str(azure_python), "-X", "utf8", "-IBm", "azure.cli", *values[1:]]
        if not (
            os.environ.get("PYTEST_CURRENT_TEST")
            and os.environ.get("CSA_TEST_COMMAND_SHIMS") == "1"
        ):
            raise RuntimeError("Azure CLI installation is incomplete: bundled python.exe is missing")
    if values[0] in {"npm", "npx"} and shim.suffix.lower() in {".cmd", ".bat"}:
        node = shim.parent / "node.exe"
        script = shim.parent / "node_modules" / "npm" / "bin" / ("npx-cli.js" if values[0] == "npx" else "npm-cli.js")
        if _is_file(node) and _is_file(script):
            return [str(node), str(script), *values[1:]]
    if shim.suffix.lower() in {".cmd", ".bat"}:
        return [
            os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c",
            subprocess.list2cmdline([str(shim), *values[1:]]),
        ]
    if _is_file(shim):
        values[0] = str(shim)
    return values
