# Waza skill laboratory — starter suites

Each folder here is a complete, working example of how to test one skill in isolation: the skill's
own instructions, a set of fake product tools, a handful of realistic prompts, and pass/fail rules
over what the agent did. Nothing in this folder touches CSA Workbench or its data — the tools are
mocks that return canned answers. For what this lane can and cannot prove, read
[the Waza guide](../../../testing/waza-skill-evals.md), starting with "Why this lane exists".

## The four suites, and what each demonstrates

| Suite | Lane | What its tasks show |
|---|---|---|
| `engagement-meeting-prep` | curated (`gate` tag) | The full pattern: direct trigger, paraphrased trigger, two does-not-trigger cases, a failure-mode case, and a grounding case |
| `tasks` | advisory | The minimal pair: one direct create, one "calendar wording must not trigger the tasks skill" |
| `calendar` | advisory | The same minimal pair from the calendar side |
| `weekly-review` | advisory | A multi-step workflow trigger, plus "a single task request must not trigger a whole review" |

Every suite carries at least one **negative** (does-not-trigger) case. That is deliberate: the most
common skill failure in practice is a skill firing when it should stay silent, and a suite with only
positive cases cannot see it.

## Test your own skill in about ten minutes

1. Copy the smallest suite: duplicate `tasks/` as `<your-skill>/`.
2. In `eval.yaml`, point `skill` at your skill file, rename the eval, and replace the `mcp_mocks`
   with the tools your skill expects — each mock needs an input shape and a canned response.
3. In `tasks/`, write at least one positive prompt (the skill should fire and call your tool) and
   one negative prompt (a neighboring request that must not fire it).
4. Register the suite as `advisory` in the `WAZA_SUITES` list in `scripts/workbench.py` so the
   runner picks it up.
5. Validate for free — no model, no sign-in:

   ```text
   npm run eval:waza:validate
   npm run eval:waza:check
   ```

6. Run it (a one-time `copilot login` is required first — see the guide's setup section):

   ```text
   npm run eval:waza:advisory
   ```

Results land under `evidence/mvp/local-synthetic/waza/<run>/` as `waza.json` plus full transcripts.
Read a failing task's transcript before changing anything: the transcript shows what the agent
actually did, which is usually more informative than the pass/fail bit.

## Rules of the road

- Mocks never contact the product. If your test needs real saved state, it belongs in the
  [product-runtime suite](../../../testing/agent-evals.md), not here.
- A pass here says the skill's instructions route a generic agent correctly. It says nothing about
  the CSA Workbench runtime — never quote a Waza result as product evidence.
- These four suites double as documentation examples; keep them small and readable.
