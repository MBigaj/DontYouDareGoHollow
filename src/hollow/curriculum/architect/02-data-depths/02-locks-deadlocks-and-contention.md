# Locks, Deadlocks and Contention

> **Why this matters for you:** Under load, lock waits become latency and outages; seniors read pg_locks, not guesses.

## You should be able to
- Explain row and table locks, and which statements take which
- Diagnose and prevent deadlocks
- Spot migrations that take dangerous locks

## Lesson
PostgreSQL has two lock layers, and outages usually come from the one people forget.

**Row locks** are taken by writes and by explicit locking reads. `UPDATE` and `DELETE` lock the rows they touch until commit. `SELECT ... FOR UPDATE` takes the same lock without writing; `FOR NO KEY UPDATE`, `FOR SHARE` and `FOR KEY SHARE` are weaker variants. A foreign-key insert takes `FOR KEY SHARE` on the parent row, which is why inserting order lines can wait on someone updating the order's primary key. Row locks are stored on the tuple itself, so locking a million rows costs no lock memory. Plain `SELECT`s never wait for row locks: MVCC gives them a snapshot instead.

**Table locks** are taken by every statement, in one of eight modes. The ones that matter:

| Statement | Mode | Blocks |
|---|---|---|
| `SELECT` | ACCESS SHARE | only ACCESS EXCLUSIVE |
| `INSERT`, `UPDATE`, `DELETE` | ROW EXCLUSIVE | `CREATE INDEX`, most `ALTER TABLE` |
| `CREATE INDEX` | SHARE | all writes, not reads |
| `CREATE INDEX CONCURRENTLY`, `VACUUM` | SHARE UPDATE EXCLUSIVE | other DDL and vacuum, not reads or writes |
| most `ALTER TABLE`, `DROP`, `TRUNCATE` | ACCESS EXCLUSIVE | everything, including `SELECT` |

**The lock queue is the trap.** Lock requests on a table queue in order. Your migration runs `ALTER TABLE orders ADD COLUMN note text`, which is instant once it gets its ACCESS EXCLUSIVE lock. But a five-minute analytics query holds ACCESS SHARE, so the `ALTER` waits. Every new `SELECT` on `orders` now queues *behind the waiting `ALTER`*, because it conflicts with the lock the `ALTER` asked for. The pool fills, health checks time out, ECS kills the tasks. The fix is two lines in every migration: `SET lock_timeout = '3s'`, plus a retry. A migration that fails fast and retries is harmless; one that waits politely takes the service down.

**Deadlocks** happen when two transactions each hold a lock the other needs. Transaction A updates account 1 then 2; B updates 2 then 1. PostgreSQL checks for cycles after `deadlock_timeout` (1 s by default), aborts one transaction with SQLSTATE `40P01`, and the other proceeds. Prevention is ordering: lock rows in a consistent order, for example `SELECT ... WHERE id = ANY($1) ORDER BY id FOR UPDATE` before updating them. Keep transactions short (no HTTP calls while holding locks), and retry `40P01` like a serialization failure.

**SKIP LOCKED turns a table into a work queue.**

```sql
UPDATE jobs SET state = 'running', started_at = now()
WHERE id IN (
  SELECT id FROM jobs WHERE state = 'queued'
  ORDER BY id LIMIT 10
  FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

Each worker claims rows nobody else holds and never waits on the others. Pair it with a partial index on `state = 'queued'`. For "only one of these may run at once" across rows that may not exist yet, `pg_advisory_xact_lock(hashtext('nightly-report'))` gives you a named lock released at commit.

**Diagnose, don't guess.** When requests stall:

```sql
SELECT pid, pg_blocking_pids(pid) AS blocked_by, wait_event_type, state,
       now() - xact_start AS in_tx, left(query, 80)
FROM pg_stat_activity
WHERE wait_event_type = 'Lock';
```

Follow `blocked_by` to the root, which is often an idle transaction, not a busy one. Turn on `log_lock_waits` so waits longer than `deadlock_timeout` reach the logs before anyone asks.

## Quiz
### A migration runs `ALTER TABLE orders ADD COLUMN note text` while a five-minute report reads `orders`. Within seconds every request touching `orders` hangs. Why?
- [ ] Adding a column rewrites the whole table under a lock
- [ ] The report's `SELECT` holds an exclusive lock on the table
- [x] The `ALTER` waits for ACCESS EXCLUSIVE behind the report, and every new query queues behind the waiting `ALTER`
- [ ] Autovacuum starts and blocks writes during the change

A nullable column with no default is a catalog-only change; the damage is the queue. A waiting ACCESS EXCLUSIVE request blocks everyone behind it.

### Which setting makes that migration fail fast instead of freezing traffic?
- [x] `SET lock_timeout = '3s'`, with a retry around the migration
- [ ] `SET deadlock_timeout = '3s'`
- [ ] `SET idle_in_transaction_session_timeout = '3s'`
- [ ] Raising `max_locks_per_transaction`

`lock_timeout` bounds how long a statement waits for a lock. A failed attempt costs three seconds of queueing instead of an outage.

### Transaction A updates account 1 then account 2; transaction B updates 2 then 1. How do you stop them deadlocking?
- [ ] Raise `deadlock_timeout` so PostgreSQL waits longer before giving up
- [ ] Run both at SERIALIZABLE
- [ ] Add an index on the account id
- [x] Lock the rows in a consistent order, for example `ORDER BY id FOR UPDATE`, before updating

A cycle needs two transactions taking the same locks in opposite orders. Remove the ordering difference and the cycle cannot form.

### Many workers run `SELECT ... FROM jobs WHERE state = 'queued' LIMIT 1 FOR UPDATE SKIP LOCKED`. What does each worker get?
- [ ] The same first job, and the others wait until it commits
- [x] The first queued job no other transaction has locked, without waiting
- [ ] A random job, possibly one another worker holds
- [ ] An error if any queued job is already locked

`SKIP LOCKED` passes over rows locked by others, so workers spread across the queue instead of lining up on one row.

### You run `CREATE INDEX` (without `CONCURRENTLY`) on a busy table. What does it block while it builds?
- [x] Writes (`INSERT`, `UPDATE`, `DELETE`), but not reads
- [ ] Reads and writes
- [ ] Nothing: index builds take no table lock
- [ ] Only other `CREATE INDEX` statements

It takes a SHARE lock. On a large table that is minutes of failed writes, which is why production uses `CREATE INDEX CONCURRENTLY`.

### Requests are piling up and you suspect lock waits. Where do you look first?
- [ ] The `pg_class` catalog for table sizes
- [ ] `EXPLAIN ANALYZE` of the slow endpoint's query
- [x] `pg_stat_activity` with `pg_blocking_pids(pid)`, following the chain to the root blocker
- [ ] The PostgreSQL error log for deadlock messages only

The root is often an idle transaction holding a lock. `EXPLAIN` cannot show time spent waiting on other sessions.

## Exam questions
- Why can ALTER TABLE take your service down for minutes?
- Two transactions deadlock updating the same two rows. How do you prevent it?
- What does SKIP LOCKED let you build?
