# Agentic SDLC

Use this process for repository work. Keep it proportional: a documentation correction needs less
ceremony than a change to product behavior, stored data, security, deployment, or permissions.

## 1. Understand the request

- Confirm the outcome, success criteria, scope, owner, and important constraints.
- Read the product, architecture, development, and deployment documents related to the work.
- Inspect the current source and worktree before proposing a change.
- Preserve unrelated and concurrent work.

Create or identify a GitHub issue before changing product behavior, stored data, deployment,
security, permissions, or an external system. Read-only investigation and explicitly approved
changes to internal coding-agent files do not require a new issue.

## 2. Agree on the approach

Explain the proposed approach, affected areas, risks, planned checks, and unresolved decisions.
Obtain the responsible person's approval before implementation. Ask again if investigation changes
the intended behavior, architecture, risk, or scope.

## 3. Make the change

- Implement the smallest complete change that satisfies the approved outcome.
- Keep file-changing work serial in one worktree unless separate worktrees and file ownership have
  been agreed.
- Do not switch the primary branch, rewrite protected history, change Git hosting, or affect an
  external system without explicit approval.

## 4. Check and review

Use the [testing skill](testing.md) to select checks that match the risk. Exercise the running
application when the behavior can be observed there.

A reviewer who did not write the change must check the final files against the success criteria.
The author may self-review, but may not provide the independent approval.

## 5. Finish clearly

Report:

- what changed and why;
- what was checked and the results;
- what was not checked;
- remaining risks or decisions; and
- the integration or delivery state.

Do not describe the work as complete until the agreed outcome and required checks are complete.
