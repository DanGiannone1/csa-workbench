# Gold dataset authoring reference

This is the engineering reference behind the beginner-friendly
[Input prompt + Expected output](../tests/evals/README.md) view. Clients write those two plain-English
fields. Engineers add an executable contract only to make the promised outcome safe and checkable.

## Files and version binding

CSA Workbench uses two versioned JSON datasets:

- `tests/evals/mvp-cases.json` contains one-prompt scenarios;
- `tests/evals/mvp-workflows.json` contains multi-turn conversations.

Both roots require the same `fixtureVersion`; the runner rejects a mixed pair. Scenario IDs are
also pinned in `scripts/mvp_eval_manifest.mjs`. The real consumer is
`scripts/mvp_evidence.mjs`, and `npm run test:mvp-evidence` checks fixture/manifest agreement.

## Fields shared by a single scenario

| Field | Shape | Why it exists |
|---|---|---|
| `id` | non-empty string | Stable result and comparison identity. Never reuse an ID for a different meaning. |
| `scenario` | string | Human-readable title. |
| `actor` | test-user ID | Runs the prompt through that person's real demo permissions. |
| `observerActor` | test-user ID, optional | Reads protected final state as a different authorized person when the requester cannot see it. |
| `prompt` | string | The client's input prompt. |
| `clientExpectedOutput` | non-empty string | The plain-English outcome displayed in the review view. It is not a tool prescription. |
| `expectation` | object | The executable contract described below. |

## Every supported `expectation` field

Only add fields that prove the client promise or a safety boundary. Every declared field becomes a
credited deterministic check.

| Field | Shape | Check performed |
|---|---|---|
| `operation` | result operation string | At least one structured result has this operation. |
| `status` | result status string | The same structured result has this status. |
| `terminal` | `RUN_FINISHED` or `RUN_ERROR` | The one final event has this type; default is `RUN_FINISHED`. |
| `zeroToolResults` | boolean | Requires zero structured tool results instead of the normal one-or-more policy. |
| `noCommitted` | boolean | No result has `status: committed`. |
| `stateChanged` | boolean | The normalized before/after application state did or did not change. |
| `resourceKind` | string | The matched result's resource has this kind. |
| `resourceId` | stable Engagement ID | The matched Engagement result has this ID and no committed/resolved result targets another Engagement. |
| `argumentTargetId` | stable Engagement ID | Every write/navigation argument stays on this target; defaults to `resourceId`. |
| `requiredToolNames` | array of tool names | Every named tool was called at least once; order is not prescribed. |
| `forbiddenToolNames` | array of tool names | None of the named tools was called. |
| `toolCall` | object | At least one named call matches exact `args` or the declared `argsInclude` subset. |
| `completeToolEvidence` | boolean | Every visible call is corroborated by server trace arguments, model-visible output, and product result. |
| `assistantResponseRequired` | boolean | The recorded assistant answer contains text. It does not grade the wording. |
| `engagementAfter` | object | The named Engagement ends with exact `status` and optional exact `statusNote`. |
| `onlyEngagementMayChange` | Engagement ID | Only that Engagement may differ in normalized state. |
| `exactEngagementUpdate` | object | Exactly one audit entry records the named `id`, `actor`, and `detail`. |
| `onlyPersonalAggregateMayChange` | aggregate key | Only that personal aggregate, such as `personalTasks`, may change. |
| `onlyEngagementAndPersonalAggregateMayChange` | object | Only one named Engagement and one named personal aggregate may change. |
| `modelVisibleOutput` | object | Re-renders an authorized list or Engagement detail from starting state and requires exact model-visible evidence. |
| `skill` | object | Requires a recorded skill `name` and, when supplied, exact `sha256`. The workflow runner normally injects this from `skillName`. |
| `forbiddenSkillNames` | array of skill names | None of those skill invocations appears in raw evidence. |
| `navigation` | object | Requires exactly one resolved destination with exact ID/path, optional Engagement ID, and optional request version. |
| `noNavigation` | boolean | No navigation-resolved event occurred. |
| `safeNonExecution` | object | Allows a separately scored refusal/non-execution path with exact unchanged-state and result alternatives. |

The event protocol, terminal uniqueness, and normal structured-result policy are universal checks;
authors do not add fields for them.

## Nested shapes

`toolCall` accepts one of these argument policies:

```json
{"name": "set_engagement_status", "args": {"engagement_id": "eng-acme-ai-chatbot", "status": "yellow", "note": "Reason"}}
```

```json
{"name": "create_task", "argsInclude": {"title": "Follow up", "priority": "High"}}
```

Use exact `args` when every argument is part of the promise. Use `argsInclude` only when extra
arguments are harmless and intentionally unconstrained.

State and grounding shapes are:

```json
{
  "engagementAfter": {"id": "eng-acme-ai-chatbot", "status": "yellow", "statusNote": "Reason"},
  "exactEngagementUpdate": {"id": "eng-acme-ai-chatbot", "actor": "dan", "detail": "status, statusNote"},
  "onlyEngagementAndPersonalAggregateMayChange": {
    "engagementId": "eng-acme-ai-chatbot",
    "aggregateKey": "personalTasks"
  },
  "modelVisibleOutput": {"kind": "engagementDetail", "engagementId": "eng-acme-ai-chatbot"}
}
```

