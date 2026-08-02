#!/usr/bin/env python3
"""One cross-platform command surface for the CSA Workbench repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from datetime import UTC, datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts.host_commands import command_for_host

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
WAZA_VERSION = "0.38.3"
WAZA_RELEASE = f"v{WAZA_VERSION}"
WAZA_CHECKSUMS = {
    "waza-linux-amd64": "168e3562deeaa1958d44366b37d963b48b091c325c6c9b5b2613e5399ff077b9",
    "waza-linux-arm64": "ab5d6a3e502a0f7f5a48149e034fa07875a2fe02addddec6b9b9dba14f3b4685",
    "waza-darwin-amd64": "f2a0c6952abbb5ad75bf17e2769c34c480093c269574839368b82d40b3c5dec9",
    "waza-darwin-arm64": "99aa4366b198f319145cffeef42d500eb9f6178235a0537d34c19dd8f2f46fec",
    "waza-windows-amd64.exe": "b2f7c84dfd8df44a6eb962385b37976c59637c96f0a9b34cf7328e8ababc5b88",
    "waza-windows-arm64.exe": "b867521c70ae817fed827d0de6bde4ce927cd7df9be5214d7033ae82ed14c891",
}


class CommandError(RuntimeError):
    """A repository command cannot continue safely."""

    exit_code = 1


class ConfigurationError(CommandError):
    """A command was configured incorrectly before work began."""

    exit_code = 2


@dataclass(frozen=True)
class WazaSuite:
    name: str
    lane: str

    @property
    def eval_file(self) -> Path:
        return ROOT / "tests" / "evals" / "waza" / self.name / "eval.yaml"

    @property
    def skill_dir(self) -> Path:
        return ROOT / "backend" / "assistant" / "product-skills" / self.name


WAZA_SUITES = (
    WazaSuite("engagement-meeting-prep", "gate"),
    WazaSuite("tasks", "advisory"),
    WazaSuite("calendar", "advisory"),
    WazaSuite("weekly-review", "advisory"),
)


def run(
    command: Sequence[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run an argument list without shell parsing."""
    resolved = command_for_host(command)
    print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(
        resolved, cwd=cwd, env=env, text=True, check=True,
        capture_output=capture,
    )


def require(*commands: str) -> None:
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        raise CommandError(f"Required tool is unavailable: {', '.join(missing)}")


def setup() -> int:
    """Check tools, create the local environment file once, and install dependencies."""
    if sys.version_info < (3, 12):
        raise ConfigurationError("Python 3.12 or later is required")
    require("git", "node", "npm", "uv")
    if shutil.which("az") is None:
        print("Note: Azure CLI is not installed. Local work is ready; install it before deployment.")

    dotenv = ROOT / ".env"
    if dotenv.exists():
        print("Keeping existing .env unchanged.")
    else:
        example = ROOT / ".env.example"
        if not example.exists():
            raise CommandError(".env.example is missing")
        with dotenv.open("x", encoding="utf-8") as destination:
            destination.write(example.read_text(encoding="utf-8"))
        print("Created .env from .env.example. Review its values before running locally.")

    run(["npm", "ci"])
    run(["uv", "sync", "--locked"])
    run(["npm", "ci"], cwd=FRONTEND)
    print("Setup complete.")
    return 0


def dev() -> int:
    """Start the launcher that owns the three local child processes."""
    return subprocess.run([sys.executable, "-m", "scripts.dev"], cwd=ROOT).returncode


