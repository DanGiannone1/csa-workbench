# CSA Workbench design system

`src/tokens.css` is the single production source for color, depth, focus, motion, and typography.
The palette is the reference prototype's **ink** scheme — a blue-violet brand on cool light
surfaces — chosen by the product owner; dark mode and palette selection deliberately do not ship.
Type pairs Source Serif 4 for display and reading surfaces with Instrument Sans for the interface;
controls are quiet and sentence-case per the reference. The frontend imports the token file once
from `frontend/src/app/globals.css`. Component code uses semantic token names such as `surface-1`,
`text-primary`, and `brand-primary`; it does not define a second palette.

## Components

Production React primitives live in `frontend/src/components/ui/`:

- `Button` for primary, secondary, ghost, and destructive controls;
- `Surface` and `Card` for bounded content (`level="flat"` for surfaces mounted flush inside a
  rail or panel);
- `Field` for labels, hints, and validation;
- `Status` for neutral, informational, success, warning, and danger states;
- `Tabs` and `Tab` for page sections;
- `Dialog`, `Drawer`, and `Overlay` for contained modal and compact navigation surfaces; and
- `Toast` for live, non-blocking status messages.

Use the smallest semantic primitive and preserve the native element contract:

```tsx
<Button variant="primary" disabled={saving}>Save</Button>
<Status tone="warning">Needs review</Status>
<Field label="Customer" htmlFor="customer"><input id="customer" className="ui-input" /></Field>
```

Product-specific layout classes may compose these primitives, but visual values belong in tokens and
the primitive classes in `frontend/src/app/globals.css`. New gradients, translucent blur surfaces,
hard-coded palette colors, and arbitrary color utilities are not production styles.

## Reference quarantine

`reference/claude-design/` is an attributable, read-only import from commit `eb0708b`. It is visual
research, not production source. `.dc.html`, generated `support.js`, prototype CSS, and the complete
reference directory are excluded from application and container bundles.
