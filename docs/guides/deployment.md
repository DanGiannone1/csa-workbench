# Azure deployment

This guide creates one isolated CSA Workbench instance with the repository's Python command.
Planning is read-only. Deployment changes Azure resources and requires the user's explicit approval.
The plan and apply commands are identical in PowerShell on Windows and in Terminal on macOS or Linux.

## Human-to-agent quick start

The human selects the Azure account. The coding agent performs the documented planning, deployment,
and verification work.

```bash
az login --tenant '<tenant-id-or-domain>'
az account set --subscription '<subscription-id-or-name>'
az account show --query '{subscription:name,subscriptionId:id,tenantId:tenantId,user:user.name}' -o json
```

Then give the agent a request such as:

```text
Deploy CSA Workbench instance <instance> to the Azure tenant and subscription currently selected in
Azure CLI, following docs/guides/deployment.md. Use identity mode <entra|demo> and these model values:
<values>. I authorize the matching plan and apply. Stop for any unapproved deletion, target change,
security choice, or material cost choice. Verify the deployed application end to end.
```

The agent owns the repository procedure, work record, exact plan confirmation, deployment commands,
and evidence. The human does not need to translate the guide into individual shell commands. A
request to inspect or plan is not authorization to apply.

## Before starting

1. Read the current `infra/deploy.py` deployment policy.
2. Confirm the approved work record required by the [Master SDLC](../governance/master-sdlc.md).
3. Use a clean worktree.
4. Sign in to the intended Azure tenant and subscription.
5. Obtain the exact instance and model values from the user.

```bash
az login --tenant '<tenant-id-or-domain>'
az account set --subscription '<subscription-id-or-name>'
az account show --query '{subscription:name,subscriptionId:id,tenantId:tenantId,user:user.name}' -o json
```

For a VNet-integrated Container Apps environment, some subscriptions must first register
`Microsoft.Network/AllowBringYourOwnPublicIpAddress` and then re-register the `Microsoft.Network`
provider. The repository deployment command does not perform that subscription-level registration. The agent may
inspect its state, but must stop and obtain explicit approval before registering it, or ask the human
to complete the prerequisite in the selected subscription. Authorization to apply the instance plan
does not implicitly authorize provider or feature registration. After the human-approved prerequisite
completes, rerun `az account show` and the plan command below; never reuse an earlier confirmation.

## Required values

PowerShell on Windows:

```powershell
$env:INSTANCE_SLUG='your-instance-slug'
$env:MODEL_DEPLOYMENT_NAME='your-model-deployment-name'
$env:MODEL_NAME='your-model-name'
$env:MODEL_VERSION='your-model-version'
$env:MODEL_SKU_NAME='your-model-sku-name'
$env:MODEL_CAPACITY='your-model-capacity'
$env:LEGACY_MODEL_DEPLOYMENT_NAME='your-legacy-deployment-name'
$env:LEGACY_MODEL_NAME='your-legacy-model-name'
$env:LEGACY_MODEL_VERSION='your-legacy-model-version'
$env:LEGACY_MODEL_SKU_NAME='your-legacy-model-sku-name'
$env:LEGACY_MODEL_CAPACITY='your-legacy-model-capacity'
$env:IDENTITY_MODE='entra'
```

Terminal on macOS or Linux:

```bash
export INSTANCE_SLUG='your-instance-slug'
export MODEL_DEPLOYMENT_NAME='your-model-deployment-name'
export MODEL_NAME='your-model-name'
export MODEL_VERSION='your-model-version'
export MODEL_SKU_NAME='your-model-sku-name'
export MODEL_CAPACITY='your-model-capacity'
export LEGACY_MODEL_DEPLOYMENT_NAME='your-legacy-deployment-name'
export LEGACY_MODEL_NAME='your-legacy-model-name'
export LEGACY_MODEL_VERSION='your-legacy-model-version'
export LEGACY_MODEL_SKU_NAME='your-legacy-model-sku-name'
export LEGACY_MODEL_CAPACITY='your-legacy-model-capacity'
export IDENTITY_MODE='entra'
```

Use `IDENTITY_MODE=demo` only for an isolated demo deployment. Demo mode also requires
`DEMO_PASSWORD` to be present in the environment without printing or committing it.

The resource group is `csa-wb-<instance-slug>-rg`.

## Plan

```text
uv run python -m scripts.workbench deploy plan
```

Planning authenticates to Azure, inspects the selected target, checks whether recovery is needed,
and runs the available Bicep what-if operation. It prints a `PLAN_ID` and a confirmation in this
format:

```text
apply:<plan-id>:<resource-group>
```

