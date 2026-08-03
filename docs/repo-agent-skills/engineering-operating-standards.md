# Engineering operating standards

Use these standards whenever you investigate, change, review, or integrate repository work.

## Understand before changing

Confirm the requested scope, repository instructions, affected source and documentation, current
worktree changes, interfaces, and expected behavior. Support factual claims with direct source
references. State clearly when something has not been checked.

If the same approach repeatedly fails, stop and reconsider it.

## Keep changes safe and focused

- Follow the current architecture and nearby code patterns.
- Prefer the smallest complete change.
- Do not add speculative abstractions, silent fallbacks, unused compatibility code, or unrelated
  cleanup.
- Preserve existing and concurrent work.
- Use `rg` or `rg --files` for repository searches when available.
- Use the repository's cross-platform commands instead of inventing operating-system-specific
  alternatives.

## Respect decisions and limits

Work only within the approved scope and available permissions. Stop when a missing product or
architecture decision would materially change the result.

Do not make unapproved changes to Git hosting, releases, data, security, permissions, deployment,
or external systems. Read-only inspection is allowed when it supports the requested work.

## Check and report

Use the [testing skill](testing.md) to choose checks that match the changed behavior and the cost of
an error. Review the final diff against every success criterion. Report failures, remaining risks,
and anything that still needs confirmation.
