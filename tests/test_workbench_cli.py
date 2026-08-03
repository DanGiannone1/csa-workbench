from __future__ import annotations

from pathlib import Path
import json
import subprocess

import pytest
from scripts import workbench

ROOT = Path(__file__).resolve().parents[1]


def test_command_surface_has_the_five_plain_language_verbs() -> None:
    parser = workbench.parser()
    for command in ("setup", "dev", "verify", "eval", "deploy"):
        parsed = parser.parse_args([command]) if command not in {"eval"} else parser.parse_args([command, "mvp"])
        assert parsed.command == command


def test_setup_never_overwrites_an_existing_environment_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text("KEEP=original\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("KEEP=example\n", encoding="utf-8")
    (tmp_path / "frontend").mkdir()
    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(workbench, "ROOT", tmp_path)
    monkeypatch.setattr(workbench, "FRONTEND", tmp_path / "frontend")
    monkeypatch.setattr(workbench, "require", lambda *args: None)
    monkeypatch.setattr(workbench, "run", lambda command, cwd=tmp_path, **kwargs: commands.append((list(command), cwd)))

    assert workbench.setup() == 0
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "KEEP=original\n"
    assert [command for command, _ in commands] == [
        ["npm", "ci"], ["uv", "sync", "--locked"], ["npm", "ci"],
    ]


def test_setup_creates_environment_file_only_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env.example").write_text("SAFE=example\n", encoding="utf-8")
    (tmp_path / "frontend").mkdir()
    monkeypatch.setattr(workbench, "ROOT", tmp_path)
    monkeypatch.setattr(workbench, "FRONTEND", tmp_path / "frontend")
    monkeypatch.setattr(workbench, "require", lambda *args: None)
    monkeypatch.setattr(workbench, "run", lambda *args, **kwargs: None)

    assert workbench.setup() == 0
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "SAFE=example\n"


def test_what_if_changes_only_the_azure_operation_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from infra.deploy import Deployment

    deployment = object.__new__(Deployment)
    recorded: list[list[str]] = []
    monkeypatch.setattr(deployment, "execute", lambda command, **kwargs: recorded.append(list(command)))
    create = ["az", "deployment", "sub", "create", "--parameters", "azureOpenAiModelName=create"]

    deployment.deployment_what_if(create)

    assert recorded == [[
        "az", "deployment", "sub", "what-if", "--parameters", "azureOpenAiModelName=create",
        "--result-format", "FullResourcePayloads", "--only-show-errors",
    ]]


def _minimum_deployment_environment() -> dict[str, str]:
    return {
        "INSTANCE_SLUG": "mvp1",
        "MODEL_DEPLOYMENT_NAME": "primary",
        "MODEL_NAME": "model",
        "MODEL_VERSION": "2026-01-01",
        "MODEL_SKU_NAME": "GlobalStandard",
        "MODEL_CAPACITY": "30",
    }


def test_optional_azure_capabilities_are_off_by_default() -> None:
    from infra.deploy import Deployment

    deployment = Deployment(_minimum_deployment_environment())

    assert deployment.enable_legacy_model is False
    assert deployment.enable_foundry_project is False
    assert deployment.legacy_model_deployment_name == ""


def test_existing_legacy_model_configuration_remains_backward_compatible() -> None:
    from infra.deploy import Deployment

    environment = {
        **_minimum_deployment_environment(),
        "LEGACY_MODEL_DEPLOYMENT_NAME": "rollback",
        "LEGACY_MODEL_NAME": "legacy-model",
        "LEGACY_MODEL_VERSION": "2025-01-01",
        "LEGACY_MODEL_SKU_NAME": "GlobalStandard",
        "LEGACY_MODEL_CAPACITY": "10",
    }

    deployment = Deployment(environment)

    assert deployment.enable_legacy_model is True
    assert deployment.legacy_model_deployment_name == "rollback"


def _plan_id(environment: dict[str, str]) -> str:
    from infra.deploy import Deployment

    deployment = Deployment(environment)
    deployment.validate_account_and_revision = lambda: None
    deployment.governance_preflight = lambda: None
    deployment.recovery_preflight = lambda: None
    return deployment.make_plan()[1]


def test_plan_confirmation_binds_optional_azure_capabilities() -> None:
    base = _minimum_deployment_environment()
    foundry = {**base, "ENABLE_FOUNDRY_PROJECT": "true"}
    legacy = {
        **base,
        "ENABLE_LEGACY_MODEL": "true",
        "LEGACY_MODEL_DEPLOYMENT_NAME": "rollback",
        "LEGACY_MODEL_NAME": "legacy-model",
        "LEGACY_MODEL_VERSION": "2025-01-01",
        "LEGACY_MODEL_SKU_NAME": "GlobalStandard",
        "LEGACY_MODEL_CAPACITY": "10",
    }

    default_plan = _plan_id(base)

    assert _plan_id(foundry) != default_plan
    assert _plan_id(legacy) != default_plan


def test_windows_azure_cli_uses_its_python_in_utf8_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import host_commands

    monkeypatch.setattr(host_commands, "_is_windows_host", lambda: True)
    monkeypatch.setattr(host_commands.shutil, "which", lambda _name: "C:/AzureCLI/bin/az.cmd")
    monkeypatch.setattr(host_commands, "_is_file", lambda _path: True)
    body = '{"text":"café ☕ with spaces & | % and \\"quotes\\""}'

    command = host_commands.command_for_host(["az", "rest", "--method", "POST", "--body", body])

    assert command == [
        "C:\\AzureCLI\\python.exe", "-X", "utf8", "-IBm", "azure.cli",
        "rest", "--method", "POST", "--body", body,
    ]


def test_windows_azure_cli_fails_closed_without_its_python(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import host_commands

    monkeypatch.setattr(host_commands, "_is_windows_host", lambda: True)
    monkeypatch.setattr(host_commands.shutil, "which", lambda _name: "C:/AzureCLI/bin/az.cmd")
    monkeypatch.setattr(host_commands, "_is_file", lambda _path: False)
    monkeypatch.delenv("CSA_TEST_COMMAND_SHIMS", raising=False)

    with pytest.raises(RuntimeError, match="installation is incomplete"):
        host_commands.command_for_host(["az", "rest", "--body", '{"unsafe":"& | %"}'])


@pytest.mark.parametrize(
    ("machine", "asset"),
    [("AMD64", "waza-windows-amd64.exe"), ("ARM64", "waza-windows-arm64.exe")],
)
def test_waza_has_pinned_native_windows_assets(
    machine: str, asset: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workbench.platform, "system", lambda: "Windows")
    monkeypatch.setattr(workbench.platform, "machine", lambda: machine)

    selected, checksum = workbench._waza_asset()

    assert selected == asset
    assert len(checksum) == 64


def test_waza_python_test_wrapper_uses_the_current_interpreter() -> None:
    wrapper = Path("C:/temporary test/fake-waza.py")

    assert workbench._waza_command(wrapper, ["--version"], test_mode=True) == [
        workbench.sys.executable, str(wrapper), "--version",
    ]

    native = Path("C:/tools/waza.exe")
    assert workbench._waza_command(native, ["--version"], test_mode=True) == [
        str(native), "--version",
    ]

    assert workbench._waza_command(wrapper, ["--version"], test_mode=False) == [
        str(wrapper), "--version",
    ]


def test_waza_advisory_runs_every_catalog_suite_and_aggregates_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for suite in workbench.WAZA_SUITES:
        (tmp_path / "tests" / "evals" / "waza" / suite.name).mkdir(parents=True)
        (tmp_path / "tests" / "evals" / "waza" / suite.name / "eval.yaml").write_text("name: fixture\n")
        (tmp_path / "backend" / "assistant" / "product-skills" / suite.name).mkdir(parents=True)
    calls: list[str] = []
    statuses = {"engagement-meeting-prep": 0, "tasks": 1, "calendar": 0, "weekly-review": 0}
    monkeypatch.setattr(workbench, "ROOT", tmp_path)
    monkeypatch.setattr(workbench, "_install_waza", lambda: tmp_path / "waza")
    monkeypatch.setattr(
        workbench, "_run_waza_eval",
        lambda binary, suite, tag: calls.append(suite.name) or statuses[suite.name],
    )

    assert workbench.waza("advisory", inside_wsl=False, use_wsl=False) == 1
    assert calls == ["engagement-meeting-prep", "tasks", "calendar", "weekly-review"]


def test_waza_advisory_stops_on_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for suite in workbench.WAZA_SUITES:
        (tmp_path / "tests" / "evals" / "waza" / suite.name).mkdir(parents=True)
        (tmp_path / "tests" / "evals" / "waza" / suite.name / "eval.yaml").write_text("name: fixture\n")
        (tmp_path / "backend" / "assistant" / "product-skills" / suite.name).mkdir(parents=True)
    calls: list[str] = []
    monkeypatch.setattr(workbench, "ROOT", tmp_path)
    monkeypatch.setattr(workbench, "_install_waza", lambda: tmp_path / "waza")
    monkeypatch.setattr(workbench, "_run_waza_eval", lambda binary, suite, tag: calls.append(suite.name) or 2)

    assert workbench.waza("advisory", inside_wsl=False, use_wsl=False) == 2
    assert calls == ["engagement-meeting-prep"]


def test_waza_test_failure_keeps_per_suite_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = workbench.WazaSuite("tasks", "advisory")
    (tmp_path / "tests" / "evals" / "waza" / suite.name).mkdir(parents=True)
    (tmp_path / "tests" / "evals" / "waza" / suite.name / "eval.yaml").write_text("name: fixture\n")
    skill = tmp_path / "backend" / "assistant" / "product-skills" / suite.name / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Tasks\n", encoding="utf-8")
    monkeypatch.setattr(workbench, "ROOT", tmp_path)
    monkeypatch.setenv("CSA_WAZA_TEST_MODE", "1")
    monkeypatch.setenv("CSA_WAZA_RESULTS_ROOT", str(tmp_path / "results"))
    monkeypatch.setattr(
        workbench, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "a" * 40 + "\n" if "rev-parse" in command else "", ""),
    )

    def fake_process(binary: Path, arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output = Path(arguments[arguments.index("--output") + 1])
        output.write_text(json.dumps({"schemaVersion": "1.2", "tasks": []}), encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 1, "", "")

    monkeypatch.setattr(workbench, "_waza_process", fake_process)

    assert workbench._run_waza_eval(tmp_path / "waza", suite, "advisory") == 1
    result_file = next((tmp_path / "results").glob("*/waza.json"))
    provenance = json.loads(result_file.read_text(encoding="utf-8"))["csaMvpProvenance"]
    assert provenance["skill"]["name"] == "tasks"
    assert provenance["sourceDirtyBefore"] is True
    assert provenance["sourceDirtyAfter"] is True


def test_post_deploy_verification_checks_entra_session_without_exposing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from infra import deploy

    azure_calls: list[list[str]] = []
    http_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(deploy.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(deploy.subprocess, "run", lambda *args, **kwargs: deploy.subprocess.CompletedProcess(args[0], 0, "", ""))

    def azure(command: list[str], env: dict[str, str]) -> str:
        azure_calls.append(command)
        joined = " ".join(command)
        if "frontend" in joined and "containerapp show" in joined:
            return "frontend.example"
        if "api" in joined and "containerapp show" in joined:
            return "api.example"
        if "ad app list" in joined:
            return "api-client"
        if "get-access-token" in joined:
            return "secret-token"
        raise AssertionError(joined)

    def http(url: str, *, method: str = "GET", **kwargs: object) -> object:
        http_calls.append((method, url))
        if url.endswith("/auth/me"):
            return {"identity": "entra", "id": "u-1"}
        if method == "POST":
            return {"status": "active", "session_id": "session-1"}
        return {}

    monkeypatch.setattr(deploy, "_azure_output", azure)
    monkeypatch.setattr(deploy, "_http_json", http)
    monkeypatch.setattr(deploy, "_http_reachable", lambda url: None)

    assert deploy.verify_deployment({"INSTANCE_SLUG": "mvp1", "IDENTITY_MODE": "entra"}) == 0
    assert ("DELETE", "https://api.example/sessions/session-1") in http_calls
    assert any("get-access-token" in call for call in azure_calls)


def test_apply_verifies_the_running_application_before_reporting_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from infra import deploy

    deployment = object.__new__(deploy.Deployment)
    deployment.env = {"INSTANCE_SLUG": "mvp1", "IDENTITY_MODE": "entra"}
    deployment.slug = "mvp1"
    deployment.resource_group = "csa-wb-mvp1-rg"
    deployment.frontend_app_name = "csa-wb-mvp1-frontend"
    deployment.api_app_name = "csa-wb-mvp1-api"
    deployment.runtime_app_name = "csa-wb-mvp1-runtime"
    deployment.tenant_id = "tenant"
    deployment.identity_mode = "entra"
    deployment.sha = "a" * 40
    deployment.make_plan = lambda: ({}, "plan-1")
    deployment.foundation_command = lambda: ["az", "deployment", "group", "create"]
    deployment.delete_approved_recovery_targets = lambda: None
    deployment.deployment_what_if = lambda _command: None
    deployment.execute = lambda *_args, **_kwargs: None
    values = {
        "environmentDefaultDomain": "example.test",
        "acrLoginServer": "acr.example.test",
        "acrName": "acr",
        "azureOpenAiName": "ai",
        "azureOpenAiEndpoint": "https://ai.example.test",
        "frontendIdentityId": "frontend-id",
        "apiIdentityId": "api-id",
        "runtimeIdentityId": "runtime-id",
        "apiIdentityPrincipalId": "api-principal",
        "cosmosAccountName": "cosmos",
        "storageAccountName": "storage",
        "appInsightsConnectionString": "InstrumentationKey=test",
    }
    deployment.foundation_output = lambda name: values[name]
    deployment.output = lambda _command: json.dumps({
        "api_client_id": "api-client",
        "web_client_id": "web-client",
        "runtime_client_id": "runtime-client",
    })
    deployment._apps_command = lambda _outputs: ["az", "deployment", "group", "create"]
    deployment.verify_inventory = lambda _outputs: None
    verified: list[dict[str, str]] = []
    monkeypatch.setattr(deploy, "verify_deployment", lambda env: verified.append(dict(env)) or 0)

    deployment.apply("apply:plan-1:csa-wb-mvp1-rg")

    assert verified == [deployment.env]