def verify(*, skip_bicep: bool, skip_waza: bool) -> int:
    """Run the deterministic repository checks on every supported host."""
    require("git", "node", "npm", "uv")
    if not skip_bicep:
        require("az")

    run(["uv", "lock", "--check"])
    run(["uv", "run", "pytest", "-q"])
    run(["npm", "run", "test:mvp-evidence"])
    run(["npm", "run", "test:design-system"])
    package_scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8")).get("scripts", {})
    if "eval:waza:validate" in package_scripts:
        run(["npm", "run", "eval:waza:validate"])
    if skip_waza:
        print("Skipping Waza only because --skip-waza was supplied.")
    else:
        waza("check", inside_wsl=False, use_wsl=False)
    run(["npm", "run", "test:contract"], cwd=FRONTEND)
    run(["npm", "run", "lint"], cwd=FRONTEND)
    run(["npm", "run", "build"], cwd=FRONTEND)
    if not skip_bicep:
        with tempfile.TemporaryDirectory(prefix="csa-workbench-bicep-") as temporary:
            output = Path(temporary)
            run(["az", "bicep", "build", "--file", "infra/foundation.bicep", "--outfile", str(output / "foundation.json")])
            run(["az", "bicep", "build", "--file", "infra/apps.bicep", "--outfile", str(output / "apps.json")])
    run(["git", "diff", "--check"])
    return 0


