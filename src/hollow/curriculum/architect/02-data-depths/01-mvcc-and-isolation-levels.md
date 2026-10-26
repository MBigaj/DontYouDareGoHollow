# MVCC and Isolation Levels

> **Why this matters for you:** Most subtle data bugs you will meet are isolation bugs; MVCC explains why PostgreSQL behaves as it does.

## You should be able to
- Explain MVCC: tuple versions, snapshots, visibility and vacuum
- Name the anomalies each isolation level allows, with examples
- Pick an isolation level (or explicit locking) for a given race

## Lesson
PostgreSQL never updates a row in place. Every row on disk is a *tuple version* stamped with `xmin`, the transaction that created it, and `xmax`, the transaction that deleted or replaced it. An `UPDATE` writes a new version and sets `xmax` on the old one. A *snapshot* decides which versions a statement can see: the ones committed before the snapshot was taken, and not yet deleted from its point of view. That is MVCC, and it is why readers never block writers and writers never block readers.

**Vacuum is the other half.** Old versions stay on disk until no snapshot could still need them. Autovacuum then marks the space as reusable. The oldest open snapshot in the cluster sets that horizon. A session left `idle in transaction` for six hours, or one long report, holds back vacuum on *every* table, and hot tables bloat: more pages to read, bigger indexes, slower queries. Watch `pg_stat_activity` for old `xact_start`, and set `idle_in_transaction_session_timeout`.

**The isolation levels, as PostgreSQL implements them:**

- **READ COMMITTED** (the default): each *statement* gets a fresh snapshot. Two reads in one transaction can disagree, and a read-modify-write in application code loses updates.
- **REPEATABLE READ**: one snapshot for the whole transaction, taken at its first statement. In PostgreSQL this is snapshot isolation, which also hides phantoms. If you try to update a row someone else changed since your snapshot, you get a serialization failure instead of a silent overwrite.
- **SERIALIZABLE**: snapshot isolation plus SSI, which tracks read/write dependencies and aborts one transaction when the result could not have come from running them one at a time. READ UNCOMMITTED exists only in name; it behaves as READ COMMITTED.

**The lost update.** Two requests run `SELECT balance` (both see 500), compute 400 in Python and write it back. One subtraction vanishes. You have four fixes, in order of how often you should reach for them:

1. Let the database do the arithmetic: `UPDATE accounts SET balance = balance - 100 WHERE id = $1`. Under READ COMMITTED the second update waits for the first one's row lock, then re-evaluates against the newly committed row. Both subtractions land.
2. Lock what you read: `SELECT ... FOR UPDATE`, then update in the same transaction.
3. Optimistic concurrency: `UPDATE ... SET version = version + 1 WHERE id = $1 AND version = $2`, and treat zero rows updated as a conflict.
4. REPEATABLE READ or SERIALIZABLE, with a retry loop.

**Write skew** is the anomaly REPEATABLE READ lets through. A rota needs at least one doctor on call. Alice and Bob are both on call, and each, in their own transaction, checks "two are on call" and takes themselves off. Each transaction updates a *different* row, so no row conflict is ever detected, and both commit. The invariant spans rows, and only SERIALIZABLE, a lock on every row the check read, or a constraint can protect it.

**Serializable has a contract.** Any transaction can fail with SQLSTATE `40001`, and the caller must rerun the *whole* transaction, reads included. In a FastAPI service that means the unit of work is a retryable function, not a session opened in a dependency and committed somewhere later.

```python
for attempt in range(3):
    try:
        async with session.begin():
            await transfer(session, src, dst, amount)
        break
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) != "40001" or attempt == 2:
            raise
```

Pick **FOR UPDATE** when you know exactly which rows guard the invariant and contention is low. Pick **SERIALIZABLE** when the invariant is spread across queries you might not think of. You pay with retries and some false positives, but you stop guessing which rows to lock.

## Quiz
### Under READ COMMITTED, two requests each run `SELECT balance` (500), subtract 100 in Python and write the result back. What is the final balance?
- [ ] 300, because the row lock makes the second write wait for the first
- [x] 400: one subtraction is lost, because both wrote a value computed from the same old read
- [ ] PostgreSQL raises a deadlock error
- [ ] PostgreSQL raises a serialization failure

The second write waits for the lock, but it still writes the 400 it computed from a stale read. Do the arithmetic in the `UPDATE`, or lock the row when you read it.

### What does an `UPDATE` do to a row on disk in PostgreSQL?
- [ ] Overwrites the row in place and logs the old value to the WAL
- [ ] Moves the row to the end of the table
- [ ] Locks the page until the transaction commits
- [x] Writes a new tuple version and marks the old one as replaced with `xmax`; vacuum reclaims it later

That is why update-heavy tables need healthy autovacuum, and why an update can grow a table.

### A session has sat `idle in transaction` for six hours. Why are unrelated hot tables bloating?
- [x] Its snapshot holds back the vacuum horizon, so dead tuples everywhere newer than it cannot be removed
- [ ] It holds an exclusive lock on those tables
- [ ] Idle transactions disable autovacuum for the whole database
- [ ] It fills the WAL, which stops vacuum from writing

Vacuum can only remove versions no open snapshot could still see. `idle_in_transaction_session_timeout` stops the leak.

### Two on-call doctors each check "at least two are on call" and take themselves off, in separate transactions. Which setting stops both from committing?
- [ ] REPEATABLE READ, because both read the same snapshot
- [ ] READ COMMITTED with a retry loop
- [x] SERIALIZABLE, or locking every row the check read with `FOR UPDATE`
- [ ] An index on the `on_call` column

That is write skew: each transaction updates a different row, so snapshot isolation sees no conflict. The invariant spans rows.

### Your service switches a transfer to SERIALIZABLE. What must the application code now do?
- [ ] Nothing: PostgreSQL retries failed transactions itself
- [ ] Take `FOR UPDATE` locks as well, or SERIALIZABLE does nothing
- [ ] Retry only the final `COMMIT` when it fails
- [x] Catch SQLSTATE `40001` and rerun the whole transaction, reads included

A retry must redo the reads, because the decision was based on them. Make the unit of work one retryable function.

### Two sessions run `UPDATE accounts SET balance = balance - 100 WHERE id = 1` at the same time under READ COMMITTED. Starting from 500, what happens?
- [ ] The second fails with a serialization error
- [x] The second waits for the first's row lock, then applies to the newly committed row: 300
- [ ] Both read 500, so the result is 400
- [ ] They deadlock, and PostgreSQL aborts one

READ COMMITTED re-checks the updated row after the lock is released, so in-database arithmetic is safe without raising the isolation level.

## Exam questions
- Two requests read a balance and both subtract 100. Which isolation level stops it, and how?
- What is write skew, and why does REPEATABLE READ not prevent it?
- Why do long-running transactions cause table bloat?
- SERIALIZABLE vs SELECT ... FOR UPDATE: when would you pick each?
