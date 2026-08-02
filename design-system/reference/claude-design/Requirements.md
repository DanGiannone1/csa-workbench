# CSA Workbench — requirements

Living doc. Maintained alongside the prototype (`CSA Workbench.dc.html`). Anything marked **MVP** is in the prototype today; **Later** is agreed but deliberately out of scope.

## 1. Purpose

Help a Cloud Solution Architect do the whole job in one place: keep engagements on track, cut admin time, and build context over time so the record is never stale and never re-derived from memory.

Design principle: **the record is the product, the assistant maintains it.** The assistant reads freely, writes only through an apply the CSA presses.

## 2. Information architecture (MVP)

| Surface | Purpose |
|---|---|
| Home | Today: what needs attention, today's calls, your tasks |
| Engagements | The portfolio list → one engagement record |
| My Work | Tasks across all engagements + your own list + upcoming dates |
| AI Mode | The assistant full screen |
| Settings | Assistant behaviour, appearance |

Decided: no per-engagement list in the left nav — the single "Engagements" entry is enough.

## 3. Engagement data model

An engagement is the unit of shared context. Everything below is versioned and attributable (who wrote it, when, from what source).

| Field | Type | Purpose / notes |
|---|---|---|
| `name`, `customer` | text | Identity |
| `description` | one line | **What this is.** Plain-language scope, readable by someone who has never seen it |
| `businessValue` | one line | **Why it matters to the customer.** The outcome behind the work — what breaks or is lost if it slips. Required at creation |
| `value` | currency | Portfolio weighting and prioritisation |
| `status` | green / yellow / red | Health |
| `statusReason` | text | **Required whenever status ≠ green.** A status without a reason is not a status |
| `currentState` | prose + as-of date | "Where it stands" — the one paragraph a stand-in could read to take over |
| `objectives` | list of text | What good looks like. Lives on the engagement; edited in the overview rail; the assistant can propose additions |
| `keyDates` | date + label + done | The arc: milestones, gates, go-lives. Lives on the engagement; added and marked done in the overview rail; the assistant can propose them from a call |
| `timeline` | dated entries, typed: meeting / decision / risk / note | The log. Entries carry author + source (e.g. the file they came from) |
| `tasks` | title, assignee, due, done | Shared commitments. Overdue derived from due date |
| `contacts` | **customer-side only** — name + their title | Who to chase on the customer side |
| `team` | **our side only** — name + CSA role | Who is delivering. Never mixed with customer contacts in the UI: they are different populations with different trust and different actions |
| `documents` | bronze / silver / gold (below) | Artifacts |

Derived, never stored: overdue counts, "needs attention", portfolio aggregates, next key date.

**MVP holds this flat and simple.** One level — the engagement — with plain fields. Risk is a timeline entry type, not an object with a lifecycle. Objectives are prose, not measured targets. A task is a task. Provenance is only what comes for free: author, date, and the source file an entry came from.

### 3.1 How each field is updated

| Field | Update path |
|---|---|
| `description`, `businessValue` | Typed at creation, edited in place. Rarely changes |
| `status`, `statusReason`, `currentState` | Assistant proposal after a call (apply), or edited in place |
| `objectives` | Added in the overview rail; assistant may propose |
| `keyDates` | Added in the overview rail, marked done by clicking; assistant may propose from a call |
| `timeline` | Assistant proposal from an uploaded file, or a note typed on the Timeline tab. Append-only |
| `tasks` | Assistant proposal, or typed on the Tasks tab; toggled done anywhere they appear |
| `contacts`, `team` | Added in the overview rail, each group separately. (Invitations and permissions are out of MVP — adding a CSA records who is on it, it does not grant access) |
| `documents` | Bronze by upload; silver by editing; gold by explicit promotion |

### 3.2 Deferred until the app works
Discussed and deliberately not built yet:

| Idea | Why it's deferred |
|---|---|
| A **customer** layer above engagements (contacts, environment facts, history that outlives a project) | Real, but it doubles the IA before we know the engagement view is right |
| **Risk as an entity** with open → mitigating → closed, an owner and a threatened date | Timeline entries carry risks well enough to test with |
| **Measurable objectives** (target + current value: seats, WAU, workloads migrated) | Needs a data feed to be worth anything; prose tests the same conversation |
| **Commitment vs. internal task** distinction | One list first; split it only if testing shows people conflate them |
| **Timeline as the single source of truth** (status and tasks as projections of an append-only log) | Architecturally cleaner, materially more work, invisible to a test participant |
| Full **field-level provenance and freshness** (who/when/from what on every field) | Partially there via entry attribution; the full version waits |

### 3.3 Document tiers

| Tier | Contains | Rules |
|---|---|---|
| **Bronze** | Raw sources: client files, meeting transcripts, exports | Immutable. Never edited. Linked to the timeline entries derived from them |
| **Silver** | Working artifacts: drafts, plans, option papers, notes | Editable by the delivery team. The everyday workspace |
| **Gold** | Curated, vetted artifacts | Promoted from silver by a deliberate action. What a customer or a stand-in should read |

Promotion is an explicit user action (silver → gold), recorded with who and when.

## 4. Assistant requirements

**MVP**
- **Async brief on login.** The day's ranked items and the accompanying message are computed in the background when the app loads, so they are already there the first time the assistant is opened. No tool-call chrome on this message — it is the app speaking, not a query being answered.
- Ranked items are clickable and route straight into the record.
- Streaming responses with a visible thinking state.
- Navigation by request ("take me to my work").
- **Proposals**: from an uploaded file, the assistant proposes typed record changes (timeline entry, tasks, status reason) with per-item Apply / Dismiss and Apply all. Nothing is written until applied; every write is attributed to the user.
- Multi-session history.
- Tool-call transparency for user-asked questions (togglable in Settings — being evaluated in testing).

**Later**
- "Why this answer" / personalisation disclosure — cut from MVP.
- Auto-logging meetings the CSA attends (arrives as a proposal, still never written unprompted).
- Assistant-first home (conversation as the home surface) — in the prototype behind a Settings toggle, for testing only.

## 5. Uploads

Generic file upload, not transcript-specific. Any file lands in **bronze**; if the assistant can derive record changes from it, it proposes them.

## 6. Cut from MVP

- Share / roles / invitations — and with them the "You: Owner" role badge.
- "Why this answer" disclosure.
- Job title in the nav, tool-count footers, and other non-functional chrome. **Every UI element must serve a purpose.**

## 7. Open questions

Held open, but not blocking MVP:

1. Engagement overview: which three blocks earn the space? Currently status prose → needs attention → recent activity, with objectives / key dates / people in the rail. To be tested.
2. Does status need to be set by hand at all, or is it always an assistant proposal the CSA confirms? (MVP: set by hand, and the assistant proposes a new reason after a call.)
3. Bronze retention and permissions — can a transcript be visible to someone who was not in the call?
4. Do we need engagement-level search, or is assistant Q&A the search?

## 8. Principle for scope

Keep MVP simplistic. Ship the flat model, watch CSAs use it, then add nuance where testing proves it is missing — not before.

## 9. Design system

One system, locked: the stylesheet at `ds/` — the look of the prototype as it stands (`styles.css` = the system, `proto.css` = the app-shell layer on its tokens). No second system, bundle or stylesheet. See `CLAUDE.md`.
