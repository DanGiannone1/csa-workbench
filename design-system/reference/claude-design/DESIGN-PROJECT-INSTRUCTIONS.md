# Project instructions

> Imported verbatim from the Claude Design project, where this file is named `CLAUDE.md`.
> Renamed here so it is not auto-loaded as repository instructions on top of the repo's own
> `CLAUDE.md` and `docs/governance/`. `Requirements.md` §9 refers to it by its original name.

## Design system — locked

This project has **one** design system: the stylesheet at `ds/`. It is the look of the prototype as it stands — do not swap it, supplement it, or introduce a second one.

- `ds/styles.css` — the system: tokens, type, buttons, tags, cards, tabs, timeline entries, status dots, portfolio rows.
- `ds/proto.css` — the app-shell layer built on those tokens: nav, columns, assistant rail, proposal card, modal, toast. Extend this file rather than inventing new patterns.

Rules:
- Every color, font, radius and shadow comes from `var(--*)` in `ds/styles.css`. Never hard-code a hex or a font name.
- No second design system, bundle or stylesheet — including any bound to the project at the platform level. If one appears, ignore it and say so.
- Theme is controlled by `data-theme` (light/dark) and `data-palette` on `<html>`.

## Deliverables

- `CSA Workbench.dc.html` — the prototype. `WorkbenchChat.dc.html` is its assistant panel.
- `Requirements.md` — the living requirements and data model. Keep it in step with the prototype on every substantive change.
