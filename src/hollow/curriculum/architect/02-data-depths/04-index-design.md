# Index Design

> **Why this matters for you:** You add indexes routinely; senior work is knowing which ones, in what order, and what they cost writes.

## You should be able to
- Design composite, partial, covering and expression indexes
- Order composite index columns for real queries
- Weigh read gains against write and storage costs

## Exam questions
- Index on (tenant_id, created_at) vs (created_at, tenant_id): which queries use each?
- When is a partial index the best tool?
- How do too many indexes hurt an insert-heavy table?
