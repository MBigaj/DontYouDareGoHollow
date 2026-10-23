# Zero-Downtime Migrations

> **Why this matters for you:** Schema changes on a live service are where data work meets deployment; expand and contract is the core skill.

## You should be able to
- Run expand/contract migrations with Alembic across several deploys
- Backfill large tables safely
- Add constraints and indexes without long locks (CONCURRENTLY, NOT VALID)

## Exam questions
- Rename a column used by a running service with zero downtime. Step by step.
- How do you backfill 200 million rows without hurting production?
- Why can adding a NOT NULL column with a default be slow, or not, depending on version?
