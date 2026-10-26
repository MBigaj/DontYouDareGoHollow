# Reading Query Plans

> **Why this matters for you:** EXPLAIN ANALYZE is the difference between 'add an index' folklore and knowing.

## You should be able to
- Read EXPLAIN ANALYZE: scan types, joins, estimates vs actuals, buffers
- Explain why the planner chose a plan, and how statistics mislead it
- Fix a slow query and prove it with numbers

## Lesson
`EXPLAIN` shows the plan the planner *expects*. `EXPLAIN (ANALYZE, BUFFERS)` runs the query and shows what *happened*, node by node. Every senior performance conversation starts from the second one.

```text
Limit  (cost=0.43..18.52 rows=20 width=64) (actual time=0.031..0.090 rows=20 loops=1)
  Buffers: shared hit=24
  ->  Index Scan using orders_tenant_created_idx on orders  (cost=0.43..9046.70 rows=10000 width=64)
                                                             (actual time=0.030..0.086 rows=20 loops=1)
        Index Cond: (tenant_id = 42)
```

**How to read a node.** `cost=startup..total` is in planner units, not milliseconds; compare it only between plans. `rows` in the cost part is the *estimate*. In the actual part, `time=first..last` is in milliseconds and `rows` is what came out, both **per loop**. Under a nested loop, `actual time=0.020..0.025 rows=1 loops=50000` means 50,000 runs of about 0.025 ms: 1.25 seconds, hiding behind a tiny number. `Buffers: shared hit` pages came from PostgreSQL's cache; `read` pages came from the OS or disk. A query that is fast on the second run and slow on the first is a `read` problem.

`ANALYZE` executes the statement. `EXPLAIN ANALYZE DELETE ...` deletes. Wrap it in `BEGIN; ... ROLLBACK;`.

**Scans.**

- **Seq Scan** reads the whole table. It is the right choice for small tables, and for queries that return a large share of the rows, where random index lookups would cost more than reading pages in order.
- **Index Scan** walks the index and fetches each matching row from the heap.
- **Index Only Scan** answers from the index alone. It still checks the visibility map; `Heap Fetches: 480000` means the map is stale and the "index only" scan visited the heap anyway. Vacuum fixes that.
- **Bitmap Index Scan + Bitmap Heap Scan** collects matching row locations first, then reads heap pages in physical order. It fits the middle ground of thousands of rows, and can combine two indexes with BitmapAnd or BitmapOr.

**Joins.**

- **Nested Loop**: for each outer row, probe the inner side. Excellent when the outer side is small and the inner side is indexed; a disaster when the planner *thinks* the outer side is small.
- **Hash Join**: build a hash table on the smaller input, stream the other through it. The default for large equality joins. `Batches: 16` on the Hash node means it did not fit in `work_mem` and spilled to disk.
- **Merge Join**: both inputs sorted on the join key, walked together. Wins when sorted order is already available from indexes.

**Estimates drive everything.** The planner picks plans from row estimates built from `pg_statistic`. When `estimated rows=10` meets `actual rows=1000000`, every choice above that node is suspect. The usual causes:

- **Stale statistics** after a bulk load: run `ANALYZE orders`.
- **Correlated columns.** `city = 'Poznań' AND country = 'PL'` is estimated as two independent filters, so the row count comes out far too low. `CREATE STATISTICS ... (dependencies) ON city, country FROM addresses` teaches the planner the link.
- **Expressions on columns.** `WHERE lower(email) = $1` cannot use an index on `email`, and gets a default guess for selectivity.
- **Generic plans** for prepared statements: after five executions PostgreSQL may switch to one plan for every parameter value, which hurts skewed data such as one giant tenant. `plan_cache_mode` controls it.

Other lines worth hunting: `Rows Removed by Filter` far larger than the rows returned (a missing or wrong index), and `Sort Method: external merge  Disk: 51200kB` (raise `work_mem` for that query, or avoid the sort with an index).

**Find the right query first.** `pg_stat_statements` ranks queries by `total_exec_time`. A 2 ms query called 40,000 times a minute usually matters more than one 3-second report. Fix the top entry, capture `EXPLAIN (ANALYZE, BUFFERS)` before and after, and put both in the PR. That is the proof.

## Quiz
### A node under a nested loop reads `actual time=0.020..0.025 rows=1 loops=50000`. Roughly how much time did it take in total?
- [ ] 0.025 ms: the figures are totals for the node
- [ ] 0.045 ms: startup plus total time
- [ ] It cannot be known without `BUFFERS`
- [x] About 1.25 seconds: the times are per loop, so multiply by 50,000

Actual time and rows are per loop. Tiny numbers under a loop with a big `loops` count are where slow plans hide.

### A plan shows `rows=10` estimated and `rows=1000000` actual under a nested loop. What is the most likely cause and first step?
- [ ] The index is corrupt; reindex it
- [x] Statistics are stale or missing correlations; run `ANALYZE`, then consider `CREATE STATISTICS`
- [ ] `work_mem` is too small; raise it
- [ ] The planner always underestimates joins; force a hash join

The planner chose the nested loop because it believed ten rows. Fix the belief, and it chooses a better join itself.

### A query filters `WHERE lower(email) = $1`, and the table has an index on `email`. The plan is a sequential scan. Why?
- [x] An index on `email` cannot serve an expression over it; it needs an index on `lower(email)`
- [ ] The planner ignores indexes on text columns
- [ ] Sequential scans are always chosen for equality filters
- [ ] The parameter `$1` prevents any index use

An expression index (`CREATE INDEX ON users (lower(email))`) matches the expression exactly, and gives the planner statistics for it too.

### You run `EXPLAIN ANALYZE DELETE FROM sessions WHERE expires_at < now()` on production to check the plan. What happened?
- [ ] Nothing: `EXPLAIN` never executes the statement
- [ ] PostgreSQL deleted the rows, then rolled back automatically
- [x] The rows were deleted; `ANALYZE` executes the statement, so wrap it in `BEGIN` and `ROLLBACK`
- [ ] PostgreSQL refuses `EXPLAIN ANALYZE` on writes

`ANALYZE` measures by running. For writes, run it in a transaction you roll back, or on a copy.

### An Index Only Scan shows `Heap Fetches: 480000`. What does that tell you?
- [ ] The index is missing columns the query needs
- [x] The visibility map is out of date, so PostgreSQL visited the heap for most rows; vacuum the table
- [ ] The query read 480,000 pages from disk
- [ ] The index is bloated and needs `REINDEX`

An index-only scan must still confirm visibility. Pages not marked all-visible send it to the heap, which erases the benefit.

### A Hash Join's hash node reports `Batches: 16`. What does that mean?
- [ ] The join ran on 16 parallel workers
- [ ] The inner side was scanned 16 times
- [ ] The planner split the query into 16 statements
- [x] The hash table did not fit in `work_mem`, so it spilled to disk in 16 batches

`Batches: 1` means it fit in memory. More batches means temporary files; give that query more `work_mem` or shrink the hashed side.

## Exam questions
- Seq scan on a table with an index: list three reasons it can be the right choice.
- Estimated rows 10, actual 1,000,000. What went wrong and how do you fix it?
- Nested loop vs hash join vs merge join: when does each win?