Before deployment, review:

- tenant, subscription, instance name, and resource group;
- identity mode and model values;
- the pinned Microsoft Entra auth-sidecar image digest;
- public frontend and API access;
- managed identities and their roles;
- resources that can incur cost; and
- any recovery deletion reported by the plan.

Ask the user again before continuing if the plan introduces a new deletion, target, security choice,
or cost choice that was not already approved.

## Apply

Run apply only when the user requested deployment and the current plan matches that request:

```text
uv run python -m scripts.workbench deploy apply --confirm "apply:<plan-id>:<resource-group>"
```

Apply recomputes and checks the plan before changing Azure. A stale confirmation fails. When
recovery is needed, the command removes only the exact Container Apps and environment named in the
current plan before creating the approved resources.

The command creates Entra registrations, builds Git-SHA-tagged images, deploys the Azure components,
and inspects the resulting resource group, network, identities, and application settings.

The final inspection requires exactly the three expected Container Apps with the configured access,
ports, replica limits, and Git-SHA image tag. It requires the runtime auth sidecar and, in Entra
mode, the API auth sidecar, both pinned to
`mcr.microsoft.com/entra-sdk/auth-sidecar@sha256:fc4b3871adfacf41a46b3ad9e8cf619e59d58b39bf5b00dfe9ff13c1de140dd6`.
It also checks their loopback endpoint, tenant, audience, scope or role, resources, the private
network, Cosmos and Blob settings, managed-identity roles, and expected resource list. An unexpected
application-owned resource causes the deployment check to fail. Sidecar drift also fails the check.

A first deployment can take tens of minutes. Container Apps environment creation or recovery and
private-endpoint provisioning are long-running Azure control-plane operations; lack of terminal
output during those operations is not evidence that the deployment is stuck. Do not start a second
apply while the first is still active.

## Verify the deployed application

Run the same command on Windows, macOS, or Linux:

```text
uv run python -m scripts.workbench deploy verify
```

The command resolves the deployed addresses from Azure, checks the public frontend and API, and
keeps credentials out of terminal output. With `IDENTITY_MODE=entra`, it obtains a delegated token,
checks `/auth/me`, creates a session through the API, and deletes that session. The session round
trip proves the API can call the private runtime with its managed identity. It does not replace an
interactive browser redirect or MFA check when that experience is release-critical.

For a new or dedicated demo instance, set `IDENTITY_MODE=demo`, `DEMO_PASSWORD`, and
`AZURE_DEPLOYMENT` using the PowerShell or Terminal syntax shown under Required values. Then, only
with approval to change demo records, run:

```text
uv run python -m scripts.workbench deploy verify --browser
```

The command supplies the resolved remote URLs to the browser journey. It refuses to run that journey
without the demo password and deployed model name and must never target an Entra or shared instance.

The successful API and session requests also exercise Microsoft Identity Web key discovery in the
API and runtime sidecars. Preserve the deployment inventory output and sanitized `mise-auth`
container logs as validation evidence. Do not capture access tokens or full claim payloads. S360
telemetry processing is external and can lag the deployment, so retain the exact Git SHA, sidecar
digest, UTC validation time, and affected App IDs when replying to the compliance owner.

For Entra v2 workload tokens, request the runtime scope as
`api://<runtime-client-id>/.default`, but validate the token `aud` claim as the bare runtime client
ID. Treat the scope URI and emitted audience as distinct values.

## Acceptance evidence

A deployment is complete only after all of the following pass:

- the post-deployment inventory and private-network checks in `infra/inventory_verifier.py`;
- public frontend and API health checks, with the runtime remaining private;
- immutable image tags matching the deployed Git SHA;
- immutable Microsoft auth-sidecar digests and a successful sidecar-backed validation request;
- an authenticated API-to-runtime session round trip;
- the remote browser suite for a dedicated demo instance; and
- for Entra, delegated API authentication plus an interactive browser sign-in when required for the
  release claim.

Do not describe the MVP as production-ready solely because it is deployed to an instance named
`prod`. Release readiness also requires current dependency-vulnerability review, observability,
operational ownership, and the remaining production controls identified in the architecture docs.

## Reminder email

The current Azure templates do not create Azure Communication Services resources or a scheduled
Reminder job. Adding either requires separate approval and infrastructure work. Scale-to-zero
deployments need an external schedule because an inactive API cannot run its in-process Reminder
loop.

## GitHub Actions

`.github/workflows/deploy.yml` runs repository checks on Windows, macOS, and Linux plus Bicep
compilation. It has no Azure credential and does not deploy. The guarded Python command is the
deployment path.