def _waza_asset() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = {"linux": "linux", "darwin": "darwin", "windows": "windows"}.get(system)
    architecture = {
        "x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64",
    }.get(machine)
    if os_name is None or architecture is None:
        raise CommandError(f"Waza {WAZA_VERSION} does not publish a binary for {system}/{machine}")
    asset = f"waza-{os_name}-{architecture}{'.exe' if os_name == 'windows' else ''}"
    return asset, WAZA_CHECKSUMS[asset]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _waza_process(binary: Path, arguments: Sequence[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    command = [str(binary), *arguments]
    if os.name == "nt" and binary.suffix.lower() == ".sh":
        command = ["bash", str(binary), *arguments]
    print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(
        command, cwd=ROOT, env={**os.environ, "WAZA_NO_UPDATE_CHECK": "1"},
        text=True, capture_output=capture, check=False,
    )


def _install_waza() -> Path:
    test_mode = os.getenv("CSA_WAZA_TEST_MODE", "0") == "1"
    override = os.getenv("CSA_WAZA_BIN", "")
    if (override or os.getenv("CSA_WAZA_RESULTS_ROOT")) and not test_mode:
        raise ConfigurationError("Waza binary/result overrides are available only to deterministic wrapper tests")
    if override:
        binary = Path(override)
        if not binary.is_file() or (os.name != "nt" and not os.access(binary, os.X_OK)):
            raise ConfigurationError(f"Injected Waza binary is missing or not executable: {binary}")
        result = _waza_process(binary, ["--version"], capture=True)
        if result.returncode != 0 or WAZA_VERSION not in result.stdout:
            raise ConfigurationError(f"Injected Waza binary is missing or not version {WAZA_VERSION}: {binary}")
        return binary

    asset, checksum = _waza_asset()
    install_root = ROOT / "evidence" / "mvp" / "local-synthetic" / "tools" / "waza" / WAZA_RELEASE
    binary = install_root / ("waza.exe" if sys.platform == "win32" else "waza")
    if binary.is_file() and _sha256(binary) == checksum:
        version = _waza_process(binary, ["--version"], capture=True)
        if version.returncode == 0 and WAZA_VERSION in version.stdout:
            return binary
        raise ConfigurationError(f"Pinned Waza binary reports an unexpected version: {binary}")

    install_root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="waza.download.", dir=install_root, delete=False) as download:
        temporary = Path(download.name)
    try:
        urllib.request.urlretrieve(
            f"https://github.com/microsoft/waza/releases/download/{WAZA_RELEASE}/{asset}",
            temporary,
        )
        actual = _sha256(temporary)
        if actual != checksum:
            raise ConfigurationError(f"Waza checksum mismatch for {asset}: expected {checksum}, got {actual}")
        temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        temporary.replace(binary)
    finally:
        temporary.unlink(missing_ok=True)
    version = _waza_process(binary, ["--version"])
    if version.returncode != 0:
        return_code = version.returncode if version.returncode > 1 else 2
        raise ConfigurationError(f"Waza version check failed with exit status {return_code}")
    return binary


def _run_waza_eval(binary: Path, suite: WazaSuite, tag: str | None) -> int:
    results_root = Path(os.getenv("CSA_WAZA_RESULTS_ROOT", str(ROOT / "evidence" / "mvp" / "local-synthetic" / "waza")))
    eval_file = suite.eval_file
    skill_file = suite.skill_dir / "SKILL.md"
    if not eval_file.is_file() or not skill_file.is_file():
        print(f"Waza suite is incomplete: {suite.name}", file=sys.stderr)
        return 2
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = results_root / f"{stamp}-{os.getpid()}-{suite.name}"
    transcript_dir = run_dir / "transcripts"
    result_path = run_dir / "waza.json"
    transcript_dir.mkdir(parents=True)

    before_hash = _sha256(skill_file)
    source_revision = run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip()
    test_mode = os.getenv("CSA_WAZA_TEST_MODE", "0") == "1"
    dirty_before = test_mode or bool(run(["git", "status", "--porcelain", "--untracked-files=normal"], capture=True).stdout.strip())
    arguments = ["run", str(eval_file), "--output", str(result_path), "--transcript-dir", str(transcript_dir), "--interpret", "--no-cache"]
    trials = os.getenv("CSA_WAZA_TRIALS", "")
    if trials:
        arguments.extend(["--trials", trials])
    if tag:
        arguments.extend(["--tags", tag])
    result = _waza_process(binary, arguments)
    if result.returncode > 1:
        print(f"Waza could not execute {eval_file}; exit status {result.returncode}", file=sys.stderr)
        return result.returncode
    if not result_path.is_file() or result_path.stat().st_size == 0:
        print(f"Waza returned {result.returncode} without a result file: {result_path}", file=sys.stderr)
        return 2
    if _sha256(skill_file) != before_hash:
        print("Product skill changed during the Waza run; refusing unbound evidence", file=sys.stderr)
        return 2
    source_revision_after = run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip()
    dirty_after = test_mode or bool(run(["git", "status", "--porcelain", "--untracked-files=normal"], capture=True).stdout.strip())

    report = json.loads(result_path.read_text(encoding="utf-8"))
    report["csaMvpProvenance"] = {
        "runner": "scripts/workbench.py",
        "wazaVersion": WAZA_VERSION,
        "sourceRevision": source_revision,
        "sourceRevisionAfter": source_revision_after,
        "sourceDirtyBefore": dirty_before,
        "sourceDirtyAfter": dirty_after,
        "tag": tag or "all",
        "skill": {
            "name": suite.name,
            "path": f"backend/assistant/product-skills/{suite.name}/SKILL.md",
            "sha256": before_hash,
        },
        "eval": f"tests/evals/waza/{suite.name}/eval.yaml",
        "recordedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    result_path.write_text(f"{json.dumps(report, indent=2)}\n", encoding="utf-8")
    print(f"CSA MVP provenance recorded in: {result_path}")
    return result.returncode


def _waza_in_wsl(action: str) -> int:
    require("wsl")
    translated = run(["wsl", "wslpath", "-a", str(ROOT)], capture=True).stdout.strip()
    if not translated:
        raise CommandError("WSL could not translate the repository path")
    run([
        "wsl", "--cd", translated, "python3", "-m", "scripts.workbench", "eval", "waza", action, "--inside-wsl",
    ])
    return 0


def waza(action: str, *, inside_wsl: bool, use_wsl: bool) -> int:
    """Install and run the pinned native Waza binary, with optional WSL fallback."""
    if sys.platform == "win32" and use_wsl and not inside_wsl:
        return _waza_in_wsl(action)
    trials = os.getenv("CSA_WAZA_TRIALS", "")
    if trials and not re.fullmatch(r"[1-9][0-9]*", trials):
        raise ConfigurationError("CSA_WAZA_TRIALS must be a positive integer")
    binary = _install_waza()
    if action in {"install", "version"}:
        result = _waza_process(binary, ["--version"])
        return result.returncode
    available = [suite for suite in WAZA_SUITES if suite.eval_file.is_file() and suite.skill_dir.is_dir()]
    if not available:
        raise ConfigurationError("No complete Waza suites are checked in")
    if action == "check":
        for suite in available:
            result = _waza_process(binary, ["check", str(suite.skill_dir), "--format", "json"], capture=True)
            if result.returncode != 0:
                return result.returncode
            report = json.loads(result.stdout)
            if not isinstance(report.get("skills"), list) or len(report["skills"]) != 1 or report["skills"][0].get("ready") is not True:
                raise CommandError(f"Waza readiness did not approve exactly one skill: {suite.name}")
            result = _waza_process(binary, ["check", str(suite.skill_dir)])
            if result.returncode != 0:
                return result.returncode
        return 0
    if action == "advisory":
        advisory = [suite for suite in available if suite.lane == "advisory"]
        if not advisory:
            raise ConfigurationError("No advisory Waza suites are checked in")
        aggregate = 0
        for suite in advisory:
            status = _run_waza_eval(binary, suite, "advisory")
            if status > 1:
                return status
            aggregate = max(aggregate, status)
        return aggregate
    gate = next(suite for suite in WAZA_SUITES if suite.lane == "gate")
    return _run_waza_eval(binary, gate, "gate" if action == "gate" else None)


def eval_command(name: str, action: str | None, inside_wsl: bool, use_wsl: bool) -> int:
    commands = {
        "mvp": ["node", "scripts/mvp_agent_eval.mjs"],
        "scorecard": ["node", "scripts/mvp_scorecard_merge.mjs"],
        "history": ["node", "scripts/mvp_scorecard_history.mjs"],
        "showcase": ["node", "scripts/eval_showcase_server.mjs"],
        "demo": ["node", "scripts/eval_demo.mjs"],
        "playwright": ["node", "scripts/mvp_playwright.mjs"],
        "foundry": ["uv", "run", "--package", "workbench-assistant", "--with", "azure-ai-projects", "--with", "azure-identity", "python", "scripts/foundry_eval_upload.py"],
    }
    if name == "waza":
        return waza(action or "check", inside_wsl=inside_wsl, use_wsl=use_wsl)
    run(commands[name])
    return 0


def deploy(action: str, confirmation: str | None, browser: bool) -> int:
    """Delegate Azure safety policy to the portable deployment helper."""
    from infra.deploy import DeploymentError, main as deploy_main

    try:
        return deploy_main(action=action, confirmation=confirmation, browser=browser)
    except DeploymentError as exc:
        raise CommandError(str(exc)) from exc


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    subcommands = command.add_subparsers(dest="command", required=True)
    subcommands.add_parser("setup", help="check tools and install dependencies")
    subcommands.add_parser("dev", help="start the local app")
    verification = subcommands.add_parser("verify", help="run deterministic checks")
    verification.add_argument("--skip-bicep", action="store_true", help="skip Bicep compilation when Azure CLI is unavailable")
    verification.add_argument("--skip-waza", action="store_true", help="skip the external Waza download in the portable CI matrix")

    evaluation = subcommands.add_parser("eval", help="run an evaluation workflow")
    evaluation.add_argument("name", choices=["mvp", "scorecard", "history", "showcase", "foundry", "demo", "playwright", "waza"])
    evaluation.add_argument("action", nargs="?", choices=["install", "version", "check", "gate", "advisory", "run"])
    evaluation.add_argument("--inside-wsl", action="store_true", help=argparse.SUPPRESS)
    evaluation.add_argument("--wsl", action="store_true", help="use WSL instead of the native Windows Waza binary")

    deployment = subcommands.add_parser("deploy", help="plan, apply, or verify the guarded Azure deployment")
    deployment.add_argument("action", choices=["plan", "apply", "verify"], nargs="?", default="plan")
    deployment.add_argument("--confirm", help="exact apply:<PLAN_ID>:<RESOURCE_GROUP> value printed by plan")
    deployment.add_argument("--browser", action="store_true", help="also run the authorized demo browser journey during verify")
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "setup":
            return setup()
        if args.command == "dev":
            return dev()
        if args.command == "verify":
            return verify(skip_bicep=args.skip_bicep, skip_waza=args.skip_waza)
        if args.command == "eval":
            return eval_command(args.name, args.action, args.inside_wsl, args.wsl)
        return deploy(args.action, args.confirm, args.browser)
    except subprocess.CalledProcessError as exc:
        print(f"Error: command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode
    except (CommandError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code if isinstance(exc, CommandError) else 1


if __name__ == "__main__":
    raise SystemExit(main())
