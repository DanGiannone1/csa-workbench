"""Resolve Windows command shims without shell parsing."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence


def command_for_host(command: Sequence[str]) -> list[str]:
    values = list(command)
    if os.name != "nt" or not values:
        return values
    resolved = shutil.which(values[0])
    if resolved is None:
        return values
    shim = Path(resolved)
    if values[0] == "az" and shim.suffix.lower() in {".cmd", ".bat"}:
        azure_python = shim.parent.parent / "python.exe"
        if azure_python.is_file():
            return [str(azure_python), "-X", "utf8", "-IBm", "azure.cli", *values[1:]]
    if values[0] in {"npm", "npx"} and shim.suffix.lower() in {".cmd", ".bat"}:
        node = shim.parent / "node.exe"
        script = shim.parent / "node_modules" / "npm" / "bin" / ("npx-cli.js" if values[0] == "npx" else "npm-cli.js")
        if node.is_file() and script.is_file():
            return [str(node), str(script), *values[1:]]
    if shim.suffix.lower() in {".cmd", ".bat"}:
        return [
            os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c",
            subprocess.list2cmdline([str(shim), *values[1:]]),
        ]
    if shim.is_file():
        values[0] = str(shim)
    return values
