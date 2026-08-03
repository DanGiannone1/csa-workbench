# Meeting Notes — Northstar Kickoff

**Date:** 2026-06-16

## Attendees
Product, Design, and Engineering leads.

## Discussion
- Agreed the first milestone is a working dashboard shell with one real metric, not a
  full feature set. Ship something live early, then expand.
- Design raised that the legacy color coding confuses new users; we will standardize on
  a single status palette (green / orange / red / gray).
- Engineering flagged that two of the three legacy data sources lack stable identifiers,
  which will need a mapping layer.

## Decisions
- Batch refresh every 15 minutes is acceptable for v1; real-time is deferred.
- We will retire the legacy dashboards only after the new one has run in parallel for two weeks.

## Action items
- Product to write the one-page brief and circulate before Friday's review.
- Design to deliver the standardized status palette.
- Engineering to scope the source-identifier mapping layer.