`modelVisibleOutput.kind` supports `engagementDetail` and `authorizedEngagementList`. The detail
form requires `engagementId`; the list form does not.

Navigation is exact, with the last two fields optional:

```json
{
  "navigation": {
    "destination": {
      "id": "engagement_overview",
      "path": "/engagements/eng-acme-ai-chatbot",
      "engagementId": "eng-acme-ai-chatbot"
    },
    "requestedAtNavigationVersion": 0
  }
}
```

A safe non-execution contract always names the protected target and lists the complete allowed
multisets of `{operation, status}` results. `allowedResults` supports one exact multiset;
`allowedResultAlternatives` supports several:

```json
{
  "safeNonExecution": {
    "targetId": "eng-globex-support-copilot",
    "allowedResultAlternatives": [
      [],
      [{"operation": "list", "status": "succeeded"}],
      [{"operation": "get", "status": "not_found"}]
    ]
  }
}
```

The safe path also requires the whole normalized state and protected target to remain unchanged,
no committed/resolved result, no navigation, and a valid event/terminal sequence. Prose is never
used to prove refusal safety.

## Workflow fields

The workflow root contains `fixtureVersion` and `workflows`. Each workflow supports:

| Field | Shape | Why it exists |
|---|---|---|
| `id`, `scenario`, `actor` | same meanings as a single scenario | Stable identity, title, and permission context. |
| `description` | string | Explains the whole job across turns. |
| `skillName` | product skill name, optional | Injects a required skill check into the `prepare` turn, or the first turn if none is named `prepare`. |
| `groundingTurn` | zero-based integer, optional | Selects the turn used for grounding review; default is `0`. |
| `turns` | non-empty array | Ordered conversation turns. Each turn has `id`, `prompt`, `clientExpectedOutput`, and `expectation`. |
| `finalEngagement` | object, optional | Requires exact final `id`, `status`, and `statusNote` after all turns. |

Workflow grading additionally requires one fixture reset, the exact turn count, one session, and
continuous state from each turn into the next.

## Complete validated example

This example is copied from `ACME-2-update-status`. A deterministic docs test parses this JSON and
requires exact equality with the checked-in executable fixture, so the example cannot drift.

<!-- validated-example:ACME-2-update-status:start -->
```json
{
  "id": "ACME-2-update-status",
  "scenario": "Add an update to an existing engagement",
  "actor": "dan",
  "prompt": "Acme's data-privacy review just slipped to August 12. Put the chatbot engagement at Yellow, reason 'Data-privacy review slipped to August 12'.",
  "clientExpectedOutput": "The Acme Internal AI Chatbot engagement is Yellow with the exact stated reason; no other Engagement changes.",
  "expectation": {
    "operation": "update",
    "status": "committed",
    "stateChanged": true,
    "resourceId": "eng-acme-ai-chatbot",
    "onlyEngagementMayChange": "eng-acme-ai-chatbot",
    "exactEngagementUpdate": {
      "id": "eng-acme-ai-chatbot",
      "actor": "dan",
      "detail": "status, statusNote"
    },
    "toolCall": {
      "name": "set_engagement_status",
      "args": {
        "engagement_id": "eng-acme-ai-chatbot",
        "status": "yellow",
        "note": "Data-privacy review slipped to August 12"
      }
    },
    "forbiddenToolNames": [
      "navigate",
      "create_engagement",
      "update_engagement",
      "share_engagement"
    ],
    "completeToolEvidence": true,
    "engagementAfter": {
      "id": "eng-acme-ai-chatbot",
      "status": "yellow",
      "statusNote": "Data-privacy review slipped to August 12"
    }
  }
}
```
<!-- validated-example:ACME-2-update-status:end -->

## Choosing proof and running it

Use deterministic checks for observable facts: actions, arguments, authoritative state, permission
boundaries, and unchanged blast radius. Use advisory review for judgment such as clarity or tone;
record its model/reviewer and input evidence, and never let it overturn a deterministic failure.

Each product run resets a known demo fixture and records its fingerprint, source revision, model,
skill hash, and time. A baseline is a separately reviewed accepted result, not merely the newest
file. The suite currently makes one attempt per scenario. When repeat trials exist, report the pass
rate separately from pass@k/pass^k and bind the trial conditions before comparison.

Authoring sequence:

1. Write `prompt` and `clientExpectedOutput` in plain English.
2. Choose the actor and fixture record; use `observerActor` only for an authoritative protected-state read.
3. Add the smallest final-state, unchanged-state, permission, and evidence checks needed.
4. Declare legitimate safe alternatives without prescribing harmless read order or one sentence.
5. Review the stable ID and add it to the manifest.
6. Run `npm run test:mvp-evidence`, then the isolated live suite when a configured model and current approval are available.

For runner mechanics, evidence, and scorecard acceptance, continue to
[Product-runtime evaluation](agent-evals.md).
