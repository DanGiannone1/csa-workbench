"""Guarded, cross-platform Azure deployment for one CSA Workbench instance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping, Sequence

from infra.governance_nsg import select_governance_nsgs
from scripts.host_commands import command_for_host

ROOT = Path(__file__).resolve().parent.parent
MISE_SIDECAR_IMAGE = "mcr.microsoft.com/entra-sdk/auth-sidecar@sha256:fc4b3871adfacf41a46b3ad9e8cf619e59d58b39bf5b00dfe9ff13c1de140dd6"


class DeploymentError(RuntimeError):
    """A guarded deployment precondition failed."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        raise DeploymentError(f"{name} is required")
    return value


def _model_value(env: Mapping[str, str], name: str, maximum: int) -> str:
    value = _required(env, name)
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise DeploymentError(f"{name} must not contain whitespace or control characters")
    if len(value) > maximum:
        raise DeploymentError(f"{name} exceeds maximum length {maximum}")
    return value


def _capacity(env: Mapping[str, str], name: str) -> int:
    raw = _required(env, name)
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        raise DeploymentError(f"{name} must be a positive integer")
    value = int(raw)
    if value > 1_000_000:
        raise DeploymentError(f"{name} exceeds maximum 1000000")
    return value


def _flag(env: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    value = raw.lower()
    if value not in {"true", "false"}:
        raise DeploymentError(f"{name} must be 'true' or 'false'")
    return value == "true"


class Deployment:
    """Own the plan/apply policy and all Azure subprocess calls."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        source = os.environ if env is None else env
        self.env = dict(source)
        self.slug = _required(source, "INSTANCE_SLUG")
        if not re.fullmatch(r"[a-z][a-z0-9]{2,9}", self.slug):
            raise DeploymentError("INSTANCE_SLUG must match ^[a-z][a-z0-9]{2,9}$")

        self.model_deployment_name = _model_value(source, "MODEL_DEPLOYMENT_NAME", 64)
        self.model_name = _model_value(source, "MODEL_NAME", 128)
        self.model_version = _model_value(source, "MODEL_VERSION", 128)
        self.model_sku_name = _model_value(source, "MODEL_SKU_NAME", 64)
        self.model_capacity = _capacity(source, "MODEL_CAPACITY")
        legacy_names = (
            "LEGACY_MODEL_DEPLOYMENT_NAME", "LEGACY_MODEL_NAME", "LEGACY_MODEL_VERSION",
            "LEGACY_MODEL_SKU_NAME", "LEGACY_MODEL_CAPACITY",
        )
        self.enable_legacy_model = _flag(
            source, "ENABLE_LEGACY_MODEL", default=any(source.get(name, "") for name in legacy_names),
        )
        if self.enable_legacy_model:
            self.legacy_model_deployment_name = _model_value(source, "LEGACY_MODEL_DEPLOYMENT_NAME", 64)
            self.legacy_model_name = _model_value(source, "LEGACY_MODEL_NAME", 128)
            self.legacy_model_version = _model_value(source, "LEGACY_MODEL_VERSION", 128)
            self.legacy_model_sku_name = _model_value(source, "LEGACY_MODEL_SKU_NAME", 64)
            self.legacy_model_capacity = _capacity(source, "LEGACY_MODEL_CAPACITY")
            if self.legacy_model_deployment_name == self.model_deployment_name:
                raise DeploymentError("LEGACY_MODEL_DEPLOYMENT_NAME must differ from MODEL_DEPLOYMENT_NAME")
        else:
            self.legacy_model_deployment_name = ""
            self.legacy_model_name = ""
            self.legacy_model_version = ""
            self.legacy_model_sku_name = ""
            self.legacy_model_capacity = 1

        self.location = source.get("LOCATION", "eastus2")
        self.acr_location = source.get("ACR_LOCATION", self.location)
        self.identity_mode = source.get("IDENTITY_MODE", "entra")
        self.demo_password = source.get("DEMO_PASSWORD", "")
        if self.identity_mode not in {"entra", "demo"}:
            raise DeploymentError("IDENTITY_MODE must be 'entra' or 'demo'")
        if self.identity_mode == "demo" and not self.demo_password:
            raise DeploymentError("DEMO_PASSWORD is required when IDENTITY_MODE=demo")

        self.base = f"csa-wb-{self.slug}"
        self.resource_group = f"{self.base}-rg"
        self.environment_name = f"{self.base}-env"
        self.frontend_app_name = f"{self.base}-frontend"
        self.api_app_name = f"{self.base}-api"
        self.runtime_app_name = f"{self.base}-runtime"
        self.frontend_identity_name = f"{self.base}-frontend-identity"
        self.api_identity_name = f"{self.base}-api-identity"
        self.runtime_identity_name = f"{self.base}-runtime-identity"
        self.vnet_name = f"{self.base}-vnet"
        self.cosmos_private_endpoint_name = f"{self.base}-cosmos-pe"
        self.storage_private_endpoint_name = f"{self.base}-storage-pe"
        self.openai_private_endpoint_name = f"{self.base}-openai-pe"
        self.private_dns_vnet_link_name = f"{self.base}-vnet-link"
        self.database_name = f"{self.base}-entra"
        self.enable_foundry_project = _flag(source, "ENABLE_FOUNDRY_PROJECT")
        self.foundry_project_name = source.get("FOUNDRY_PROJECT_NAME", self.base)
        if any(character.isspace() or ord(character) < 32 for character in self.foundry_project_name) or len(self.foundry_project_name) > 64:
            raise DeploymentError("FOUNDRY_PROJECT_NAME must be a non-whitespace value of at most 64 characters")
        self.log_analytics_name = f"{self.base}-logs"
        self.app_insights_name = f"{self.base}-insights"
        self.cosmos_private_dns_zone = "privatelink.documents.azure.com"
        self.storage_private_dns_zone = "privatelink.blob.core.windows.net"
        self.openai_private_dns_zone = "privatelink.openai.azure.com"
        self.cognitive_services_private_dns_zone = "privatelink.cognitiveservices.azure.com"
        self.ai_services_private_dns_zone = "privatelink.services.ai.azure.com"

        self.tenant_id = ""
        self.subscription_id = ""
        self.sha = ""
        self.recovery_state = ""
        self.recovery_environment_id = ""
        self.recovery_deletion_targets: list[str] = []
        self.aca_nsg_id = ""
        self.private_endpoint_nsg_id = ""

    @staticmethod
    def require_tools() -> None:
        missing = [name for name in ("az", "git") if shutil.which(name) is None]
        if missing:
            raise DeploymentError(f"required command not found: {missing[0]}")

    def execute(
        self,
        command: Sequence[str],
        *,
        capture: bool = False,
        quiet: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        values = command_for_host(command)
        return subprocess.run(
            values, cwd=ROOT, env=self.env, text=True, check=True,
            capture_output=capture,
            stdout=subprocess.DEVNULL if quiet and not capture else None,
        )

    def output(self, command: Sequence[str]) -> str:
        return self.execute(command, capture=True).stdout.strip()

    def json_output(self, command: Sequence[str]) -> object:
        return json.loads(self.output(command))

    def validate_account_and_revision(self) -> None:
        try:
            self.execute(["az", "account", "show", "--only-show-errors"], quiet=True)
        except subprocess.CalledProcessError as exc:
            raise DeploymentError("sign in with az login before continuing") from exc
        self.tenant_id = self.output(["az", "account", "show", "--query", "tenantId", "-o", "tsv"])
        self.subscription_id = self.output(["az", "account", "show", "--query", "id", "-o", "tsv"])
        if not self.tenant_id or not self.subscription_id:
            raise DeploymentError("current Azure account must provide tenant and subscription IDs")
        self.sha = self.output(["git", "rev-parse", "HEAD"])
        if not re.fullmatch(r"[0-9a-f]{40}", self.sha):
            raise DeploymentError("deployment requires a full 40-character Git SHA")
        if self.output(["git", "status", "--porcelain"]):
            raise DeploymentError("deployment requires a clean worktree so images and SHA agree")
        try:
            self.execute(["az", "bicep", "version"], quiet=True)
        except subprocess.CalledProcessError as exc:
            raise DeploymentError("Azure CLI Bicep support is required") from exc

    def governance_preflight(self) -> None:
        exists = self.output(["az", "group", "exists", "-n", self.resource_group, "-o", "tsv"])
        if exists == "true":
            inventory = self.json_output(["az", "network", "nsg", "list", "-g", self.resource_group, "-o", "json"])
        elif exists == "false":
            inventory = []
        else:
            raise DeploymentError("resource group existence check returned an invalid value")
        try:
            selected = select_governance_nsgs(
                inventory, self.subscription_id, self.resource_group, self.location, self.slug,
            )
        except (TypeError, ValueError) as exc:
            raise DeploymentError("tenant-governance NSG preflight failed") from exc
        self.aca_nsg_id = selected["aca_nsg_id"]
        self.private_endpoint_nsg_id = selected["private_endpoint_nsg_id"]

    def recovery_preflight(self) -> None:
        exists = self.output(["az", "group", "exists", "-n", self.resource_group, "-o", "tsv"])
        if exists == "false":
            self.recovery_state, self.recovery_deletion_targets = "absent", []
            return
        if exists != "true":
            raise DeploymentError("resource group existence check returned an invalid value")

        environments = self.json_output(["az", "containerapp", "env", "list", "-g", self.resource_group, "-o", "json"])
        if not isinstance(environments, list) or any(not isinstance(item, dict) for item in environments):
            raise DeploymentError("Container Apps environment inventory validation failed")
        matches = [item for item in environments if item.get("name") == self.environment_name]
        if len(matches) > 1:
            raise DeploymentError("Container Apps environment inventory validation failed")
        if not matches:
            self.recovery_state, self.recovery_deletion_targets = "absent", []
            return
        environment_id = matches[0].get("id")
        if not isinstance(environment_id, str) or not environment_id:
            raise DeploymentError("Container Apps environment inventory validation failed")
        self.recovery_environment_id = environment_id

        environment = self.json_output(["az", "containerapp", "env", "show", "-g", self.resource_group, "-n", self.environment_name, "-o", "json"])
        apps = self.json_output(["az", "containerapp", "list", "-g", self.resource_group, "-o", "json"])
        if not isinstance(environment, dict) or environment.get("name") != self.environment_name or not isinstance(apps, list):
            raise DeploymentError("recovery inventory is malformed")
        if any(
            not isinstance(app, dict)
            or not isinstance(app.get("name"), str)
            or not isinstance(app.get("properties", {}).get("managedEnvironmentId"), str)
            for app in apps
        ):
            raise DeploymentError("recovery app inventory is malformed")
        attached = [
            app["name"] for app in apps
            if app["properties"]["managedEnvironmentId"].rstrip("/").lower() == environment_id.rstrip("/").lower()
        ]
        if len(attached) != len(set(attached)):
            raise DeploymentError("recovery app inventory has duplicate names")

        properties = environment.get("properties", {})
        profiles = properties.get("workloadProfiles") if isinstance(properties, dict) else None
        vnet = properties.get("vnetConfiguration", {}) if isinstance(properties, dict) else {}
        subnet = vnet.get("infrastructureSubnetId") if isinstance(vnet, dict) else None
        expected_subnet = (
            f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/providers/"
            f"Microsoft.Network/virtualNetworks/{self.vnet_name}/subnets/aca-infrastructure"
        )
        profile_compatible = (
            isinstance(profiles, list) and len(profiles) == 1 and isinstance(profiles[0], dict)
            and profiles[0].get("name") == "Consumption"
            and profiles[0].get("workloadProfileType") == "Consumption"
            and set(profiles[0]) <= {"name", "workloadProfileType", "enableFips"}
            and profiles[0].get("enableFips") in (None, False)
        )
        spec_compatible = isinstance(subnet, str) and subnet.lower() == expected_subnet.lower() and profile_compatible
        healthy = (
            spec_compatible and properties.get("provisioningState") == "Succeeded"
            and isinstance(properties.get("staticIp"), str) and bool(properties["staticIp"].strip())
        )
        expected_apps = [self.frontend_app_name, self.api_app_name, self.runtime_app_name]
        if healthy:
            self.recovery_state, self.recovery_deletion_targets = "compatible", []
        elif not attached or set(attached) == set(expected_apps):
            targets = [f"containerapp/{name}" for name in expected_apps if name in attached]
            targets.append(f"managedEnvironment/{self.environment_name}")
            self.recovery_state, self.recovery_deletion_targets = "incompatible", targets
        else:
            raise DeploymentError("incompatible environment app inventory is unsafe")

    def make_plan(self) -> tuple[dict[str, object], str]:
        self.validate_account_and_revision()
        self.governance_preflight()
        self.recovery_preflight()
        payload: dict[str, object] = {
            "schema": "csa-workbench-portable-plan-v3",
            "tenant_id": self.tenant_id,
            "subscription_id": self.subscription_id,
            "instance_slug": self.slug,
            "resource_group": self.resource_group,
            "location": self.location,
            "git_sha": self.sha,
            "acr_location": self.acr_location,
            "identity_mode": self.identity_mode,
            "demo_password_sha256": hashlib.sha256(self.demo_password.encode()).hexdigest(),
            "mise_sidecar_image": MISE_SIDECAR_IMAGE,
            "model_deployment_name": self.model_deployment_name,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_sku_name": self.model_sku_name,
            "model_capacity": self.model_capacity,
            "enable_legacy_model": self.enable_legacy_model,
            "legacy_model_deployment_name": self.legacy_model_deployment_name,
            "legacy_model_name": self.legacy_model_name,
            "legacy_model_version": self.legacy_model_version,
            "legacy_model_sku_name": self.legacy_model_sku_name,
            "legacy_model_capacity": self.legacy_model_capacity,
            "enable_foundry_project": self.enable_foundry_project,
            "foundry_project_name": self.foundry_project_name,
            "entra_display_names": [
                f"CSA Workbench [{self.slug}] Web",
                f"CSA Workbench [{self.slug}] API",
                f"CSA Workbench [{self.slug}] Runtime",
            ],
            "recovery_state": self.recovery_state,
            "recovery_deletion_targets": self.recovery_deletion_targets,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return payload, hashlib.sha256(canonical.encode()).hexdigest()

    def foundation_command(self) -> list[str]:
        self.foundation_deployment_name = f"{self.base}-foundation-{self.sha[:12]}"
        return [
            "az", "deployment", "sub", "create", "--name", self.foundation_deployment_name,
            "--location", self.location, "--template-file", "infra/foundation.bicep", "--parameters",
            f"instanceSlug={self.slug}", f"location={self.location}", f"acrLocation={self.acr_location}",
            f"azureOpenAiDeploymentName={self.model_deployment_name}", f"azureOpenAiModelName={self.model_name}",
            f"azureOpenAiModelVersion={self.model_version}", f"azureOpenAiModelSkuName={self.model_sku_name}",
            f"azureOpenAiModelCapacity={self.model_capacity}", f"enableFoundryProject={str(self.enable_foundry_project).lower()}",
            f"foundryProjectName={self.foundry_project_name}", f"enableLegacyModel={str(self.enable_legacy_model).lower()}",
            f"legacyModelDeploymentName={self.legacy_model_deployment_name}", f"legacyModelName={self.legacy_model_name}",
            f"legacyModelVersion={self.legacy_model_version}", f"legacyModelSkuName={self.legacy_model_sku_name}",
            f"legacyModelCapacity={self.legacy_model_capacity}", f"acaInfrastructureNsgId={self.aca_nsg_id}",
            f"privateEndpointNsgId={self.private_endpoint_nsg_id}",
        ]

    def deployment_what_if(self, command: Sequence[str]) -> None:
        preview = list(command)
        if len(preview) < 4 or preview[:2] != ["az", "deployment"] or preview[2] not in {"sub", "group"} or preview[3] != "create":
            raise DeploymentError("invalid Azure deployment command for what-if")
        preview[3] = "what-if"
        self.execute([*preview, "--result-format", "FullResourcePayloads", "--only-show-errors"])

    def delete_approved_recovery_targets(self) -> None:
        if self.recovery_state != "incompatible":
            return
        allowed = [
            f"containerapp/{self.frontend_app_name}", f"containerapp/{self.api_app_name}",
            f"containerapp/{self.runtime_app_name}", f"managedEnvironment/{self.environment_name}",
        ]
        targets = self.recovery_deletion_targets
        if not targets or len(targets) != len(set(targets)) or targets != [target for target in allowed if target in targets] or targets[-1] != allowed[-1]:
            raise DeploymentError("recovery deletion targets are not an approved ordered subset")
        for target in targets:
            kind, name = target.split("/", 1)
            if kind == "containerapp":
                self.execute(["az", "containerapp", "delete", "-g", self.resource_group, "-n", name, "--yes", "--only-show-errors"])
            elif target == allowed[-1]:
                self.execute(["az", "containerapp", "env", "delete", "-g", self.resource_group, "-n", name, "--yes", "--only-show-errors"])
            else:
                raise DeploymentError(f"unapproved recovery deletion target: {target}")

    def foundation_output(self, name: str) -> str:
        return self.output([
            "az", "deployment", "sub", "show", "--name", self.foundation_deployment_name,
            "--query", f"properties.outputs.{name}.value", "-o", "tsv",
        ])

    def _apps_command(self, values: Mapping[str, str]) -> list[str]:
        return [
            "az", "deployment", "group", "create", "-g", self.resource_group,
            "--name", f"{self.base}-apps-{self.sha[:12]}", "--template-file", "infra/apps.bicep", "--parameters",
            f"environmentName={self.environment_name}", f"acrServer={values['acr_server']}", f"imageTag={self.sha}",
            f"frontendAppName={self.frontend_app_name}", f"apiAppName={self.api_app_name}", f"runtimeAppName={self.runtime_app_name}",
            f"frontendIdentityId={values['frontend_identity_id']}", f"apiIdentityId={values['api_identity_id']}",
            f"runtimeIdentityId={values['runtime_identity_id']}", f"tenantId={self.tenant_id}",
            f"apiClientId={values['api_client_id']}", f"runtimeClientId={values['runtime_client_id']}",
            f"miseSidecarImage={MISE_SIDECAR_IMAGE}", f"frontendUrl={values['frontend_url']}",
            f"runtimeFqdn={values['runtime_fqdn']}", f"cosmosAccountName={values['cosmos_account_name']}",
            f"storageAccountName={values['storage_account_name']}", f"databaseName={self.database_name}",
            f"azureOpenAiEndpoint={values['aoai_endpoint'].rstrip('/')}/openai/v1/",
            f"azureOpenAiDeployment={self.model_deployment_name}", f"identityMode={self.identity_mode}",
            f"demoPassword={self.demo_password}", f"appInsightsConnectionString={values['app_insights_connection_string']}",
        ]

    def _inventory(self, values: Mapping[str, str]) -> dict[str, str]:
        def j(command: Sequence[str]) -> str:
            value = self.output(command)
            json.loads(value)
            return value

        rg = ["-g", self.resource_group]
        system_topics = j(["az", "eventgrid", "system-topic", "list", *rg, "--query", "[].{name:name,provisioningState:provisioningState,source:source,topicType:topicType}", "-o", "json"])
        topics = json.loads(system_topics)
        if not isinstance(topics, list) or len(topics) > 1 or any(not isinstance(topic, dict) for topic in topics):
            raise DeploymentError("tenant-managed Event Grid system topic inventory drifted")
        topic_name = "" if not topics else topics[0].get("name", "")
        subscriptions = "[]"
        if topic_name:
            subscriptions = j(["az", "eventgrid", "system-topic", "event-subscription", "list", *rg, "--system-topic-name", topic_name, "--query", "[].{name:name,provisioningState:provisioningState,destination:{endpointType:destination.endpointType,endpointBaseUrl:destination.endpointBaseUrl,aadApplication:destination.azureActiveDirectoryApplicationIdOrUri,aadTenant:destination.azureActiveDirectoryTenantId,maxEventsPerBatch:destination.maxEventsPerBatch,preferredBatchSizeInKilobytes:destination.preferredBatchSizeInKilobytes,deliveryAttributeMappings:destination.deliveryAttributeMappings},eventDeliverySchema:eventDeliverySchema,filter:filter,retryPolicy:retryPolicy,deadLetterDestination:deadLetterDestination,deadLetterWithResourceIdentity:deadLetterWithResourceIdentity,deliveryWithResourceIdentity:deliveryWithResourceIdentity,expirationTimeUtc:expirationTimeUtc,labels:labels}", "-o", "json"])
        frontend_principal = self.output(["az", "identity", "show", *rg, "-n", self.frontend_identity_name, "--query", "principalId", "-o", "tsv"])
        api_principal = self.output(["az", "identity", "show", *rg, "-n", self.api_identity_name, "--query", "principalId", "-o", "tsv"])
        runtime_principal = self.output(["az", "identity", "show", *rg, "-n", self.runtime_identity_name, "--query", "principalId", "-o", "tsv"])
        assignments = [
            json.loads(j(["az", "role", "assignment", "list", "--assignee", principal, "--all", "-o", "json"]))
            for principal in (frontend_principal, api_principal, runtime_principal)
        ]
        resources = j(["az", "resource", "list", *rg, "-o", "json"])
        resource_items = json.loads(resources)
        smart_detection_action_group = "null"
        if any(
            isinstance(resource, dict)
            and resource.get("type", "").lower() == "microsoft.insights/actiongroups"
            and resource.get("name", "").lower() == "application insights smart detection"
            for resource in resource_items
        ):
            smart_detection_action_group = j([
                "az", "resource", "show", *rg, "-n", "Application Insights Smart Detection",
                "--resource-type", "Microsoft.Insights/ActionGroups", "--query",
                "{name:name,type:type,location:location,properties:{enabled:properties.enabled,groupShortName:properties.groupShortName,armRoleReceivers:properties.armRoleReceivers,automationRunbookReceivers:properties.automationRunbookReceivers,azureAppPushReceivers:properties.azureAppPushReceivers,azureFunctionReceivers:properties.azureFunctionReceivers,emailReceivers:properties.emailReceivers,eventHubReceivers:properties.eventHubReceivers,itsmReceivers:properties.itsmReceivers,logicAppReceivers:properties.logicAppReceivers,smsReceivers:properties.smsReceivers,voiceReceivers:properties.voiceReceivers,webhookReceivers:properties.webhookReceivers}}",
                "-o", "json",
            ])
        zones = {
            "COSMOS": self.cosmos_private_dns_zone, "STORAGE": self.storage_private_dns_zone,
            "OPENAI": self.openai_private_dns_zone, "COGNITIVE_SERVICES": self.cognitive_services_private_dns_zone,
            "AI_SERVICES": self.ai_services_private_dns_zone,
        }
        payload = {
            "APPS": j(["az", "containerapp", "list", *rg, "-o", "json"]),
            "DEPLOYMENTS": j(["az", "cognitiveservices", "account", "deployment", "list", *rg, "-n", values["aoai_name"], "-o", "json"]),
            "IDENTITIES": j(["az", "identity", "list", *rg, "-o", "json"]),
            "RESOURCES": resources, "SMART_DETECTION_ACTION_GROUP": smart_detection_action_group,
            "SYSTEM_TOPICS": system_topics, "SYSTEM_TOPIC_SUBSCRIPTIONS": subscriptions,
            "APP_INSIGHTS": j(["az", "resource", "show", *rg, "-n", self.app_insights_name, "--resource-type", "Microsoft.Insights/components", "-o", "json"]),
            "LOG_ANALYTICS": j(["az", "resource", "show", *rg, "-n", self.log_analytics_name, "--resource-type", "Microsoft.OperationalInsights/workspaces", "-o", "json"]),
            "ACR": j(["az", "acr", "show", *rg, "-n", values["acr_name"], "-o", "json"]),
            "AZURE_OPEN_AI": j(["az", "cognitiveservices", "account", "show", *rg, "-n", values["aoai_name"], "-o", "json"]),
            "FOUNDRY_PROJECT": (
                j(["az", "resource", "show", "--ids", f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/providers/Microsoft.CognitiveServices/accounts/{values['aoai_name']}/projects/{self.foundry_project_name}", "-o", "json"])
                if self.enable_foundry_project else "null"
            ),
            "COSMOS": j(["az", "cosmosdb", "show", *rg, "-n", values["cosmos_account_name"], "-o", "json"]),
            "STORAGE": j(["az", "storage", "account", "show", *rg, "-n", values["storage_account_name"], "-o", "json"]),
            "VNET": j(["az", "network", "vnet", "show", *rg, "-n", self.vnet_name, "-o", "json"]),
            "PRIVATE_ENDPOINTS": j(["az", "network", "private-endpoint", "list", *rg, "-o", "json"]),
            "PRIVATE_DNS_ZONES": j(["az", "network", "private-dns", "zone", "list", *rg, "-o", "json"]),
            "MANAGED_ENVIRONMENT": j(["az", "containerapp", "env", "show", *rg, "-n", self.environment_name, "-o", "json"]),
            "NETWORK_SECURITY_GROUPS": j(["az", "network", "nsg", "list", *rg, "-o", "json"]),
            "COSMOS_DNS_GROUPS": j(["az", "network", "private-endpoint", "dns-zone-group", "list", *rg, "--endpoint-name", self.cosmos_private_endpoint_name, "-o", "json"]),
            "STORAGE_DNS_GROUPS": j(["az", "network", "private-endpoint", "dns-zone-group", "list", *rg, "--endpoint-name", self.storage_private_endpoint_name, "-o", "json"]),
            "OPENAI_DNS_GROUPS": j(["az", "network", "private-endpoint", "dns-zone-group", "list", *rg, "--endpoint-name", self.openai_private_endpoint_name, "-o", "json"]),
            "ASSIGNMENTS": json.dumps(assignments, separators=(",", ":")),
            "COSMOS_SQL_ASSIGNMENTS": j(["az", "cosmosdb", "sql", "role", "assignment", "list", *rg, "-a", values["cosmos_account_name"], "-o", "json"]),
        }
        for key, zone in zones.items():
            payload[f"{key}_DNS_LINKS"] = j(["az", "network", "private-dns", "link", "vnet", "list", *rg, "--zone-name", zone, "-o", "json"])
            payload[f"{key}_DNS_RECORDS"] = j(["az", "network", "private-dns", "record-set", "a", "list", *rg, "-z", zone, "-o", "json"])
        payload.update(self._inventory_config(values, frontend_principal, api_principal, runtime_principal))
        return payload

    def _inventory_config(self, values: Mapping[str, str], frontend_principal: str, api_principal: str, runtime_principal: str) -> dict[str, str]:
        return {
            "FRONTEND_APP_NAME": self.frontend_app_name, "API_APP_NAME": self.api_app_name, "RUNTIME_APP_NAME": self.runtime_app_name,
            "FRONTEND_IDENTITY_NAME": self.frontend_identity_name, "API_IDENTITY_NAME": self.api_identity_name, "RUNTIME_IDENTITY_NAME": self.runtime_identity_name,
            "MODEL_DEPLOYMENT_NAME": self.model_deployment_name, "MODEL_NAME": self.model_name, "MODEL_VERSION": self.model_version,
            "MODEL_SKU_NAME": self.model_sku_name, "MODEL_CAPACITY": str(self.model_capacity),
            "LEGACY_MODEL_DEPLOYMENT_NAME": self.legacy_model_deployment_name, "LEGACY_MODEL_NAME": self.legacy_model_name,
            "LEGACY_MODEL_VERSION": self.legacy_model_version, "LEGACY_MODEL_SKU_NAME": self.legacy_model_sku_name,
            "LEGACY_MODEL_CAPACITY": str(self.legacy_model_capacity), "ENABLE_LEGACY_MODEL": str(self.enable_legacy_model).lower(),
            "FOUNDRY_PROJECT_NAME": self.foundry_project_name, "ENABLE_FOUNDRY_PROJECT": str(self.enable_foundry_project).lower(),
            "SHA": self.sha, "RESOURCE_GROUP": self.resource_group, "SUBSCRIPTION_ID": self.subscription_id,
            "ENVIRONMENT_NAME": self.environment_name, "DATABASE_NAME": self.database_name, "VNET_NAME": self.vnet_name,
            "COSMOS_ACCOUNT_NAME": values["cosmos_account_name"], "STORAGE_ACCOUNT_NAME": values["storage_account_name"],
            "ACR_NAME": values["acr_name"], "AOAI_NAME": values["aoai_name"], "APP_INSIGHTS_NAME": self.app_insights_name,
            "LOG_ANALYTICS_NAME": self.log_analytics_name, "COSMOS_PRIVATE_ENDPOINT_NAME": self.cosmos_private_endpoint_name,
            "STORAGE_PRIVATE_ENDPOINT_NAME": self.storage_private_endpoint_name, "OPENAI_PRIVATE_ENDPOINT_NAME": self.openai_private_endpoint_name,
            "COSMOS_PRIVATE_DNS_ZONE": self.cosmos_private_dns_zone, "STORAGE_PRIVATE_DNS_ZONE": self.storage_private_dns_zone,
            "OPENAI_PRIVATE_DNS_ZONE": self.openai_private_dns_zone, "COGNITIVE_SERVICES_PRIVATE_DNS_ZONE": self.cognitive_services_private_dns_zone,
            "AI_SERVICES_PRIVATE_DNS_ZONE": self.ai_services_private_dns_zone, "PRIVATE_DNS_VNET_LINK_NAME": self.private_dns_vnet_link_name,
            "FRONTEND_PRINCIPAL": frontend_principal, "API_PRINCIPAL": api_principal, "RUNTIME_PRINCIPAL": runtime_principal,
            "LOCATION": self.location, "IDENTITY_MODE": self.identity_mode, "TENANT_ID": self.tenant_id,
            "API_CLIENT_ID": values["api_client_id"], "RUNTIME_CLIENT_ID": values["runtime_client_id"],
            "MISE_SIDECAR_IMAGE": MISE_SIDECAR_IMAGE,
        }

    def verify_inventory(self, values: Mapping[str, str]) -> None:
        inventory = self._inventory(values)
        with tempfile.TemporaryDirectory(prefix="csa-workbench-inventory-") as temporary:
            payload = Path(temporary) / "inventory.json"
            payload.write_text(json.dumps(inventory), encoding="utf-8")
            self.execute([sys.executable, "infra/inventory_verifier.py", str(payload)])

    def apply(self, confirmation: str) -> None:
        payload, plan_id = self.make_plan()
        expected = f"apply:{plan_id}:{self.resource_group}"
        if confirmation != expected:
            raise DeploymentError(f"confirmation does not match current plan; expected {expected}")
        payload, plan_id = self.make_plan()
        if confirmation != f"apply:{plan_id}:{self.resource_group}":
            raise DeploymentError("confirmation is stale after preflight recomputation")

        foundation = self.foundation_command()
        self.delete_approved_recovery_targets()
        self.deployment_what_if(foundation)
        self.execute([*foundation, "--only-show-errors"], quiet=True)
        outputs = {
            key: self.foundation_output(output) for key, output in {
                "environment_domain": "environmentDefaultDomain", "acr_server": "acrLoginServer", "acr_name": "acrName",
                "aoai_name": "azureOpenAiName", "aoai_endpoint": "azureOpenAiEndpoint", "frontend_identity_id": "frontendIdentityId",
                "api_identity_id": "apiIdentityId", "runtime_identity_id": "runtimeIdentityId", "api_principal_id": "apiIdentityPrincipalId",
                "cosmos_account_name": "cosmosAccountName", "storage_account_name": "storageAccountName",
                "app_insights_connection_string": "appInsightsConnectionString",
            }.items()
        }
        if any(not value for value in outputs.values()):
            raise DeploymentError("foundation deployment did not return required outputs")
        outputs["frontend_url"] = f"https://{self.frontend_app_name}.{outputs['environment_domain']}"
        outputs["api_url"] = f"https://{self.api_app_name}.{outputs['environment_domain']}"
        outputs["runtime_fqdn"] = f"{self.runtime_app_name}.internal.{outputs['environment_domain']}"

        entra = json.loads(self.output([
            sys.executable, "-m", "infra.entra", "--instance-slug", self.slug, "--tenant-id", self.tenant_id,
            "--frontend-redirect-uri", outputs["frontend_url"], "--api-uami-principal-id", outputs["api_principal_id"],
        ]))
        outputs.update({
            "api_client_id": entra["api_client_id"], "web_client_id": entra["web_client_id"],
            "runtime_client_id": entra["runtime_client_id"],
        })
        self.execute(["az", "acr", "build", "-r", outputs["acr_name"], "-g", self.resource_group, "-t", f"csa-workbench-api:{self.sha}", "-f", "backend/api/Dockerfile", ".", "--only-show-errors"])
        self.execute(["az", "acr", "build", "-r", outputs["acr_name"], "-g", self.resource_group, "-t", f"csa-workbench-runtime:{self.sha}", "-f", "backend/assistant/Dockerfile", ".", "--only-show-errors"])
        self.execute(["az", "acr", "build", "-r", outputs["acr_name"], "-g", self.resource_group, "-t", f"csa-workbench-frontend:{self.sha}", "-f", "frontend/Dockerfile", ".", "--build-arg", f"NEXT_PUBLIC_API_URL={outputs['api_url']}", "--build-arg", f"NEXT_PUBLIC_IDENTITY_MODE={self.identity_mode}", "--build-arg", f"NEXT_PUBLIC_ENTRA_TENANT_ID={self.tenant_id}", "--build-arg", f"NEXT_PUBLIC_ENTRA_CLIENT_ID={outputs['web_client_id']}", "--build-arg", f"NEXT_PUBLIC_ENTRA_API_CLIENT_ID={outputs['api_client_id']}", "--build-arg", f"NEXT_PUBLIC_ENTRA_API_SCOPES=api://{outputs['api_client_id']}/access_as_user", "--build-arg", f"NEXT_PUBLIC_ENTRA_REDIRECT_URI={outputs['frontend_url']}", "--only-show-errors"])
        apps = self._apps_command(outputs)
        self.deployment_what_if(apps)
        self.execute([*apps, "--only-show-errors"], quiet=True)
        self.verify_inventory(outputs)
        verify_deployment(self.env)
        print(f"Deployed and verified isolated instance {self.slug} with immutable images tagged {self.sha}")


def _azure_output(command: Sequence[str], env: Mapping[str, str]) -> str:
    return subprocess.run(
        command_for_host(command), cwd=ROOT, env=dict(env), text=True, check=True,
        capture_output=True,
    ).stdout.strip()


def _http_json(
    url: str, *, method: str = "GET", token: str | None = None, body: bytes | None = None,
) -> object:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    last_error: Exception | None = None
    for attempt in range(12):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
            return json.loads(content) if content else {}
        except (OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 11:
                time.sleep(5)
    raise DeploymentError(f"deployed endpoint did not become healthy: {url}") from last_error


def _http_reachable(url: str) -> None:
    last_error: Exception | None = None
    for attempt in range(12):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=30) as response:
                response.read(1)
            return
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 11:
                time.sleep(5)
    raise DeploymentError(f"deployed endpoint did not become healthy: {url}") from last_error


def verify_deployment(env: Mapping[str, str] | None = None, *, browser: bool = False) -> int:
    """Check deployed health and identity without platform-specific shell syntax."""
    source = dict(os.environ if env is None else env)
    slug = _required(source, "INSTANCE_SLUG")
    if not re.fullmatch(r"[a-z][a-z0-9]{2,9}", slug):
        raise DeploymentError("INSTANCE_SLUG must match ^[a-z][a-z0-9]{2,9}$")
    if shutil.which("az") is None:
        raise DeploymentError("required command not found: az")
    try:
        subprocess.run(command_for_host(["az", "account", "show", "--only-show-errors"]), cwd=ROOT, env=source, check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        raise DeploymentError("sign in with az login before continuing") from exc

    base = f"csa-wb-{slug}"
    resource_group = f"{base}-rg"
    frontend_fqdn = _azure_output(["az", "containerapp", "show", "-g", resource_group, "-n", f"{base}-frontend", "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"], source)
    api_fqdn = _azure_output(["az", "containerapp", "show", "-g", resource_group, "-n", f"{base}-api", "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"], source)
    if not frontend_fqdn or not api_fqdn:
        raise DeploymentError("Azure did not return the deployed frontend and API addresses")
    frontend_url, api_url = f"https://{frontend_fqdn}", f"https://{api_fqdn}"
    _http_json(f"{api_url}/health")
    _http_reachable(f"{frontend_url}/")

    identity_mode = source.get("IDENTITY_MODE", "entra")
    if identity_mode == "entra":
        api_client_id = _azure_output(["az", "ad", "app", "list", "--display-name", f"CSA Workbench [{slug}] API", "--query", "[0].appId", "-o", "tsv"], source)
        if not api_client_id:
            raise DeploymentError("the deployed Entra API registration was not found")
        token = _azure_output(["az", "account", "get-access-token", "--scope", f"api://{api_client_id}/access_as_user", "--query", "accessToken", "-o", "tsv"], source)
        actor = _http_json(f"{api_url}/auth/me", token=token)
        if not isinstance(actor, dict) or actor.get("identity") != "entra" or not str(actor.get("id", "")).startswith("u-"):
            raise DeploymentError("the deployed Entra identity response is invalid")
        session = _http_json(f"{api_url}/sessions", method="POST", token=token, body=b"{}")
        if not isinstance(session, dict) or session.get("status") != "active" or not session.get("session_id"):
            raise DeploymentError("the deployed API could not create a runtime session")
        _http_json(f"{api_url}/sessions/{session['session_id']}", method="DELETE", token=token)
    elif identity_mode == "demo":
        if browser:
            if not source.get("DEMO_PASSWORD") or not source.get("AZURE_DEPLOYMENT"):
                raise DeploymentError("demo browser verification requires DEMO_PASSWORD and AZURE_DEPLOYMENT")
            browser_env = {
                **source, "MVP_ALLOW_REMOTE": "1", "MVP_APP_URL": frontend_url,
                "MVP_API_URL": api_url, "IDENTITY_MODE": "demo",
            }
            subprocess.run([shutil.which("node") or "node", "scripts/mvp_playwright.mjs"], cwd=ROOT, env=browser_env, check=True)
    else:
        raise DeploymentError("IDENTITY_MODE must be 'entra' or 'demo'")
    print(f"Verified frontend {frontend_url} and API {api_url}")
    return 0


def main(*, action: str = "plan", confirmation: str | None = None, env: Mapping[str, str] | None = None, browser: bool = False) -> int:
    if action not in {"plan", "apply", "verify"}:
        raise DeploymentError("action must be plan, apply, or verify")
    if action == "verify":
        return verify_deployment(env, browser=browser)
    if action == "apply" and confirmation is None:
        raise DeploymentError("apply requires --confirm apply:<PLAN_ID>:<RESOURCE_GROUP>")
    deployment = Deployment(env)
    deployment.require_tools()
    if action == "apply":
        deployment.apply(confirmation or "")
        return 0
    payload, plan_id = deployment.make_plan()
    foundation = deployment.foundation_command()
    if deployment.recovery_state != "incompatible":
        print("Running foundation what-if (read-only; it cannot preview later Entra creation, ACR builds, or app deployment for a new instance).")
        deployment.deployment_what_if(foundation)
    print("PLAN_PAYLOAD=")
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    print(f"PLAN_ID={plan_id}")
    print(f"CONFIRM=apply:{plan_id}:{deployment.resource_group}")
    return 0
