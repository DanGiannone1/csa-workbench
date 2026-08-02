"""Focused portable-instance contracts for deployment and Entra desired state."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER_LAUNCHER = """
import json, os, runpy, sys, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as directory:
    payload = Path(directory) / 'inventory.json'
    payload.write_text(json.dumps(dict(os.environ)), encoding='utf-8')
    sys.argv = ['infra/inventory_verifier.py', str(payload)]
    runpy.run_path('infra/inventory_verifier.py', run_name='__main__')
"""
SPEC = importlib.util.spec_from_file_location("entra", ROOT / "infra" / "entra.py")
assert SPEC and SPEC.loader
entra = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = entra
SPEC.loader.exec_module(entra)


class FakeGraph:
    def __init__(self) -> None:
        self.apps: list[dict[str, Any]] = []
        self.sps: list[dict[str, Any]] = []
        self.assignments: list[dict[str, Any]] = []
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.patches: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str) -> dict[str, Any]:
        if path.startswith("applications?"):
            display_name = unquote(path).split("displayName eq '", 1)[1].split("'", 1)[0]
            return {"value": [deepcopy(app) for app in self.apps if app["displayName"] == display_name]}
        if path.startswith("servicePrincipals?"):
            app_id = unquote(path).split("appId eq '", 1)[1].split("'", 1)[0]
            return {"value": [deepcopy(sp) for sp in self.sps if sp["appId"] == app_id]}
        if "/appRoleAssignedTo" in path:
            return {"value": deepcopy(self.assignments)}
        raise AssertionError(path)

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        self.posts.append((path, deepcopy(body)))
        if path == "applications":
            app = {**deepcopy(body), "id": f"object-{len(self.apps) + 1}", "appId": f"client-{len(self.apps) + 1}", "identifierUris": []}
            self.apps.append(app)
            return deepcopy(app)
        if path == "servicePrincipals":
            sp = {"id": f"sp-{len(self.sps) + 1}", "appId": body["appId"]}
            self.sps.append(sp)
            return deepcopy(sp)
        if path.endswith("/appRoleAssignedTo"):
            self.assignments.append(deepcopy(body))
            return deepcopy(body)
        raise AssertionError(path)

    def patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        self.patches.append((path, deepcopy(body)))
        app = next(item for item in self.apps if isinstance(item.get("id"), str) and path.endswith(item["id"]))
        app.update(deepcopy(body))
        return deepcopy(app)


def test_entra_creates_only_selected_instance_and_ignores_unsuffixed_legacy() -> None:
    graph = FakeGraph()
    graph.apps = [{"displayName": "CSA Workbench API"}, {"displayName": "CSA Workbench Web"}, {"displayName": "CSA Workbench Runtime"}]

    result = entra.ensure_entra(graph, "mvp1", "tenant", "https://frontend.example", "api-principal")

    names = entra.names_for_slug("mvp1")
    assert result.api_client_id == "client-4"
    assert {app["displayName"] for app in graph.apps} >= {names.web, names.api, names.runtime}
    assert len(graph.apps) == 6
    assert graph.assignments == [{"principalId": "api-principal", "resourceId": "sp-3", "appRoleId": entra.RUNTIME_ROLE_ID}]


def test_entra_fails_closed_for_duplicate_or_drifted_selected_registration_without_mutation() -> None:
    names = entra.names_for_slug("mvp1")
    graph = FakeGraph()
    graph.apps = [{"displayName": names.api}, {"displayName": names.api}]
    with pytest.raises(entra.GraphError, match="duplicate dedicated"):
        entra.ensure_entra(graph, "mvp1", "tenant", "https://frontend.example", "api-principal")
    assert graph.posts == [] and graph.patches == []

    graph = FakeGraph()
    created = entra.ensure_entra(graph, "mvp1", "tenant", "https://frontend.example", "api-principal")
    api = next(app for app in graph.apps if app["displayName"] == names.api)
    api["api"]["oauth2PermissionScopes"][0]["value"] = "drifted"
    before = (len(graph.posts), len(graph.patches))
    with pytest.raises(entra.GraphError, match="conflicting"):
        entra.ensure_entra(graph, "mvp1", "tenant", "https://frontend.example", "api-principal")
    assert (len(graph.posts), len(graph.patches)) == before
    assert created.api_client_id


@pytest.mark.parametrize("slug", ["ab", "Mvp1", "mvp-1", "mvp12345678"])
def test_entra_rejects_invalid_instance_slug_before_graph_mutation(slug: str) -> None:
    graph = FakeGraph()
    with pytest.raises(entra.GraphError, match="instance slug"):
        entra.ensure_entra(graph, slug, "tenant", "https://frontend.example", "api-principal")
    assert graph.posts == [] and graph.patches == []


def test_governance_nsg_is_instance_and_location_parameterized() -> None:
    spec = importlib.util.spec_from_file_location("governance_nsg", ROOT / "infra" / "governance_nsg.py")
    assert spec and spec.loader
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    aca, private, vnet = helper.expected_names("mvp1", "westus3")
    base = "/subscriptions/sub/resourceGroups/csa-wb-mvp1-rg/providers/Microsoft.Network"
    inventory = [
        {"name": aca, "id": f"{base}/networkSecurityGroups/{aca}", "location": "WestUS3", "provisioningState": "Succeeded", "securityRules": [], "networkInterfaces": None, "subnets": []},
        {"name": private, "id": f"{base}/networkSecurityGroups/{private}", "location": "WestUS3", "provisioningState": "Succeeded", "securityRules": [], "networkInterfaces": None, "subnets": [{"id": f"{base}/virtualNetworks/{vnet}/subnets/private-endpoints"}]},
    ]
    selected = helper.select_governance_nsgs(inventory, "sub", "csa-wb-mvp1-rg", "westus3", "mvp1")
    assert selected["aca_nsg_id"].endswith(aca)
    with pytest.raises(ValueError, match="inventory drifted"):
        helper.select_governance_nsgs(inventory, "sub", "csa-wb-other-rg", "westus3", "other")


def _write_command_stubs(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir, log = tmp_path / "bin", tmp_path / "az.log"
    bin_dir.mkdir(parents=True)
    helper = ROOT / "tests" / "fixtures" / "fake_deploy_cli.py"
    for command in ("git", "az"):
        if os.name == "nt":
            (bin_dir / f"{command}.cmd").write_text(
                f'@set FAKE_COMMAND={command}\n@"{sys.executable}" "{helper}" %*\n',
                encoding="utf-8",
            )
        else:
            launcher = bin_dir / command
            launcher.write_text(
                f'#!/usr/bin/env sh\nFAKE_COMMAND={command} exec "{sys.executable}" "{helper}" "$@"\n',
                encoding="utf-8",
            )
            launcher.chmod(0o755)
    return bin_dir, log


def _run_deploy(tmp_path: Path, *args: str, recovery: bool = False, bad_recovery: bool = False, recovery_apps_order: str = 'expected', recovery_profile: str = 'incompatible', overrides: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_dir, log = _write_command_stubs(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "AZ_LOG": str(log), "INSTANCE_SLUG": "mvp1",
        "FAKE_RECOVERY": "1" if recovery else "0", "FAKE_BAD_RECOVERY": "1" if bad_recovery else "0",
        "FAKE_RECOVERY_APPS": recovery_apps_order, "FAKE_RECOVERY_PROFILE": recovery_profile,
        "MODEL_DEPLOYMENT_NAME": "deployment", "MODEL_NAME": "model", "MODEL_VERSION": "2026-01-01",
        "MODEL_SKU_NAME": "GlobalStandard", "MODEL_CAPACITY": "30",
        "LEGACY_MODEL_DEPLOYMENT_NAME": "legacy-deployment", "LEGACY_MODEL_NAME": "legacy-model",
        "LEGACY_MODEL_VERSION": "2025-01-01", "LEGACY_MODEL_SKU_NAME": "GlobalStandard", "LEGACY_MODEL_CAPACITY": "10",
        "IDENTITY_MODE": "entra", "DEMO_PASSWORD": "",
        **(overrides or {}),
    }
    result = subprocess.run([sys.executable, "-m", "scripts.workbench", "deploy", *args], cwd=ROOT, env=env, text=True, capture_output=True)
    return result, log.read_text() if log.exists() else ""


def test_plan_requires_explicit_inputs_and_never_mutates(tmp_path: Path) -> None:
    result, log = _run_deploy(tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'PLAN_ID=' in result.stdout and 'CONFIRM=apply:' in result.stdout
    assert 'deployment sub what-if' in log
    assert '--result-format FullResourcePayloads' in log
    for forbidden in ('deployment sub create', 'containerapp delete', 'containerapp env delete', 'acr build', 'rest --method POST', 'rest --method PATCH', 'deployment group create'):
        assert forbidden not in log

    env = {**os.environ, "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}"}
    missing = subprocess.run([sys.executable, "-m", "scripts.workbench", "deploy"], cwd=ROOT, env=env, text=True, capture_output=True)
    assert missing.returncode != 0 and 'INSTANCE_SLUG is required' in missing.stderr
    whitespace, whitespace_log = _run_deploy(tmp_path / 'whitespace', overrides={'MODEL_NAME': 'bad model'})
    assert whitespace.returncode != 0 and 'MODEL_NAME must not contain whitespace' in whitespace.stderr
    assert whitespace_log == ''


def test_deployment_guidance_allows_an_explicitly_authorized_cli_agent_without_weakening_confirmation() -> None:
    deployment = (ROOT / 'docs' / 'guides' / 'deployment.md').read_text()
    agent_setup = (ROOT / 'docs' / 'guides' / 'coding-agents.md').read_text()
    deployment_text = ' '.join(deployment.split())
    agent_setup_text = ' '.join(agent_setup.split())

    assert 'Run apply only when the user requested deployment and the current plan matches that request' in deployment_text
    assert 'A plan-only request never permits deployment' in agent_setup_text
    assert 'Apply recomputes and checks the plan before changing Azure' in deployment_text
    assert 'Confirm the approved work record required by the' in deployment_text
    assert 'new deletion, target, security choice, or cost choice' in deployment_text
    assert "export MODEL_DEPLOYMENT_NAME='your-model-deployment-name'" in deployment
    assert "export IDENTITY_MODE='entra'" in deployment
    assert 'Demo mode also requires `DEMO_PASSWORD`' in deployment_text
    assert 'deploy verify --browser' in deployment
    assert 'obtains a delegated token' in deployment_text
    assert 'checks `/auth/me`' in deployment
    assert 'creates a session through the API' in deployment_text
    assert 'An unexpected application-owned resource causes the deployment check to fail' in deployment_text
    assert 'Defender-for-Storage Event Grid topic' not in deployment
    assert 'agent may use the exact confirmation printed by that plan' in agent_setup_text
    assert 'The agent must then stop' not in agent_setup
    assert 'an agent must never run apply' not in agent_setup


def test_malformed_or_stale_confirmation_cannot_mutate(tmp_path: Path) -> None:
    plan, _ = _run_deploy(tmp_path / "plan")
    plan_id = next(line.split("=", 1)[1] for line in plan.stdout.splitlines() if line.startswith("PLAN_ID="))
    malformed, malformed_log = _run_deploy(tmp_path / "malformed", "apply", "--confirm", "not-a-confirmation")
    assert malformed.returncode != 0
    assert 'create' not in malformed_log and 'delete' not in malformed_log
    stale, stale_log = _run_deploy(tmp_path / "stale", "apply", "--confirm", f"apply:{'0' * 64}:csa-wb-mvp1-rg")
    assert stale.returncode != 0
    assert 'create' not in stale_log and 'delete' not in stale_log
    assert len(plan_id) == 64


def test_confirmed_fresh_apply_skips_recovery_deletion_and_reaches_foundation_create(tmp_path: Path) -> None:
    plan, _ = _run_deploy(tmp_path / "plan")
    plan_id = next(line.split("=", 1)[1] for line in plan.stdout.splitlines() if line.startswith("PLAN_ID="))

    apply, log = _run_deploy(
        tmp_path / "apply", "apply", "--confirm", f"apply:{plan_id}:csa-wb-mvp1-rg",
    )

    assert apply.returncode != 0  # the stub stops at the first real foundation create
    assert "containerapp delete" not in log and "containerapp env delete" not in log
    assert "deployment sub what-if" in log
    assert "deployment sub create" in log


@pytest.mark.parametrize('overrides', [
    {'ACR_LOCATION': 'westus3'},
    {'IDENTITY_MODE': 'demo', 'DEMO_PASSWORD': 'different-demo-secret'},
])
def test_mutable_plan_configuration_change_invalidates_confirmation_without_mutation(tmp_path: Path, overrides: dict[str, str]) -> None:
    plan, _ = _run_deploy(tmp_path / 'plan')
    plan_id = next(line.split('=', 1)[1] for line in plan.stdout.splitlines() if line.startswith('PLAN_ID='))
    changed, log = _run_deploy(tmp_path / 'changed', 'apply', '--confirm', f'apply:{plan_id}:csa-wb-mvp1-rg', overrides=overrides)
    assert changed.returncode != 0
    assert 'create' not in log and 'delete' not in log


def test_entra_shape_redirect_and_runtime_assignment_contracts_are_idempotent_and_fail_closed() -> None:
    graph = FakeGraph(); names = entra.names_for_slug('mvp1')
    first = entra.ensure_entra(graph, 'mvp1', 'tenant', 'https://frontend.example', 'api-principal')
    post_count = len(graph.posts)
    assert entra.ensure_entra(graph, 'mvp1', 'tenant', 'https://frontend.example', 'api-principal') == first
    assert len(graph.posts) == post_count
    api = next(app for app in graph.apps if app['displayName'] == names.api)
    web = next(app for app in graph.apps if app['displayName'] == names.web)
    runtime = next(app for app in graph.apps if app['displayName'] == names.runtime)
    assert api['identifierUris'] == [f"api://{api['appId']}"] and runtime['identifierUris'] == [f"api://{runtime['appId']}"]
    assert {item['appId'] for item in api['api']['preAuthorizedApplications']} == {web['appId'], entra.AZURE_CLI_CLIENT_ID}
    entra.ensure_entra(graph, 'mvp1', 'tenant', 'https://new.example', 'api-principal')
    assert web['spa']['redirectUris'] == ['https://new.example']
    web['spa']['redirectUris'] = ['https://one.example', 'https://two.example']; before = (len(graph.posts), len(graph.patches))
    with pytest.raises(entra.GraphError, match='redirectUris'):
        entra.ensure_entra(graph, 'mvp1', 'tenant', 'https://third.example', 'api-principal')
    assert (len(graph.posts), len(graph.patches)) == before
    web['spa']['redirectUris'] = ['https://new.example']
    graph.assignments.append({'principalId': 'api-principal', 'resourceId': 'sp-3', 'appRoleId': entra.RUNTIME_ROLE_ID})
    with pytest.raises(entra.GraphError, match='duplicate runtime'):
        entra.ensure_entra(graph, 'mvp1', 'tenant', 'https://new.example', 'api-principal')


def test_runtime_audience_contract_requests_the_identifier_uri_and_checks_mise_claims() -> None:
    apps = (ROOT / 'infra' / 'apps.bicep').read_text()
    entra_source = (ROOT / 'infra' / 'entra.py').read_text()
    workload_auth = (ROOT / 'backend' / 'assistant' / 'src' / 'workbench_assistant' / 'workload_auth.py').read_text()
    session_manager = (ROOT / 'backend' / 'api' / 'src' / 'workbench_api' / 'session_manager.py').read_text()
    deploy = (ROOT / 'infra' / 'deploy.py').read_text()

    requested_resource = "api://${runtimeClientId}"
    assert f"{{ name: 'POOL_AUTH_AUDIENCE', value: '{requested_resource}' }}" in apps
    assert "{ name: 'WORKLOAD_ENTRA_AUDIENCE', value: runtimeClientId }" in apps
    assert 'expected = [f"api://{application[\'appId\']}"]' in entra_source
    assert 'claims["aud"] != self.config.audience' in workload_auth
    assert "name: 'mise-auth'" in apps
    assert "{ name: 'AzureAd__Audience', value: runtimeClientId }" in apps
    assert 'mcr.microsoft.com/entra-sdk/auth-sidecar@sha256:' in deploy
    assert 'f"miseSidecarImage={MISE_SIDECAR_IMAGE}"' in deploy
    assert 'os.getenv("POOL_AUTH_AUDIENCE", "").strip().rstrip("/")' in session_manager
    assert 'return f"{audience}/.default"' in session_manager


def test_python_authentication_has_no_direct_jwt_or_jwks_validation_path() -> None:
    sources = [
        (ROOT / 'backend' / 'api' / 'src' / 'workbench_api' / 'api_auth.py').read_text(),
        (ROOT / 'backend' / 'assistant' / 'src' / 'workbench_assistant' / 'workload_auth.py').read_text(),
        (ROOT / 'backend' / 'api' / 'pyproject.toml').read_text(),
        (ROOT / 'backend' / 'assistant' / 'pyproject.toml').read_text(),
    ]
    combined = '\n'.join(sources).lower()
    assert 'pyjwkclient' not in combined
    assert 'pyjwt' not in combined
    assert 'jwt.decode' not in combined


def test_deployment_what_if_replaces_only_the_operation_token_and_preserves_create_model_values(tmp_path: Path) -> None:
    result, log = _run_deploy(tmp_path, overrides={'MODEL_NAME': 'create'})

    assert result.returncode == 0, result.stderr
    foundation_preview = next(line for line in log.splitlines() if line.startswith('deployment sub what-if'))
    assert 'azureOpenAiModelName=create' in foundation_preview
    assert 'azureOpenAiModelName=what-if' not in foundation_preview

    deploy_source = (ROOT / 'infra' / 'deploy.py').read_text()
    assert 'preview[3] = "what-if"' in deploy_source
    assert 'self.deployment_what_if(foundation)' in deploy_source
    assert 'self.deployment_what_if(apps)' in deploy_source


def test_deployment_workflow_runs_the_canonical_host_suite_with_containerized_bicep() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'deploy.yml').read_text()
    package = json.loads((ROOT / 'package.json').read_text())
    verifier = (ROOT / 'scripts' / 'workbench.py').read_text()

    assert 'actions/setup-node@v4' in workflow
    assert "node-version: '22'" in workflow
    assert 'npm ci' in workflow and 'npm ci --prefix frontend' in workflow
    assert 'astral-sh/setup-uv@v6' in workflow
    assert 'uv sync --locked' in workflow
    assert 'uv sync --locked' in workflow
    assert 'session-container' not in workflow
    assert 'npm run verify:ci' in workflow
    assert 'azure/cli@v2' in workflow and 'az bicep build --file infra/foundation.bicep' in workflow
    assert 'pytest' not in workflow
    assert 'pip install pytest' not in workflow
    assert package['scripts']['verify:ci'] == 'uv run python -m scripts.workbench verify --skip-bicep --skip-waza'
    assert 'matrix:' in workflow and 'ubuntu-latest, windows-latest, macos-latest' in workflow
    assert 'with tempfile.TemporaryDirectory' in verifier


def test_ci_verifier_rejects_an_invalid_bicep_option_before_running_checks() -> None:
    result = subprocess.run([sys.executable, '-m', 'scripts.workbench', 'verify', '--skip-bicep=true'], cwd=ROOT, text=True, capture_output=True)

    assert result.returncode == 2
    assert 'ignored explicit argument' in result.stderr


def test_governance_nsg_rejects_extra_wrong_state_and_association() -> None:
    spec = importlib.util.spec_from_file_location('governance_nsg_cases', ROOT / 'infra' / 'governance_nsg.py'); assert spec and spec.loader
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    aca, private, vnet = helper.expected_names('mvp1', 'eastus2'); base = '/subscriptions/sub/resourceGroups/csa-wb-mvp1-rg/providers/Microsoft.Network'
    def item(name: str) -> dict[str, Any]: return {'name': name, 'id': f'{base}/networkSecurityGroups/{name}', 'location': 'eastus2', 'provisioningState': 'Succeeded', 'securityRules': [], 'networkInterfaces': None, 'subnets': []}
    good = [item(aca), item(private)]
    for bad in (good + [item('extra')], [{**item(aca), 'provisioningState': 'Failed'}, item(private)], [item(aca), {**item(private), 'subnets': [{'id': f'{base}/virtualNetworks/{vnet}/subnets/aca-infrastructure'}]}]):
        with pytest.raises(ValueError): helper.select_governance_nsgs(bad, 'sub', 'csa-wb-mvp1-rg', 'eastus2', 'mvp1')


def test_confirmed_recovery_deletes_only_ordered_targets_before_foundation_mutation(tmp_path: Path) -> None:
    plan, _ = _run_deploy(tmp_path / "plan", recovery=True)
    plan_id = next(line.split("=", 1)[1] for line in plan.stdout.splitlines() if line.startswith("PLAN_ID="))
    apply, log = _run_deploy(tmp_path / "apply", "apply", "--confirm", f"apply:{plan_id}:csa-wb-mvp1-rg", recovery=True)
    assert apply.returncode != 0  # the stub stops at the first foundation create
    actions = [line for line in log.splitlines() if 'containerapp delete' in line or 'containerapp env delete' in line or 'deployment sub what-if' in line or 'deployment sub create' in line]
    assert actions == [
        'containerapp delete -g csa-wb-mvp1-rg -n csa-wb-mvp1-frontend --yes --only-show-errors',
        'containerapp delete -g csa-wb-mvp1-rg -n csa-wb-mvp1-api --yes --only-show-errors',
        'containerapp delete -g csa-wb-mvp1-rg -n csa-wb-mvp1-runtime --yes --only-show-errors',
        'containerapp env delete -g csa-wb-mvp1-rg -n csa-wb-mvp1-env --yes --only-show-errors',
        next(action for action in actions if 'deployment sub what-if' in action),
        next(action for action in actions if 'deployment sub create' in action),
    ]


def test_recovery_accepts_expected_apps_in_any_azure_list_order(tmp_path: Path) -> None:
    result, log = _run_deploy(tmp_path, recovery=True, recovery_apps_order='reordered')

    assert result.returncode == 0, result.stderr
    assert '"recovery_state":"incompatible"' in result.stdout
    assert 'containerapp delete' not in log and 'containerapp env delete' not in log
    assert 'deployment sub what-if' not in log


def test_recovery_accepts_azure_enriched_compatible_consumption_profile(tmp_path: Path) -> None:
    result, log = _run_deploy(
        tmp_path,
        recovery=True,
        recovery_apps_order='missing',
        recovery_profile='azure-enriched',
    )

    assert result.returncode == 0, result.stderr
    assert '"recovery_state":"compatible"' in result.stdout
    assert 'containerapp delete' not in log and 'containerapp env delete' not in log
    assert 'deployment sub what-if' in log


def test_recovery_recreates_azure_shell_without_static_ingress_ip(tmp_path: Path) -> None:
    result, log = _run_deploy(tmp_path, recovery=True, recovery_profile='azure-shell')

    assert result.returncode == 0, result.stderr
    assert '"recovery_state":"incompatible"' in result.stdout
    assert '"recovery_deletion_targets":["containerapp/csa-wb-mvp1-frontend","containerapp/csa-wb-mvp1-api","containerapp/csa-wb-mvp1-runtime","managedEnvironment/csa-wb-mvp1-env"]' in result.stdout
    assert 'containerapp delete' not in log and 'containerapp env delete' not in log
    assert 'deployment sub what-if' not in log


def test_recovery_of_unattached_failed_environment_deletes_only_environment(tmp_path: Path) -> None:
    plan, _ = _run_deploy(tmp_path / 'plan', recovery=True, recovery_apps_order='missing')
    plan_id = next(line.split('=', 1)[1] for line in plan.stdout.splitlines() if line.startswith('PLAN_ID='))
    apply, log = _run_deploy(
        tmp_path / 'apply',
        'apply', '--confirm', f'apply:{plan_id}:csa-wb-mvp1-rg',
        recovery=True,
        recovery_apps_order='missing',
    )

    assert apply.returncode != 0  # the stub stops at the first foundation create
    assert 'containerapp delete' not in log
    assert 'containerapp env delete -g csa-wb-mvp1-rg -n csa-wb-mvp1-env --yes --only-show-errors' in log
    assert 'deployment sub what-if' in log and 'deployment sub create' in log


def test_recovery_rejects_extra_attached_apps_before_mutation(tmp_path: Path) -> None:
    result, log = _run_deploy(tmp_path, recovery=True, recovery_apps_order='extra')

    assert result.returncode != 0
    assert 'containerapp delete' not in log and 'containerapp env delete' not in log and 'deployment sub what-if' not in log


def test_malformed_recovery_inventory_fails_before_deletion_even_when_optimized(tmp_path: Path) -> None:
    for optimized in ('', '1'):
        result, log = _run_deploy(tmp_path / (optimized or 'normal'), recovery=True, bad_recovery=True, overrides={'PYTHONOPTIMIZE': optimized})
        assert result.returncode != 0
        assert 'containerapp delete' not in log and 'containerapp env delete' not in log and 'deployment sub what-if' not in log


def test_static_portable_contract_has_no_legacy_names_or_model_defaults() -> None:
    files = {path.name: path.read_text() for path in (ROOT / 'infra').glob('*') if path.suffix in {'.bicep', '.py', '.sh'}}
    source = '\n'.join(files.values()).lower()
    assert 'csa-workbench-rg' not in source and 'djgsharedacr' not in source
    assert "gpt-4.1" not in source and "gpt-5.6-terra" not in source
    assert "param azureopenaimodelname string" in files['platform.bicep'].lower()
    assert "param azureopenaimodelcapacity int" in files['platform.bicep'].lower()
    assert "param legacymodelname string" in files['platform.bicep'].lower()
    assert "param legacymodelcapacity int" in files['platform.bicep'].lower()
    assert "kind: 'AIServices'" in files['platform.bicep']
    assert "allowProjectManagement: true" in files['platform.bicep']
    assert files['platform.bicep'].count("publicNetworkAccess: 'Disabled'") == 3
    assert "privatelink.services.ai.azure.com" in files['platform.bicep']
    assert "openAiPrivateEndpointName: openAiPrivateEndpointName" in files['foundation.bicep']
    assert "enableAutomaticFailover: true" in files['platform.bicep']
    assert "param databaseName string" in files['apps.bicep']
    assert "param frontendIdentityId string" in files['apps.bicep']
    assert "param miseSidecarImage string" in files['apps.bicep']
    assert "azureOpenAiDeploymentName: azureOpenAiDeploymentName" in files['foundation.bicep']
    assert "legacyModelDeploymentName: legacyModelDeploymentName" in files['foundation.bicep']
    assert "foundryProjectName: foundryProjectName" in files['foundation.bicep']
    assert "{ name: 'AZURE_DEPLOYMENT', value: azureOpenAiDeployment }" in files['apps.bicep']
    assert "--instance-slug" in files['entra.py'] and "apply=true" not in files['deploy.sh'].lower()


def test_parameterized_verifier_rejects_cross_instance_identity_drift() -> None:
    verifier = VERIFIER_LAUNCHER
    slug = 'mvp1'
    sha = '0123456789abcdef0123456789abcdef01234567'
    apps = []
    for name, external, port, image in ((f'csa-wb-{slug}-frontend', True, 3000, 'csa-workbench-frontend'), (f'csa-wb-{slug}-api', True, 8000, 'csa-workbench-api'), (f'csa-wb-{slug}-runtime', False, 8080, 'csa-workbench-runtime')):
        container: dict[str, Any] = {'image': f'acr.azurecr.io/{image}:{sha}'}
        if name.endswith('runtime'):
            container['env'] = [{'name': 'AZURE_DEPLOYMENT', 'value': 'deployment'}, {'name': 'AZURE_ENDPOINT', 'value': 'https://ai/openai/v1/'}]
        apps.append({'name': name, 'properties': {'provisioningState': 'Succeeded', 'workloadProfileName': 'Consumption', 'configuration': {'ingress': {'external': external, 'targetPort': port, 'transport': 'auto'}}, 'template': {'scale': {'minReplicas': 0, 'maxReplicas': 1}, 'containers': [container]}}})
    env = {
        **os.environ,
        'APPS': json.dumps(apps), 'DEPLOYMENTS': json.dumps([{'name': 'deployment', 'properties': {'provisioningState': 'Succeeded', 'model': {'format': 'OpenAI', 'name': 'model', 'version': 'version'}} , 'sku': {'name': 'GlobalStandard', 'capacity': 30}}]),
        'IDENTITIES': json.dumps([{'name': 'csa-wb-other-frontend-identity'}]), 'RESOURCES': '[]', 'SYSTEM_TOPICS': '[]', 'SYSTEM_TOPIC_SUBSCRIPTIONS': '[]', 'ACR': '{}', 'AZURE_OPEN_AI': json.dumps({'properties': {'endpoint': 'https://ai/'}}), 'FOUNDRY_PROJECT': '{}', 'COSMOS': '{}', 'STORAGE': '{}', 'VNET': '{}', 'PRIVATE_ENDPOINTS': '[]', 'PRIVATE_DNS_ZONES': '[]', 'MANAGED_ENVIRONMENT': '{}', 'NETWORK_SECURITY_GROUPS': '[]', 'COSMOS_DNS_LINKS': '[]', 'STORAGE_DNS_LINKS': '[]', 'OPENAI_DNS_LINKS': '[]', 'COGNITIVE_SERVICES_DNS_LINKS': '[]', 'AI_SERVICES_DNS_LINKS': '[]', 'COSMOS_DNS_GROUPS': '[]', 'STORAGE_DNS_GROUPS': '[]', 'OPENAI_DNS_GROUPS': '[]', 'COSMOS_DNS_RECORDS': '[]', 'STORAGE_DNS_RECORDS': '[]', 'OPENAI_DNS_RECORDS': '[]', 'COGNITIVE_SERVICES_DNS_RECORDS': '[]', 'AI_SERVICES_DNS_RECORDS': '[]', 'ASSIGNMENTS': '[]', 'COSMOS_SQL_ASSIGNMENTS': '[]', 'APP_INSIGHTS': '{}', 'LOG_ANALYTICS': '{}',
        'FRONTEND_APP_NAME': f'csa-wb-{slug}-frontend', 'API_APP_NAME': f'csa-wb-{slug}-api', 'RUNTIME_APP_NAME': f'csa-wb-{slug}-runtime', 'FRONTEND_IDENTITY_NAME': f'csa-wb-{slug}-frontend-identity', 'API_IDENTITY_NAME': f'csa-wb-{slug}-api-identity', 'RUNTIME_IDENTITY_NAME': f'csa-wb-{slug}-runtime-identity', 'MODEL_DEPLOYMENT_NAME': 'deployment', 'MODEL_NAME': 'model', 'MODEL_VERSION': 'version', 'MODEL_SKU_NAME': 'GlobalStandard', 'MODEL_CAPACITY': '30', 'LEGACY_MODEL_DEPLOYMENT_NAME': 'legacy-deployment', 'LEGACY_MODEL_NAME': 'legacy-model', 'LEGACY_MODEL_VERSION': 'legacy-version', 'LEGACY_MODEL_SKU_NAME': 'GlobalStandard', 'LEGACY_MODEL_CAPACITY': '10', 'FOUNDRY_PROJECT_NAME': f'csa-wb-{slug}', 'SHA': sha, 'RESOURCE_GROUP': f'csa-wb-{slug}-rg', 'SUBSCRIPTION_ID': 'sub', 'ENVIRONMENT_NAME': f'csa-wb-{slug}-env', 'DATABASE_NAME': f'csa-wb-{slug}-entra', 'VNET_NAME': f'csa-wb-{slug}-vnet', 'COSMOS_ACCOUNT_NAME': 'cosmos', 'STORAGE_ACCOUNT_NAME': 'storage', 'ACR_NAME': 'acr', 'AOAI_NAME': 'ai', 'APP_INSIGHTS_NAME': f'csa-wb-{slug}-insights', 'LOG_ANALYTICS_NAME': f'csa-wb-{slug}-logs', 'COSMOS_PRIVATE_ENDPOINT_NAME': f'csa-wb-{slug}-cosmos-pe', 'STORAGE_PRIVATE_ENDPOINT_NAME': f'csa-wb-{slug}-storage-pe', 'OPENAI_PRIVATE_ENDPOINT_NAME': f'csa-wb-{slug}-openai-pe', 'COSMOS_PRIVATE_DNS_ZONE': 'privatelink.documents.azure.com', 'STORAGE_PRIVATE_DNS_ZONE': 'privatelink.blob.core.windows.net', 'OPENAI_PRIVATE_DNS_ZONE': 'privatelink.openai.azure.com', 'COGNITIVE_SERVICES_PRIVATE_DNS_ZONE': 'privatelink.cognitiveservices.azure.com', 'AI_SERVICES_PRIVATE_DNS_ZONE': 'privatelink.services.ai.azure.com', 'PRIVATE_DNS_VNET_LINK_NAME': f'csa-wb-{slug}-vnet-link', 'FRONTEND_PRINCIPAL': 'frontend', 'API_PRINCIPAL': 'api', 'RUNTIME_PRINCIPAL': 'runtime', 'LOCATION': 'eastus2',
    }
    result = subprocess.run([sys.executable, '-c', verifier], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert 'managed identity inventory drifted' in result.stderr


def _verifier_fixture() -> tuple[str, dict[str, str]]:
    code = VERIFIER_LAUNCHER; slug, sha, sub = 'mvp1', '0123456789abcdef0123456789abcdef01234567', 'sub'
    rg, base, vnet, cosmos, storage, acr, ai = f'csa-wb-{slug}-rg', f'csa-wb-{slug}', f'csa-wb-{slug}-vnet', 'cosmos', 'storage', 'acr', 'ai'
    root = f'/subscriptions/{sub}/resourceGroups/{rg}/providers'; ids = {k: f'{root}/Microsoft.ManagedIdentity/userAssignedIdentities/{base}-{k}-identity' for k in ('frontend','api','runtime')}
    principal = {'frontend':'frontend','api':'api','runtime':'runtime'}
    apps = []
    tenant_id, api_client_id, runtime_client_id = 'tenant', 'api-client-id', 'runtime-client-id'
    mise_image = 'mcr.microsoft.com/entra-sdk/auth-sidecar@sha256:fc4b3871adfacf41a46b3ad9e8cf619e59d58b39bf5b00dfe9ff13c1de140dd6'
    for kind, external, port, repo in [('frontend',True,3000,'csa-workbench-frontend'),('api',True,8000,'csa-workbench-api'),('runtime',False,8080,'csa-workbench-runtime')]:
        container = {'name': kind, 'image': f'acr.azurecr.io/{repo}:{sha}'}
        if kind == 'api': container['env'] = [
            {'name':'IDENTITY_MODE','value':'entra'}, {'name':'ENTRA_TENANT_ID','value':tenant_id},
            {'name':'ENTRA_API_CLIENT_ID','value':api_client_id}, {'name':'ENTRA_ALLOWED_AUDIENCES','value':f'api://{api_client_id}'},
            {'name':'POOL_AUTH_AUDIENCE','value':f'api://{runtime_client_id}'},
            {'name':'MISE_VALIDATION_ENDPOINT','value':'http://127.0.0.1:8081/Validate'},
            {'name':'APPLICATIONINSIGHTS_CONNECTION_STRING','value':'InstrumentationKey=fixture'},
        ]
        if kind == 'runtime': container['env'] = [
            {'name':'AZURE_DEPLOYMENT','value':'deployment'}, {'name':'AZURE_ENDPOINT','value':'https://ai/openai/v1/'},
            {'name':'WORKLOAD_AUTH_MODE','value':'entra'}, {'name':'WORKLOAD_ENTRA_TENANT_ID','value':tenant_id},
            {'name':'WORKLOAD_ENTRA_AUDIENCE','value':runtime_client_id}, {'name':'WORKLOAD_ENTRA_CALLER_OBJECT_ID','value':'api'},
            {'name':'WORKLOAD_ENTRA_REQUIRED_ROLE','value':'invoke'},
            {'name':'MISE_VALIDATION_ENDPOINT','value':'http://127.0.0.1:8081/Validate'},
            {'name':'APPLICATIONINSIGHTS_CONNECTION_STRING','value':'InstrumentationKey=fixture'},
        ]
        containers = [container]
        if kind in {'api', 'runtime'}:
            client_id = api_client_id if kind == 'api' else runtime_client_id
            authorization = {'AzureAd__Scopes':'access_as_user'} if kind == 'api' else {'AzureAd__Roles':'invoke'}
            sidecar_env = {
                'Kestrel__Endpoints__Http__Url':'http://127.0.0.1:8081', 'ASPNETCORE_ENVIRONMENT':'Production',
                'AzureAd__Instance':'https://login.microsoftonline.com/', 'AzureAd__TenantId':tenant_id,
                'AzureAd__ClientId':client_id, 'AzureAd__Audience':client_id,
                'Logging__LogLevel__Default':'Warning', 'Logging__LogLevel__Microsoft.Identity.Web':'Information', **authorization,
            }
            containers.append({'name':'mise-auth','image':mise_image,'resources':{'cpu':0.25,'memory':'0.5Gi','ephemeralStorage':'1Gi'},'env':[{'name':name,'value':value} for name,value in sidecar_env.items()]})
        apps.append({'name':f'{base}-{kind}','identity':{'userAssignedIdentities':{ids[kind]:{}}},'properties':{'provisioningState':'Succeeded','workloadProfileName':'Consumption','managedEnvironmentId':f'{root}/Microsoft.App/managedEnvironments/{base}-env','configuration':{'ingress':{'external':external,'targetPort':port,'transport':'auto'},'registries':[{'server':'acr.azurecr.io','identity':ids[kind]}]},'template':{'scale':{'minReplicas':0,'maxReplicas':1},'containers':containers}}})
    zones = ['privatelink.documents.azure.com','privatelink.blob.core.windows.net']; ai_zones = ['privatelink.openai.azure.com','privatelink.cognitiveservices.azure.com','privatelink.services.ai.azure.com']; endpoints = []
    for name, target, group, nic in [(f'{base}-cosmos-pe',f'{root}/Microsoft.DocumentDB/databaseAccounts/{cosmos}','Sql','nic1'),(f'{base}-storage-pe',f'{root}/Microsoft.Storage/storageAccounts/{storage}','blob','nic2'),(f'{base}-openai-pe',f'{root}/Microsoft.CognitiveServices/accounts/{ai}','account','nic3')]:
        endpoints.append({'name':name,'provisioningState':'Succeeded','subnet':{'id':f'{root}/Microsoft.Network/virtualNetworks/{vnet}/subnets/private-endpoints'},'networkInterfaces':[{'id':f'{root}/Microsoft.Network/networkInterfaces/{nic}'}],'privateLinkServiceConnections':[{'privateLinkServiceId':target,'groupIds':[group],'privateLinkServiceConnectionState':{'status':'Approved'}}]})
    def links(zone: str): return [{'name':f'{base}-vnet-link','provisioningState':'Succeeded','virtualNetworkLinkState':'Completed','registrationEnabled':False,'virtualNetwork':{'id':f'{root}/Microsoft.Network/virtualNetworks/{vnet}'}}]
    def groups(zone: str, names: list[str]): return [{'name':'default','provisioningState':'Succeeded','privateDnsZoneConfigs':[{'privateDnsZoneId':f'{root}/Microsoft.Network/privateDnsZones/{zone}','recordSets':[{'recordSetName':n,'ipAddresses':[f'10.42.0.{40+i}']} for i,n in enumerate(names)]}]}]
    cosmos_names=[cosmos,f'{cosmos}-eastus2']; storage_names=[storage]
    def records(names: list[str]): return [{'name':n,'aRecords':[{'ipv4Address':f'10.42.0.{40+i}'}]} for i,n in enumerate(names)]
    ai_group=[{'name':'default','provisioningState':'Succeeded','privateDnsZoneConfigs':[{'privateDnsZoneId':f'{root}/Microsoft.Network/privateDnsZones/{z}','recordSets':[{'recordSetName':ai,'ipAddresses':[f'10.42.0.{43+i}']}]} for i,z in enumerate(ai_zones)]}]
    def ai_records(offset: int): return [{'name':ai,'aRecords':[{'ipv4Address':f'10.42.0.{offset}'}]}]
    direct = [('microsoft.app/managedenvironments',f'{base}-env'),* [('microsoft.app/containerapps',f'{base}-{x}') for x in ('frontend','api','runtime')],* [('microsoft.managedidentity/userassignedidentities',f'{base}-{x}-identity') for x in ('frontend','api','runtime')],('microsoft.operationalinsights/workspaces',f'{base}-logs'),('microsoft.insights/components',f'{base}-insights'),('microsoft.containerregistry/registries',acr),('microsoft.cognitiveservices/accounts',ai),('microsoft.documentdb/databaseaccounts',cosmos),('microsoft.storage/storageaccounts',storage),('microsoft.network/virtualnetworks',vnet),('microsoft.network/privateendpoints',f'{base}-cosmos-pe'),('microsoft.network/privateendpoints',f'{base}-storage-pe'),('microsoft.network/privateendpoints',f'{base}-openai-pe'),* [('microsoft.network/privatednszones',z) for z in zones+ai_zones],('microsoft.network/networkinterfaces','nic1'),('microsoft.network/networkinterfaces','nic2'),('microsoft.network/networkinterfaces','nic3')]
    children=[('microsoft.documentdb/databaseaccounts/sqldatabases',f'{cosmos}/{base}-entra'),('microsoft.documentdb/databaseaccounts/sqldatabases/containers',f'{cosmos}/{base}-entra/appstate'),('microsoft.cognitiveservices/accounts/deployments',f'{ai}/deployment'),('microsoft.cognitiveservices/accounts/deployments',f'{ai}/legacy-deployment'),('microsoft.cognitiveservices/accounts/projects',f'{ai}/{base}'),* [('microsoft.network/privatednszones/virtualnetworklinks',f'{z}/{base}-vnet-link') for z in zones+ai_zones],('microsoft.network/privateendpoints/privatednszonegroups',f'{base}-cosmos-pe/default'),('microsoft.network/privateendpoints/privatednszonegroups',f'{base}-storage-pe/default'),('microsoft.network/privateendpoints/privatednszonegroups',f'{base}-openai-pe/default'),('microsoft.storage/storageaccounts/blobservices',f'{storage}/default'),('microsoft.storage/storageaccounts/blobservices/containers',f'{storage}/default/engagement-artifacts')]
    scope = f'/subscriptions/{sub}/resourceGroups/{rg}/'; roles=[]
    for p in ('frontend','api','runtime'): roles.append({'scope':f'{scope}providers/Microsoft.ContainerRegistry/registries/{acr}','roleDefinitionName':'AcrPull','principalId':principal[p]})
    roles += [{'scope':f'{scope}providers/Microsoft.Storage/storageAccounts/{storage}','roleDefinitionName':'Storage Blob Data Contributor','principalId':'api'},{'scope':f'{scope}providers/Microsoft.CognitiveServices/accounts/{ai}','roleDefinitionName':'Cognitive Services OpenAI User','principalId':'runtime'}]
    cscope=f'{scope}providers/Microsoft.DocumentDB/databaseAccounts/{cosmos}'; croles=[{'roleDefinitionId':f'{cscope}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002','scope':cscope,'principalId':p} for p in ('api','runtime')]
    env={**os.environ,'APPS':json.dumps(apps),'DEPLOYMENTS':json.dumps([{'name':'deployment','properties':{'provisioningState':'Succeeded','model':{'format':'OpenAI','name':'model','version':'version'}},'sku':{'name':'GlobalStandard','capacity':30}},{'name':'legacy-deployment','properties':{'provisioningState':'Succeeded','model':{'format':'OpenAI','name':'legacy-model','version':'legacy-version'}},'sku':{'name':'GlobalStandard','capacity':10}}]),'IDENTITIES':json.dumps([{'name':f'{base}-{k}-identity','id':ids[k]} for k in ('frontend','api','runtime')]),'RESOURCES':json.dumps([{'type':t,'name':n} for t,n in direct+children]),'SYSTEM_TOPICS':'[]','SYSTEM_TOPIC_SUBSCRIPTIONS':'[]','APP_INSIGHTS':json.dumps({'name':f'{base}-insights','properties':{'provisioningState':'Succeeded','WorkspaceResourceId':f'{root}/Microsoft.OperationalInsights/workspaces/{base}-logs','IngestionMode':'LogAnalytics','ConnectionString':'InstrumentationKey=fixture'}}),'LOG_ANALYTICS':json.dumps({'name':f'{base}-logs','properties':{'provisioningState':'Succeeded','sku':{'name':'PerGB2018'},'retentionInDays':30}}),'APP_INSIGHTS_NAME':f'{base}-insights','LOG_ANALYTICS_NAME':f'{base}-logs','ACR':json.dumps({'name':acr,'sku':{'name':'Basic'},'adminUserEnabled':False}),'AZURE_OPEN_AI':json.dumps({'name':ai,'kind':'AIServices','sku':{'name':'S0'},'properties':{'disableLocalAuth':True,'allowProjectManagement':True,'publicNetworkAccess':'Disabled','endpoint':'https://ai/'}}),'FOUNDRY_PROJECT':json.dumps({'name':f'{ai}/{base}','properties':{'provisioningState':'Succeeded'}}),'COSMOS':json.dumps({'disableLocalAuth':True,'publicNetworkAccess':'Disabled','enableAutomaticFailover':True}),'STORAGE':json.dumps({'publicNetworkAccess':'Disabled','allowSharedKeyAccess':False,'allowBlobPublicAccess':False}),'VNET':json.dumps({'name':vnet,'addressSpace':{'addressPrefixes':['10.42.0.0/24']},'subnets':[{'name':'aca-infrastructure','addressPrefix':'10.42.0.0/27'},{'name':'private-endpoints','addressPrefix':'10.42.0.32/27','privateEndpointNetworkPolicies':'Disabled'}]}),'PRIVATE_ENDPOINTS':json.dumps(endpoints),'PRIVATE_DNS_ZONES':json.dumps([{'name':z} for z in zones+ai_zones]),'MANAGED_ENVIRONMENT':json.dumps({'name':f'{base}-env','properties':{'vnetConfiguration':{'infrastructureSubnetId':f'{root}/Microsoft.Network/virtualNetworks/{vnet}/subnets/aca-infrastructure'}}}),'NETWORK_SECURITY_GROUPS':'[]','COSMOS_DNS_LINKS':json.dumps(links(zones[0])),'STORAGE_DNS_LINKS':json.dumps(links(zones[1])),'OPENAI_DNS_LINKS':json.dumps(links(ai_zones[0])),'COGNITIVE_SERVICES_DNS_LINKS':json.dumps(links(ai_zones[1])),'AI_SERVICES_DNS_LINKS':json.dumps(links(ai_zones[2])),'COSMOS_DNS_GROUPS':json.dumps(groups(zones[0],cosmos_names)),'STORAGE_DNS_GROUPS':json.dumps(groups(zones[1],storage_names)),'OPENAI_DNS_GROUPS':json.dumps(ai_group),'COSMOS_DNS_RECORDS':json.dumps(records(cosmos_names)),'STORAGE_DNS_RECORDS':json.dumps(records(storage_names)),'OPENAI_DNS_RECORDS':json.dumps(ai_records(43)),'COGNITIVE_SERVICES_DNS_RECORDS':json.dumps(ai_records(44)),'AI_SERVICES_DNS_RECORDS':json.dumps(ai_records(45)),'ASSIGNMENTS':json.dumps([roles]),'COSMOS_SQL_ASSIGNMENTS':json.dumps(croles),'FRONTEND_APP_NAME':f'{base}-frontend','API_APP_NAME':f'{base}-api','RUNTIME_APP_NAME':f'{base}-runtime','FRONTEND_IDENTITY_NAME':f'{base}-frontend-identity','API_IDENTITY_NAME':f'{base}-api-identity','RUNTIME_IDENTITY_NAME':f'{base}-runtime-identity','MODEL_DEPLOYMENT_NAME':'deployment','MODEL_NAME':'model','MODEL_VERSION':'version','MODEL_SKU_NAME':'GlobalStandard','MODEL_CAPACITY':'30','LEGACY_MODEL_DEPLOYMENT_NAME':'legacy-deployment','LEGACY_MODEL_NAME':'legacy-model','LEGACY_MODEL_VERSION':'legacy-version','LEGACY_MODEL_SKU_NAME':'GlobalStandard','LEGACY_MODEL_CAPACITY':'10','FOUNDRY_PROJECT_NAME':base,'SHA':sha,'RESOURCE_GROUP':rg,'SUBSCRIPTION_ID':sub,'ENVIRONMENT_NAME':f'{base}-env','DATABASE_NAME':f'{base}-entra','VNET_NAME':vnet,'COSMOS_ACCOUNT_NAME':cosmos,'STORAGE_ACCOUNT_NAME':storage,'ACR_NAME':acr,'AOAI_NAME':ai,'COSMOS_PRIVATE_ENDPOINT_NAME':f'{base}-cosmos-pe','STORAGE_PRIVATE_ENDPOINT_NAME':f'{base}-storage-pe','OPENAI_PRIVATE_ENDPOINT_NAME':f'{base}-openai-pe','COSMOS_PRIVATE_DNS_ZONE':zones[0],'STORAGE_PRIVATE_DNS_ZONE':zones[1],'OPENAI_PRIVATE_DNS_ZONE':ai_zones[0],'COGNITIVE_SERVICES_PRIVATE_DNS_ZONE':ai_zones[1],'AI_SERVICES_PRIVATE_DNS_ZONE':ai_zones[2],'PRIVATE_DNS_VNET_LINK_NAME':f'{base}-vnet-link','FRONTEND_PRINCIPAL':'frontend','API_PRINCIPAL':'api','RUNTIME_PRINCIPAL':'runtime','LOCATION':'eastus2','IDENTITY_MODE':'entra','TENANT_ID':tenant_id,'API_CLIENT_ID':api_client_id,'RUNTIME_CLIENT_ID':runtime_client_id,'MISE_SIDECAR_IMAGE':mise_image}
    return code, env


def test_portable_verifier_accepts_complete_fixture_and_rejects_wiring_roles_and_inventory() -> None:
    code, env = _verifier_fixture()
    assert subprocess.run([sys.executable,'-c',code],env=env,text=True,capture_output=True).returncode == 0
    cases = [('APPS', lambda value: value.replace('acr.azurecr.io/csa-workbench-frontend:', 'wrong/')), ('COSMOS_DNS_RECORDS', lambda value: value.replace('10.42.0.40','10.42.0.99')), ('COSMOS_DNS_GROUPS', lambda value: value.replace('["10.42.0.40"]', '[{"ipAddress":"10.42.0.40"}]')), ('RESOURCES', lambda value: value[:-1]+',{"type":"Microsoft.Search/searchServices","name":"extra"}]'), ('ASSIGNMENTS', lambda value: value[:-2]+',{"scope":"/subscriptions/sub/resourceGroups/csa-wb-mvp1-rg/providers/Microsoft.Storage/storageAccounts/storage","roleDefinitionName":"Reader","principalId":"api"}]]'), ('COSMOS_SQL_ASSIGNMENTS', lambda value: value[:-1]+',{"roleDefinitionId":"x","scope":"x","principalId":"api"}]')]
    for key, mutate in cases:
        changed={**env,key:mutate(env[key])}; assert subprocess.run([sys.executable,'-c',code],env=changed,text=True,capture_output=True).returncode != 0


def test_portable_verifier_rejects_malformed_or_duplicate_container_profiles() -> None:
    code, env = _verifier_fixture()

    malformed = json.loads(env['APPS'])
    next(app for app in malformed if app['name'].endswith('-runtime'))['properties']['template']['containers'].append('not-a-container')
    result = subprocess.run(
        [sys.executable, '-c', code], env={**env, 'APPS': json.dumps(malformed)},
        text=True, capture_output=True,
    )
    assert result.returncode != 0 and 'Container App identity, registry, or profile drifted' in result.stderr

    duplicate_env = json.loads(env['APPS'])
    sidecar = next(app for app in duplicate_env if app['name'].endswith('-runtime'))['properties']['template']['containers'][1]
    sidecar['env'].append(dict(sidecar['env'][0]))
    result = subprocess.run(
        [sys.executable, '-c', code], env={**env, 'APPS': json.dumps(duplicate_env)},
        text=True, capture_output=True,
    )
    assert result.returncode != 0 and 'Microsoft identity sidecar environment profile drifted' in result.stderr

    duplicate_container = json.loads(env['APPS'])
    containers = next(app for app in duplicate_container if app['name'].endswith('-runtime'))['properties']['template']['containers']
    containers.append(deepcopy(containers[1]))
    result = subprocess.run(
        [sys.executable, '-c', code], env={**env, 'APPS': json.dumps(duplicate_container)},
        text=True, capture_output=True,
    )
    assert result.returncode != 0 and 'Container App identity, registry, or profile drifted' in result.stderr


def test_portable_verifier_accepts_azure_sidecar_resource_projection_and_rejects_drift() -> None:
    code, env = _verifier_fixture()
    assert subprocess.run([sys.executable, '-c', code], env=env, text=True, capture_output=True).returncode == 0

    apps = json.loads(env['APPS'])
    sidecar = next(app for app in apps if app['name'].endswith('-runtime'))['properties']['template']['containers'][1]
    sidecar['resources']['ephemeralStorage'] = '2Gi'
    result = subprocess.run(
        [sys.executable, '-c', code], env={**env, 'APPS': json.dumps(apps)},
        text=True, capture_output=True,
    )
    assert result.returncode != 0 and 'Microsoft identity sidecar profile drifted' in result.stderr


@pytest.mark.parametrize("app_suffix,variable,bad_value,error", [
    ('-api', 'IDENTITY_MODE', 'demo', 'API identity binding drifted'),
    ('-api', 'ENTRA_TENANT_ID', 'wrong-tenant', 'API identity binding drifted'),
    ('-api', 'ENTRA_API_CLIENT_ID', 'wrong-api', 'API identity binding drifted'),
    ('-runtime', 'WORKLOAD_ENTRA_TENANT_ID', 'wrong-tenant', 'runtime workload identity binding drifted'),
    ('-runtime', 'WORKLOAD_ENTRA_AUDIENCE', 'wrong-runtime', 'runtime workload identity binding drifted'),
    ('-runtime', 'WORKLOAD_ENTRA_CALLER_OBJECT_ID', 'wrong-caller', 'runtime workload identity binding drifted'),
    ('-runtime', 'WORKLOAD_ENTRA_REQUIRED_ROLE', 'wrong-role', 'runtime workload identity binding drifted'),
    ('-api', 'APPLICATIONINSIGHTS_CONNECTION_STRING', 'InstrumentationKey=wrong', 'Application Insights trace binding drifted'),
    ('-runtime', 'APPLICATIONINSIGHTS_CONNECTION_STRING', 'InstrumentationKey=wrong', 'Application Insights trace binding drifted'),
])
def test_portable_verifier_rejects_main_authentication_binding_drift(
    app_suffix: str, variable: str, bad_value: str, error: str,
) -> None:
    code, env = _verifier_fixture()
    apps = json.loads(env['APPS'])
    app = next(item for item in apps if item['name'].endswith(app_suffix))
    main = app['properties']['template']['containers'][0]
    next(item for item in main['env'] if item['name'] == variable)['value'] = bad_value

    result = subprocess.run(
        [sys.executable, '-c', code], env={**env, 'APPS': json.dumps(apps)},
        text=True, capture_output=True,
    )
    assert result.returncode != 0 and error in result.stderr


def test_portable_verifier_accepts_only_demo_api_without_a_sidecar_and_with_secret_binding() -> None:
    code, env = _verifier_fixture()
    apps = json.loads(env['APPS'])
    api = next(app for app in apps if app['name'].endswith('-api'))
    containers = api['properties']['template']['containers']
    containers[:] = [container for container in containers if container['name'] == 'api']
    api_env = containers[0]['env']
    api_env[:] = [entry for entry in api_env if entry['name'] != 'MISE_VALIDATION_ENDPOINT']
    next(entry for entry in api_env if entry['name'] == 'IDENTITY_MODE')['value'] = 'demo'
    api_env.append({'name': 'DEMO_PASSWORD', 'secretRef': 'demo-password'})
    demo_env = {**env, 'IDENTITY_MODE': 'demo', 'APPS': json.dumps(apps)}
    assert subprocess.run([sys.executable, '-c', code], env=demo_env, text=True, capture_output=True).returncode == 0

    api_env.pop()
    result = subprocess.run(
        [sys.executable, '-c', code], env={**demo_env, 'APPS': json.dumps(apps)},
        text=True, capture_output=True,
    )
    assert result.returncode != 0 and 'demo API identity binding drifted' in result.stderr

def test_portable_verifier_requires_cosmos_automatic_failover() -> None:
    code, env = _verifier_fixture()
    cosmos = json.loads(env['COSMOS'])
    cosmos['enableAutomaticFailover'] = False

    result = subprocess.run(
        [sys.executable, '-c', code],
        env={**env, 'COSMOS': json.dumps(cosmos)},
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert 'Cosmos authentication/network/failover profile drifted' in result.stderr


def test_portable_verifier_accepts_only_the_defender_storage_antimalware_system_topic() -> None:
    code, env = _verifier_fixture()
    topic_name = 'storage-47dbe5dc-3d2f-4736-ad2c-acfe9ba9fd18'
    source = '/subscriptions/sub/resourceGroups/csa-wb-mvp1-rg/providers/Microsoft.Storage/storageAccounts/storage'
    topic = {
        'name': topic_name,
        'provisioningState': 'Succeeded',
        'source': source,
        'topicType': 'Microsoft.Storage.StorageAccounts',
    }
    subscription = {
        'name': 'StorageAntimalwareSubscription',
        'provisioningState': 'Succeeded',
        'destination': {
            'endpointType': 'WebHook',
            'endpointBaseUrl': 'https://eastus2.a3.storageav.azure.com:5142/EventCapture/sub/storage',
            'aadApplication': 'f1f8da5f-609a-401d-85b2-d498116b7265',
            'aadTenant': '33e01921-4d64-4f8c-a055-5bdaffd5e33d',
            'maxEventsPerBatch': 1,
            'preferredBatchSizeInKilobytes': 64,
            'deliveryAttributeMappings': None,
        },
        'eventDeliverySchema': 'EventGridSchema',
        'filter': {
            'advancedFilters': [{'key': 'data.blobType', 'operatorType': 'StringContains', 'values': ['BlockBlob']}],
            'enableAdvancedFilteringOnArrays': None,
            'includedEventTypes': ['Microsoft.Storage.BlobCreated', 'Microsoft.Storage.BlobRenamed'],
            'isSubjectCaseSensitive': None,
            'subjectBeginsWith': '',
            'subjectEndsWith': '',
        },
        'retryPolicy': {'eventTimeToLiveInMinutes': 1440, 'maxDeliveryAttempts': 30},
        'deadLetterDestination': None,
        'deadLetterWithResourceIdentity': None,
        'deliveryWithResourceIdentity': None,
        'expirationTimeUtc': None,
        'labels': None,
    }
    resources = json.loads(env['RESOURCES']) + [
        {'type': 'Microsoft.EventGrid/systemTopics', 'name': topic_name},
    ]
    governed = {
        **env,
        'SYSTEM_TOPICS': json.dumps([topic]),
        'SYSTEM_TOPIC_SUBSCRIPTIONS': json.dumps([subscription]),
        'RESOURCES': json.dumps(resources),
    }

    assert subprocess.run([sys.executable, '-c', code], env=governed, text=True, capture_output=True).returncode == 0

    invalid_cases: list[dict[str, str]] = [
        {**governed, 'SYSTEM_TOPICS': json.dumps([{**topic, 'source': source.replace('/storage', '/other')}])},
        {**governed, 'SYSTEM_TOPICS': json.dumps([{**topic, 'name': 'storage-not-a-uuid'}])},
        {**governed, 'SYSTEM_TOPICS': json.dumps([{**topic, 'topicType': 'Microsoft.Storage.Other'}])},
        {**governed, 'SYSTEM_TOPICS': json.dumps([{**topic, 'provisioningState': 'Failed'}])},
        {**governed, 'SYSTEM_TOPICS': json.dumps([topic, topic])},
        {**governed, 'RESOURCES': env['RESOURCES']},
        {**governed, 'SYSTEM_TOPICS': '[]', 'SYSTEM_TOPIC_SUBSCRIPTIONS': '[]'},
        {**governed, 'SYSTEM_TOPIC_SUBSCRIPTIONS': '[]'},
        {**governed, 'SYSTEM_TOPIC_SUBSCRIPTIONS': json.dumps([subscription, subscription])},
    ]
    subscription_mutations = [
        lambda value: value.__setitem__('name', 'OtherSubscription'),
        lambda value: value.__setitem__('provisioningState', 'Failed'),
        lambda value: value['destination'].__setitem__('endpointType', 'Queue'),
        lambda value: value['destination'].__setitem__('endpointBaseUrl', 'https://attacker.invalid/capture'),
        lambda value: value['destination'].__setitem__('aadApplication', 'wrong-app'),
        lambda value: value['destination'].__setitem__('aadTenant', 'wrong-tenant'),
        lambda value: value.__setitem__('eventDeliverySchema', 'CloudEventSchemaV1_0'),
        lambda value: value['filter'].__setitem__('includedEventTypes', ['Microsoft.Storage.BlobDeleted']),
        lambda value: value['retryPolicy'].__setitem__('maxDeliveryAttempts', 1),
    ]
    for mutate in subscription_mutations:
        changed_subscription = deepcopy(subscription)
        mutate(changed_subscription)
        invalid_cases.append({**governed, 'SYSTEM_TOPIC_SUBSCRIPTIONS': json.dumps([changed_subscription])})
    for changed in invalid_cases:
        assert subprocess.run([sys.executable, '-c', code], env=changed, text=True, capture_output=True).returncode != 0


def test_portable_verifier_normalizes_only_known_azure_container_app_defaults() -> None:
    code, env = _verifier_fixture()
    apps = json.loads(env['APPS'])
    for app in apps:
        app['properties']['template']['scale'].update({'cooldownPeriod': 300, 'pollingInterval': 30, 'rules': None})
        registry = app['properties']['configuration']['registries'][0]
        registry.update({'username': '', 'passwordSecretRef': ''})
        registry['identity'] = registry['identity'].replace('/resourceGroups/', '/resourcegroups/')
        assigned = app['identity']['userAssignedIdentities']
        app['identity']['userAssignedIdentities'] = {key.replace('/resourceGroups/', '/resourcegroups/'): value for key, value in assigned.items()}
    enriched = {**env, 'APPS': json.dumps(apps)}

    assert subprocess.run([sys.executable, '-c', code], env=enriched, text=True, capture_output=True).returncode == 0
    for mutate in (
        lambda values: values[0]['properties']['template']['scale'].__setitem__('cooldownPeriod', 301),
        lambda values: values[0]['properties']['configuration']['registries'][0].__setitem__('username', 'local-user'),
        lambda values: values[0]['properties']['template']['scale'].__setitem__('unexpected', False),
        lambda values: values[0]['properties']['template']['scale'].__setitem__('minReplicas', False),
        lambda values: values[0]['identity'].__setitem__('userAssignedIdentities', list(values[0]['identity']['userAssignedIdentities'])),
    ):
        changed = json.loads(json.dumps(apps)); mutate(changed)
        assert subprocess.run([sys.executable, '-c', code], env={**env, 'APPS': json.dumps(changed)}, text=True, capture_output=True).returncode != 0


def test_portable_verifier_accepts_only_the_optional_governance_nsg_resource_pair() -> None:
    code, env = _verifier_fixture()
    vnet = 'csa-wb-mvp1-vnet'
    names = [f'{vnet}-aca-infrastructure-nsg-eastus2', f'{vnet}-private-endpoints-nsg-eastus2']
    network_security_groups = [
        {'name': name, 'provisioningState': 'Succeeded', 'securityRules': [], 'networkInterfaces': None}
        for name in names
    ]
    resources = json.loads(env['RESOURCES']) + [
        {'type': 'Microsoft.Network/networkSecurityGroups', 'name': name}
        for name in names
    ]
    governed = {**env, 'NETWORK_SECURITY_GROUPS': json.dumps(network_security_groups), 'RESOURCES': json.dumps(resources)}

    assert subprocess.run([sys.executable, '-c', code], env=governed, text=True, capture_output=True).returncode == 0
    unrelated = {**governed, 'RESOURCES': json.dumps(resources + [{'type': 'Microsoft.Search/searchServices', 'name': 'extra'}])}
    assert subprocess.run([sys.executable, '-c', code], env=unrelated, text=True, capture_output=True).returncode != 0
    extra_nsg = {'name': 'unrelated', 'provisioningState': 'Succeeded', 'securityRules': [], 'networkInterfaces': None}
    assert subprocess.run([sys.executable, '-c', code], env={**governed, 'NETWORK_SECURITY_GROUPS': json.dumps(network_security_groups + [extra_nsg]), 'RESOURCES': json.dumps(resources + [{'type': 'Microsoft.Network/networkSecurityGroups', 'name': 'unrelated'}])}, text=True, capture_output=True).returncode != 0
    for malformed in ('null', '{}', 'false', '0', '""'):
        assert subprocess.run([sys.executable, '-c', code], env={**env, 'NETWORK_SECURITY_GROUPS': malformed}, text=True, capture_output=True).returncode != 0


def test_evaluator_runbooks_are_copyable_on_windows_macos_and_linux() -> None:
    development = (ROOT / 'docs' / 'guides' / 'local-development.md').read_text()
    evaluator = (ROOT / 'testing' / 'agent-evals.md').read_text()

    for value in ('## Run the assistant evaluation', '## Run the browser journey', 'PowerShell on Windows', 'Terminal on macOS or Linux', '$env:CSA_LOCAL_RUN_ID', 'export CSA_LOCAL_RUN_ID', "MVP_APP_URL='http://localhost:13000'", "MVP_API_URL='http://localhost:18000'", "MVP_RAW_TRACE_ROOT='.local-runs/demo1/logs/sdk-events'", 'uv run python -m scripts.workbench eval mvp', 'uv run python -m scripts.workbench eval playwright'):
        assert value in development
    for value in ('## Running it', 'PowerShell on Windows', 'Terminal on macOS or Linux', '$env:MVP_RESULTS', 'export MVP_RESULTS', 'uv run python -m scripts.workbench eval mvp', 'uv run python -m scripts.workbench eval foundry'):
        assert value in evaluator


def test_acr_build_context_rules_include_frontend_source_and_exclude_generated_content() -> None:
    root_rules = {
        line for line in (ROOT / '.dockerignore').read_text().splitlines()
        if line and not line.startswith('#')
    }
    frontend_rules = {
        line for line in (ROOT / 'frontend' / '.dockerignore').read_text().splitlines()
        if line and not line.startswith('#')
    }
    dockerfile = (ROOT / 'frontend' / 'Dockerfile').read_text()
    deployment = (ROOT / 'infra' / 'deploy.py').read_text()

    assert 'frontend' not in root_rules
    assert {
        'evidence', '.local-runs', '.mvp-artifacts', 'incoming', '.claude', '.venv',
        'node_modules', 'frontend/node_modules', 'frontend/.next*', 'frontend/.env*',
    } <= root_rules
    assert {'.next*', 'node_modules', '.env*'} <= frontend_rules
    assert not any(rule.endswith('/') for rule in root_rules | frontend_rules)
    assert 'docker build -f frontend/Dockerfile .' in dockerfile
    assert 'COPY frontend/package.json frontend/package-lock.json* ./' in dockerfile
    assert 'COPY frontend/ ./' in dockerfile
    assert 'COPY . .' not in dockerfile
    assert '"-f", "frontend/Dockerfile", "."' in deployment
