# Infrastructure

## Azure components

Each deployment uses an explicit instance name and creates one resource group named
`csa-wb-<instance>-rg`.

```text
Internet
  |-- public frontend Container App
  `-- public API Container App + Microsoft Entra auth sidecar
        `-- private assistant runtime Container App + Microsoft Entra auth sidecar
              `-- Azure OpenAI

Private network
  |-- Cosmos DB private endpoint
  `-- Blob Storage private endpoint
```

The resource group also contains a Basic Azure Container Registry, Azure OpenAI account and model
deployment, virtual network, private DNS zones, Cosmos DB account, Storage account, Log Analytics
workspace, and Application Insights. Each Container App scales from zero to one replica.

The API and runtime send OpenTelemetry traces to the instance Application Insights through the
`APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable. Tracing activates only when that
variable is present, so local development is unaffected.

## Data services

Cosmos DB uses serverless capacity, disables local keys, and blocks public network access. Blob
Storage disables public access, shared-key access, and anonymous blob access. Both services use
private endpoints and private DNS inside the instance virtual network.

Azure OpenAI disables local-key authentication but uses its identity-authenticated public endpoint.

## Managed identities

Each application component has its own user-assigned managed identity.

| Component | Access |
|---|---|
| Frontend | Pull frontend images from the registry |
| API | Pull images, read and write Cosmos and Blob, call the runtime |
| Runtime | Pull images, read and write Cosmos, call Azure OpenAI |

The deployment creates separate Entra registrations for the web application, API, and runtime. The
browser calls the API with delegated user access. The API calls the runtime through an application
role assigned to the API identity. Entra token validation runs in Microsoft's
`mcr.microsoft.com/entra-sdk/auth-sidecar` image, pinned by OCI digest. Kestrel binds the sidecar
listener only to loopback inside each Container App, and Microsoft's production middleware rejects
non-loopback callers as defense in depth. The sidecar supplies Microsoft Identity Web signing-key discovery
and compliance telemetry. A demo-mode API omits the unused sidecar; the runtime always includes it.

## Deployment process

`infra/deploy.sh` coordinates configuration checks, Azure planning, Entra setup, image builds,
deployment, and post-deployment inspection. It requires a clean worktree and explicit model values.
Application images use the full Git commit SHA rather than `latest`. The Microsoft authentication
sidecar is pinned to an immutable OCI digest, and the post-deployment inventory rejects sidecar
image or configuration drift.

Planning is the default and does not change Azure. Applying requires the exact confirmation printed
by the current plan. The script recomputes the plan before making changes and rejects stale or
copied confirmations.

See the [deployment guide](../../guides/deployment.md) for the complete procedure.

## Cost and omitted services

Scale-to-zero removes an always-running compute minimum but does not make the deployment free. Costs
can come from active Container Apps, including the authentication sidecars, Cosmos requests and
storage, Blob operations, private endpoints, the registry, image builds, and model use. Sidecars
scale to zero with their parent app.

The MVP does not provision a NAT Gateway, Azure Firewall, Front Door, API Management, VPN, Azure AI
Search, or a warm assistant pool. Application Insights receives traces only; container console logs,
data-plane diagnostic settings, and alert rules remain unprovisioned.

## Local differences

Local development keeps the frontend, API, and runtime as separate processes. It uses a separately
provided Cosmos emulator and does not reproduce private networking, managed application identities,
or Container Apps scaling. See [local development](../../guides/local-development.md).
