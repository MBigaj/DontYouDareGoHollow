# Zero-Downtime Migrations

> **Why this matters for you:** Schema changes on a live service are where data work meets deployment; expand and contract is the core skill.

## You should be able to
- Run expand/contract migrations with Alembic across several deploys
- Backfill large tables safely
- Add constraints and indexes without long locks (CONCURRENTLY, NOT VALID)

## Lesson
During an ECS rolling deploy, old and new tasks serve traffic side by side for minutes. So every schema change must work with **both the code before it and the code after it**. That one rule produces the whole discipline, usually called *expand and contract*.

**Renaming `name` to `full_name`, with zero downtime, takes several deploys:**

1. **Expand.** Add `full_name` as a nullable column. Old code ignores it.
2. **Dual write.** Deploy code that writes both columns and still reads `name`.
3. **Backfill** `full_name` from `name` for existing rows, in batches (below).
4. **Switch reads.** Deploy code that reads `full_name` and still writes both, so a rollback stays safe.
5. **Stop writing** `name`. Deploy.
6. **Contract.** Drop `name` in a later migration, once no running code mentions it.

A plain `ALTER TABLE ... RENAME COLUMN` is instant, but the old tasks still running break the moment it commits. Expand migrations run *before* the new code ships; contract migrations run *after* the old code is gone. In Alembic that means one revision per step, not one revision per feature.

**Backfills do not belong in the migration.** One `UPDATE users SET full_name = name` on 200 million rows is a single transaction that holds row locks for its whole run, writes a new version of every row (the table roughly doubles until vacuum catches up), floods the WAL and leaves the replicas minutes behind. Run it as a separate job instead:

```python
last_id = 0
while True:
    result = await session.execute(
        text("""
            UPDATE users SET full_name = name
            WHERE id IN (
                SELECT id FROM users
                WHERE id > :last AND full_name IS NULL
                ORDER BY id LIMIT 5000
            )
            RETURNING id
        """),
        {"last": last_id},
    )
    ids = result.scalars().all()
    await session.commit()
    if not ids:
        break
    last_id = max(ids)
    await asyncio.sleep(0.2)  # leave room for production traffic and replication
```

Small committed batches, walking the primary key, idempotent (`full_name IS NULL`) so it can stop and resume. Throttle on replica lag, not just a fixed sleep.

**Columns with defaults.** Since PostgreSQL 11, `ADD COLUMN status text NOT NULL DEFAULT 'new'` is a catalog-only change: the default is stored once and served for old rows, so it is instant on any table size. That holds only for a *non-volatile* default. `DEFAULT gen_random_uuid()` or `clock_timestamp()` must compute a value per row, so the table is rewritten under ACCESS EXCLUSIVE. Changing a column's type, such as `int` to `bigint`, also rewrites; do that as a new column with a backfill and a swap.

**Constraints without the long lock.** `ALTER TABLE ... ALTER COLUMN email SET NOT NULL` scans the whole table under ACCESS EXCLUSIVE. Split the work instead:

```sql
ALTER TABLE users ADD CONSTRAINT users_email_nn CHECK (email IS NOT NULL) NOT VALID;  -- instant
ALTER TABLE users VALIDATE CONSTRAINT users_email_nn;   -- scans, but reads and writes continue
ALTER TABLE users ALTER COLUMN email SET NOT NULL;      -- PG 12+: uses the valid check, no scan
ALTER TABLE users DROP CONSTRAINT users_email_nn;
```

`NOT VALID` makes the constraint apply to new writes immediately and skips checking old rows; `VALIDATE` checks them under a weaker lock. Foreign keys work the same way: add `NOT VALID`, then validate.

**Indexes** are built with `CREATE INDEX CONCURRENTLY`, which cannot run inside a transaction. Alembic wraps each revision in one, so step out of it:

```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "orders_customer_idx", "orders", ["customer_id"], postgresql_concurrently=True
        )
```

And every migration starts with `SET lock_timeout = '3s'`. A migration that cannot get its lock should fail and retry, not queue every request behind it.

## Quiz
### A running service reads `users.name`. You want it renamed to `full_name` with zero downtime. Which plan is safe?
- [ ] `ALTER TABLE ... RENAME COLUMN`, then deploy the code that reads `full_name`
- [ ] Deploy code that reads `full_name` first, then rename the column
- [x] Add `full_name`, dual-write, backfill, switch reads, stop writing `name`, then drop it: each a separate deploy
- [ ] Rename the column and deploy the code inside one database transaction

Every step stays compatible with the code before and after it, so a rolling deploy or a rollback never meets a missing column.

### During an ECS rolling deploy, what must each migration be compatible with?
- [x] Both the old and the new version of the code, because they serve traffic side by side
- [ ] Only the new version, since the migration runs first
- [ ] Only the old version, since the new tasks start after it
- [ ] Neither: ECS drains all old tasks before starting new ones

Rolling deploys overlap versions for minutes. That overlap is why renames and drops need several steps.

### You must backfill a new column on 200 million rows in production. How?
- [ ] One `UPDATE` in the Alembic migration, so it runs exactly once
- [ ] One `UPDATE` at night, when traffic is low
- [ ] Copy the table, update the copy, and swap the names
- [x] A separate job: small committed batches by primary key, idempotent, throttled on replica lag

One giant update holds locks, doubles the table until vacuum and floods replication. Small batches keep each of those bounded.

### On PostgreSQL 16 you run `ALTER TABLE orders ADD COLUMN status text NOT NULL DEFAULT 'new'` on 500 million rows. What happens?
- [ ] The table is rewritten under ACCESS EXCLUSIVE for many minutes
- [x] It is a fast catalog-only change: a constant default is stored once and served for existing rows
- [ ] PostgreSQL refuses `NOT NULL` with a default on a non-empty table
- [ ] Existing rows get `NULL` and only new rows get `'new'`

Since PostgreSQL 11, non-volatile defaults need no rewrite. A volatile default such as `gen_random_uuid()` still rewrites the table.

### How do you make an existing column `NOT NULL` without a long ACCESS EXCLUSIVE scan?
- [x] Add `CHECK (col IS NOT NULL) NOT VALID`, `VALIDATE` it, then `SET NOT NULL`, which uses the check, and drop the check
- [ ] `SET NOT NULL` with `CONCURRENTLY`
- [ ] Add a partial index on rows where the column is null
- [ ] `SET NOT NULL` inside a transaction with a short `lock_timeout`

`VALIDATE` scans under a lock that lets reads and writes continue. `SET NOT NULL` then skips its own scan, since PostgreSQL 12.

### An Alembic revision calls `op.create_index(..., postgresql_concurrently=True)` and fails: `CREATE INDEX CONCURRENTLY cannot run inside a transaction block`. What is the fix?
- [ ] Drop `postgresql_concurrently` and build it normally
- [ ] Set `transaction_per_migration = False` in `env.py`
- [x] Run it inside `op.get_context().autocommit_block()`
- [ ] Wrap the call in `op.batch_alter_table`

The autocommit block steps outside Alembic's transaction just for that operation. A failed concurrent build leaves an `INVALID` index to drop before retrying.

## Exam questions
- Rename a column used by a running service with zero downtime. Step by step.
- How do you backfill 200 million rows without hurting production?
- Why can adding a NOT NULL column with a default be slow, or not, depending on version?
