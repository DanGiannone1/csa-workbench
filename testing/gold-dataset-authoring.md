# Gold dataset authoring reference

This is the engineering reference behind the beginner-friendly [eval start page](../tests/evals/README.md). Clients start with an **Input prompt** and **Expected output**. An engineer adds only the fields needed to verify that outcome safely and repeatably.

## Keep the dataset simple

CSA Workbench currently uses two small, versioned JSON datasets:

- `tests/evals/mvp-cases.json` for one-prompt scenarios;
- `tests/evals/mvp-workflows.json` for multi-turn conversations.

Keep that arrangement unless a new product area makes it genuinely harder to understand. Do not create one file per scenario merely because it is technically possible. Both files carry the same `fixtureVersion`, and the runner rejects a mixed pair.

## From a client example to an executable contract

Start with the client pair:

| Input prompt | Expected output |
|---|---|
| Prep me for my Acme Internal AI Chatbot check-in. | A concise factual brief; do not invent facts or change a record. |

Then add the smallest set of facts needed to prove it:

| Contract field | Why it exists | Used for this example? |
|---|---|---|
| `id` | Stable name used in results and comparisons. Never reuse it for another meaning. | Yes |
| `scenario` | Human-readable title. | Yes |
| `actor` | The signed-in test person. This makes permission checks real. | Yes |
| `prompt` | The original client input. | Yes |
| `expectation.stateChanged` | Says whether saved application data may change. | Yes: `false` |
| `requiredToolNames` / `forbiddenToolNames` | Names only actions that are necessary to the promise or forbidden for safety. Do not prescribe harmless read order. | Yes |
| `modelVisibleOutput` | Rebuilds the facts shown to the model and compares them with the starting state. | Yes |
| `onlyEngagementMayChange` or a personal aggregate boundary | Proves no unrelated record changed. | No: this request is read-only |
| `engagementAfter` | Defines the final saved state for a write. | No: this request is read-only |
| `safeNonExecution` | Lists legitimate ways to refuse without changing anything. | No: use it for safety cases |

The current JSON fixtures are parsed by the real runner, and the deterministic tests bind their IDs to `scripts/mvp_eval_manifest.mjs`. Run `npm run test:mvp-evidence` after editing either dataset.

## Choose the right kind of proof

Use deterministic checks when the result can be observed as a fact: an action happened, a record has a value, a protected record stayed untouched, or an event stream is valid. These checks gate a result.

Use an advisory review when the question is inherently about judgment, such as whether a paragraph is concise or easy to follow. Record the advisory result, its model or reviewer, and its input evidence. It must not turn a deterministic failure into a pass.

## Data and comparison integrity

Each run resets to a known demo fixture, fingerprints that fixture, and records the source revision, model, skill text hash, and evidence time. This is provenance: it lets a reviewer tell whether two results are fair to compare. A baseline is a reviewed, accepted earlier result; it is not simply the last file produced by a command.

The product suite currently makes one attempt per scenario. Do not describe that as a consistency measure. When repeated trials are introduced, record the count, independent run conditions, and the pass@k calculation before promoting it to a gate.

## Authoring checklist

1. Write the prompt and expected output in plain English first.
2. Choose an existing fixture record and the correct actor; add a new fixture only when the current data cannot express the case.
3. State the smallest observable final-state or unchanged-state boundary.
4. Allow legitimate safe alternatives rather than enforcing one assistant sentence or harmless read sequence.
5. Add the stable ID to the official manifest only after the contract is reviewed.
6. Run `npm run test:mvp-evidence`; then run the isolated live suite when current approval and a configured model are available.

For full runner mechanics, evidence shape, and scorecard acceptance, see [Product-runtime evaluation](agent-evals.md).
