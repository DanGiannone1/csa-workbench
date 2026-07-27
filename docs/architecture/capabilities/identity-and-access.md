# Identity and access

CSA Workbench identifies the user before loading private work, Engagements, or assistant sessions.
Each running environment selects one identity mode.

| Environment | Mode | Sign-in |
|---|---|---|
| Local development and automated checks | `demo` | `dan`, `ava`, or `sam` with the configured demo password |
| Azure Entra deployment | `entra` | A user from one configured Microsoft Entra tenant |
| Dedicated Azure demo deployment | `demo` | Demo actors with the configured demo password |

An environment accepts only its configured credential type.

## Users

Application records use stable IDs rather than display names or email addresses. Demo IDs begin
with `demo:`. Entra IDs are derived from the validated tenant and object identifiers and are exposed
to the application as `u-<oid>`.

Display name and sign-in address come from validated Entra claims when the user is first created.
They do not replace the stable ID.

## Authentication

Demo mode validates the configured password and issues a server-side token. In Entra mode, the
official Microsoft Entra authentication sidecar performs signature, signing-key discovery, issuer,
audience, and lifetime validation. CSA Workbench accepts only the trusted claims returned over the
container-local loopback interface, then independently requires the configured tenant, audience,
user identifiers, and delegated `access_as_user` scope.

The API-to-runtime path uses the same Microsoft validator. The runtime additionally requires the
API managed identity's exact object ID and the `invoke` application role. Sidecar outages and
malformed validation responses fail closed with `503`; rejected credentials receive the same `401`
response. Tokens and complete claim sets are never written to application logs.

Missing, malformed, mixed, or wrong-mode credentials receive the same `401 Unauthorized` response.

## Authorization

Private Tasks, Calendar events, and Reminders belong only to their authenticated owner. Cross-user
requests receive the same `404` response as a missing record.

Engagement authorization uses current membership:

| Role | Access |
|---|---|
| Owner | Read, edit, manage artifacts, and manage members |
| Editor | Read, edit delivery work, and manage artifacts |
| Viewer | Read and download artifacts |

A non-member receives the same not-found response as an unknown Engagement. A known member without
enough permission receives `403`. Invalid input receives `422`.

Browser controls help people understand their permissions, but server-side services make every
authorization decision. The server reloads membership before each operation and again when retrying
a concurrent update.

## Assistant sessions

The API creates each assistant session for the authenticated user and forwards that user to the
runtime outside the model request. The runtime stores a write-once user binding. Session and product
tools reject a mismatched user without revealing whether another user's session exists.

## Reminder recipients

Reminder email uses the owning user's identity. Entra users receive mail at their validated sign-in
address. Demo users receive mail only at the operator-configured test address. Reminder requests do
not contain a recipient field.

## Exclusions

The MVP does not implement account linking, multiple Entra tenants, group membership, SCIM,
directory search, guest lifecycle management, or a shared-key authentication bypass.
