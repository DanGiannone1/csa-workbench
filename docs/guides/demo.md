# Demo guide

This demo shows the main shared-work and assistant workflow.

## Before the demo

1. Start an isolated local application using the [local development guide](local-development.md).
2. Confirm that the demo user can sign in and open Engagements.
3. Reset only the isolated demo data when a clean starting point is required.

## Main workflow

This mirrors the canonical multi-turn eval workflow (`ACME-5-full-conversation`).

1. Open the **Acme Internal AI Chatbot** Engagement in the web application.
2. Ask the assistant: `Prep me for my Acme Internal AI Chatbot check-in.`
3. Confirm that the meeting brief uses the Engagement's recorded customer, status, dates,
   milestones, tasks, and risks.
4. Tell the assistant:

   ```text
   The data-privacy review slipped to August 12. Set it to Yellow with the exact
   reason 'Data-privacy review slipped to August 12'.
   ```

5. Confirm that Acme Internal AI Chatbot now shows Yellow with that exact reason.
6. Tell the assistant: `Open it.`
7. Confirm that the application opens the Acme Internal AI Chatbot Engagement.
8. Tell the assistant:
   `Add a personal task for me to send Dana the updated architecture diagram, High priority.`
9. Open Tasks and confirm that the new task belongs to the signed-in user.

## Private-work workflow

The main workflow's final step already shows private task creation. To show private navigation:

1. Ask the assistant to open Reminders.
2. Confirm that the application moves to Reminders without changing another user's records.

## What the demo explains

- The web application works without the assistant.
- Shared Engagements and private work have different ownership rules.
- The assistant uses typed tools for supported actions.
- The application reloads saved records after assistant activity.
- Assistant text that resembles a route or successful action has no effect by itself.

The versioned automated cases are stored in `tests/evals/mvp-cases.json` and
`tests/evals/mvp-workflows.json`.

For a presenter-ready explanation of the Waza skill laboratory, Deep Agents product eval, gold
contracts, observed evidence, metrics, and live commands, use the
[agent evaluation showcase](eval-showcase.md).
