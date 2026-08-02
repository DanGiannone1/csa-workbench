# GitHub Copilot entry point

Follow the shared repository instructions in [AGENTS.md](../AGENTS.md). Keep this file short: the
shared policy lives in `docs/governance/`, while Copilot-native skills and GitHub automation live in
`.github/`.

Do not treat shipped product-assistant skills as coding-agent skills. They remain in the
product-assistant catalog, are runtime-allowlisted and container-packaged, and are evaluated as
product behavior. See [working with coding agents](../docs/guides/coding-agents.md) for supported
Copilot surfaces and discovery checks.
