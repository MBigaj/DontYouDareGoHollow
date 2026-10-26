# Index Design

> **Why this matters for you:** You add indexes routinely; senior work is knowing which ones, in what order, and what they cost writes.

## You should be able to
- Design composite, partial, covering and expression indexes
- Order composite index columns for real queries
- Weigh read gains against write and storage costs

## Lesson
Adding an index is easy. Senior index work is choosing *which* index, in *what column order*, and knowing what each one costs every write.

**Composite B-tree indexes are sorted by the first column, then the second, and so on.** An index on `(tenant_id, created_at)` is a list grouped by tenant, each group sorted by time. It serves:

- `WHERE tenant_id = $1`
- `WHERE tenant_id = $1 AND created_at > $2`
- `WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 20`, which is the perfect case: jump to the tenant, read 20 entries backwards, stop.

It does little for `WHERE created_at > $1` alone, because matching rows are scattered across every tenant's group. Swap the order to `(created_at, tenant_id)` and you get the opposite: good for time-range scans across all tenants, poor for one tenant's latest rows, which now means scanning a time range for everybody and filtering. The rule of thumb: **equality columns first, then the range or sort column.** Beyond that, put first the column your queries always filter on. PostgreSQL 18 adds skip scan, which can use a later column when the leading one has few distinct values, but design for the queries rather than relying on it.

**Partial indexes** index only the rows matching a `WHERE`. A `jobs` table with 50 million rows, 0.1% of them `queued`:

```sql
CREATE INDEX CONCURRENTLY jobs_queued_idx ON jobs (id) WHERE state = 'queued';
```

The index is tiny, stays in memory, and takes no write cost for the 99.9% of rows outside it. The catch: the planner uses it only when the query's `WHERE` provably implies the predicate. `WHERE state = 'queued'` qualifies; `WHERE state = $1` with a parameter may not, under a generic plan. Partial unique indexes enforce rules such as "one active subscription per user": `UNIQUE (user_id) WHERE cancelled_at IS NULL`.

**Covering indexes** add payload columns with `INCLUDE`, so a query can be answered by an index-only scan:

```sql
CREATE INDEX ON orders (customer_id) INCLUDE (status, total);
```

The `INCLUDE` columns are stored but not sorted, so they cannot be searched. They only save the heap visit.

**Expression indexes** index the result of an expression. `CREATE UNIQUE INDEX ON users (lower(email))` gives case-insensitive uniqueness, and serves `WHERE lower(email) = $1`, the exact expression.

**Beyond B-tree:** GIN for JSONB containment (`@>`), arrays and full-text search; BRIN for huge append-only tables whose physical order follows a column, such as event timestamps. A BRIN index is a few pages instead of gigabytes, at the price of reading whole block ranges.

**What indexes cost.** Every insert writes every index. Updates are subtler. If an `UPDATE` changes no indexed column and the page has free space, PostgreSQL makes a *HOT update*: the new version stays on the same page and no index is touched. Index a column that changes on every update, such as `updated_at` or a counter, and every update becomes a full write to every index, plus more WAL, more replica traffic and more vacuum work. On a write-heavy table, that one convenience index can cost more than all the reads it speeds up. Check `n_tup_hot_upd` against `n_tup_upd` in `pg_stat_user_tables` to see the ratio.

**Pruning.** `pg_stat_user_indexes.idx_scan = 0` over a long window marks a candidate for removal. Statistics are per server, so check the replicas too: an index unused on the primary may serve every read on a replica. Also check for duplicates: `(a)` is redundant next to `(a, b)`, unless it is unique or much smaller and hot.

In production, always build with `CREATE INDEX CONCURRENTLY`. It takes longer and cannot run inside a transaction block, so in Alembic it needs an autocommit block, and if it fails it leaves an `INVALID` index you must drop and retry.

## Quiz
### The hot query is `WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 20`. Which index serves it best?
- [x] `(tenant_id, created_at)`
- [ ] `(created_at, tenant_id)`
- [ ] Two separate indexes, one on each column
- [ ] `(created_at)` with `INCLUDE (tenant_id)`

Equality column first, sort column second: the scan jumps to the tenant and reads 20 entries already in order.

### A `jobs` table holds 50 million rows, and 0.1% are `queued`. Workers always query the queued ones. What is the best index?
- [ ] A B-tree on `state`
- [ ] A composite index on `(state, id)` across all rows
- [x] A partial index `ON jobs (id) WHERE state = 'queued'`
- [ ] A BRIN index on `state`

The partial index holds only the rows workers want: tiny, cached, and free for writes to the other 99.9%.

### You add an index on `updated_at` to a table that is updated constantly. What is the hidden cost?
- [ ] Reads on the table become slower
- [x] Updates can no longer be HOT, so every update writes every index on the table
- [ ] The table is locked whenever `updated_at` changes
- [ ] PostgreSQL stops collecting statistics on the table

HOT updates skip index writes only when no indexed column changes. A column that changes on every update rules that out.

### You want `SELECT total FROM orders WHERE customer_id = $1` answered by an index-only scan. Which index?
- [ ] `(total)`
- [ ] `(customer_id)`
- [ ] `(total, customer_id)`
- [x] `(customer_id) INCLUDE (total)`

Search on `customer_id`, carry `total` as payload, and the heap is never visited, as long as the visibility map is current.

### There is a partial index `ON users (email) WHERE deleted_at IS NULL`. A query runs `WHERE email = $1` without a `deleted_at` filter. Is the index used?
- [ ] Yes: the planner adds the missing predicate itself
- [ ] Yes, but only for an index-only scan
- [x] No: the query's `WHERE` must imply the index predicate, and this one does not
- [ ] No: partial indexes only serve `IS NULL` queries

Without `deleted_at IS NULL` the query could match deleted rows, which the index does not contain, so the planner cannot use it.

### How do you find indexes that cost writes but serve no reads?
- [x] `pg_stat_user_indexes` with `idx_scan = 0` over a long window, checked on the replicas too
- [ ] `EXPLAIN` every query in the codebase
- [ ] Drop indexes one at a time and watch latency
- [ ] `pg_class` sizes: the biggest indexes are the unused ones

Usage statistics are per server. An index idle on the primary may serve every read on a replica.

## Exam questions
- Index on (tenant_id, created_at) vs (created_at, tenant_id): which queries use each?
- When is a partial index the best tool?
- How do too many indexes hurt an insert-heavy table?
