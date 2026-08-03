# CSA Workbench — imported design prototype

Read-only import of the Claude Design project
`e96d8f52-a39e-4c20-ba3f-0947833c67e9` ("CSA Workbench"), pulled 2026-08-02 via the
`claude_design` MCP. Nothing here has been implemented or adapted — these are the source
files exactly as they exist in the design project, kept as the reference for future work.

| File | What it is |
|---|---|
| `CSA Workbench.dc.html` | The prototype (the file the design tool asked to implement) |
| `WorkbenchChat.dc.html` | The assistant panel the prototype mounts |
| `ds/styles.css` | The design system: tokens, type, buttons, cards, tabs, status dots |
| `ds/proto.css` | The app-shell layer on those tokens: nav, columns, AI rail, modal, toast |
| `support.js` | Generated `dc-runtime` bundle the `.dc.html` files load |
| `Requirements.md` | The living requirements and engagement data model |
| `DESIGN-PROJECT-INSTRUCTIONS.md` | The design project's own `CLAUDE.md` (renamed — see the note inside) |

Not imported: `.thumbnail` (a preview asset, not source).

`support.js` is machine-generated (`dc-runtime/src/*.ts`) — do not hand-edit it.
The `.dc.html` files are a design-tool template format (`<x-dc>`, `sc-if`, `sc-for`,
`{{ ... }}`), not plain HTML; they will not render usefully by opening them in a browser
outside the design tool.
