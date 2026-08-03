# MVP requirements

## Goal

A Cloud Solution Architect can manage private work, collaborate on a shared customer Engagement, and
use the assistant to perform supported actions through the same rules as the web application.

## Required behavior

1. The application provides Engagements, Home, Tasks, Calendar, Reminders, Assistant, and Settings.
2. A signed-in user can create an Engagement and becomes its owner.
3. Engagement members see the same shared record according to owner, editor, and viewer permissions.
   The record carries the delivery facts a stand-in would need: a green/yellow/red status that must
   state its reason when not green, a dated "where it stands" summary, the business value, the
   engagement value, objectives, key dates, and customer contacts (kept separate from the delivery
   team). A timeline holds meetings, decisions, risks, and notes; each entry records who added it
   and where it came from, and entries are never edited or deleted. Documents are grouped as raw
   uploads (bronze), working drafts (silver), or curated versions someone deliberately promoted
   (gold, recording who promoted them and when).
3a. Each session opens with a short ranked list of what needs attention today — imminent key dates
    first, then records that are off track, then overdue work. The server builds it directly from
    the stored record: the same data always produces the same list, no AI model is involved, and
    each item opens the matching page.
4. Each user's Tasks, Calendar events, and Reminders remain private to that user.
5. The web application provides a manual path for every supported operation.
6. The assistant uses typed tools and structured results. Assistant text alone cannot change records
   or move the application to another page.
7. Engagement artifacts remain separate from temporary assistant-session files.
8. Session uploads accept Markdown files only.
9. The product includes the `engagement-meeting-prep`, `tasks`, `calendar`, and `weekly-review` skills.
10. Azure deployment uses an explicit instance name and model configuration. Deployment changes need
    a current plan and the user's approval.
11. Reminder email recipients come from the owning user's authenticated identity. Delivery is
    at-most-once, failures are recorded on the Reminder, and Reminders continue to work in-app when
    email delivery is not configured.

## Main user journeys

### Personal and shared work

Two users sign in and see only their own private work. They see only Engagements where they are
members. One user shares an Engagement with the other, and both then see the same shared record. A
non-member cannot read it.

### Assistant control

The assistant opens an authorized Engagement and makes a supported change through a typed tool. Text
that merely looks like a route, tool call, or success message has no application effect.

### Responsive use

The main journeys remain usable on wide, compact, and narrow screens. Loading, empty, validation,
permission, and failure states remain understandable.

### Isolated Azure deployment

An approved revision can deploy to its own Azure resource group using an explicit instance name and
model configuration. The deployment process checks the selected target before making changes.

## Exclusions

The MVP does not include global Library or Search pages, general document retrieval, non-Markdown
session uploads, unattended assistant-generated Reminder content, or a Copilot production runtime.
It does not promise production readiness, external distribution, or accessibility certification.
