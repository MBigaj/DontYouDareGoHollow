# Partitioning and Sharding

> **Why this matters for you:** Tier 3 designs need data split across machines; picking the key is the whole game.

## You should be able to
- Partition tables in PostgreSQL (range, list, hash) and know the trade-offs
- Choose a shard key and explain hot spots and resharding
- Explain what cross-shard queries and transactions cost

## Lesson
The two words get mixed up, but they solve different problems. **Partitioning** splits one table into pieces *inside one database*. **Sharding** splits the data across *several database servers*. Partitioning makes a big table manageable; sharding is what you do when one machine can no longer take the writes, the storage or the connections.

**Declarative partitioning in PostgreSQL.** The parent table holds no rows; each partition is a real table with its own indexes.

```sql
CREATE TABLE events (
  tenant_id bigint NOT NULL,
  occurred_at timestamptz NOT NULL,
  payload jsonb
) PARTITION BY RANGE (occurred_at);

CREATE TABLE events_2026_10 PARTITION OF events
  FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
```

- **Range** partitioning (usually by time) fits logs, events and orders by month.
- **List** partitioning fits a small set of known values, such as region or plan tier.
- **Hash** partitioning spreads rows evenly when there is no natural range.

What you gain:

- **Pruning.** A query filtering on the partition key reads only the matching partitions.
- **Cheap retention.** `DETACH PARTITION ... CONCURRENTLY` and `DROP TABLE` remove a month in milliseconds, with none of the bloat and WAL of `DELETE FROM events WHERE occurred_at < ...`.
- **Smaller per-partition indexes**, and vacuum per partition.

What it costs:

- Queries that do not filter on the key touch every partition.
- Primary keys and unique constraints must include the partition key, because uniqueness is only enforced within each partition.
- Thousands of partitions slow down planning.

Automate creating partitions ahead of time, or inserts for a missing month fail. A `DEFAULT` partition catches strays.

**Sharding: the key is the whole game.** A good shard key:

- appears in nearly every query, so a request goes to one shard;
- has many values, spread evenly;
- keeps data that is read together on one shard.

For a multi-tenant SaaS, `tenant_id` usually wins: a tenant's orders, customers and invoices sit together, and joins and transactions inside a tenant stay local.

**What gets harder** is everything that crosses the key. Shard orders by `customer_id`, and then:

- "all orders for merchant X last week" must ask every shard and merge the results (scatter-gather), so it is as slow as the slowest shard;
- looking up an order by its public number needs a separate lookup table from number to shard;
- a transaction touching two customers spans two databases, so it becomes a saga or two-phase commit;
- unique constraints across shards no longer exist, so IDs come from UUIDv7 or a Snowflake-style generator, not a sequence per database;
- reports and analytics move to a warehouse fed by change data capture.

**Hot spots.** Hash sharding spreads keys evenly, but one enormous tenant is still one key on one shard. Range sharding on a growing key, such as an auto-increment id or a timestamp, is worse: every new insert lands on the last shard while the others idle. Detect hot spots from per-shard CPU, QPS and size, not cluster averages. Fix them by moving the big tenant to its own shard, by salting a hot key into sub-keys, or by changing the key.

**Resharding.** `hash(key) % N` looks simple until N changes: going from 8 to 9 shards remaps almost every key. Production systems shard into many *logical* shards (say 1,024) mapped to a few physical databases through a directory, or use consistent hashing. Adding capacity then means moving whole logical shards, a fraction of the data, with a dual-write or replication cutover.

**Before you shard,** use the cheaper tools: a bigger instance, read replicas, caching, partitioning, archiving cold data, and moving a hot table to its own database. Sharding is a one-way door that touches every query in the codebase. Tools like Citus make the mechanics easier, but the key-choice trade-offs stay yours.

## Quiz
### What is the difference between partitioning and sharding?
- [x] Partitioning splits a table within one database; sharding splits data across several servers
- [ ] They are the same thing under different names
- [ ] Partitioning is for reads and sharding is for writes
- [ ] Sharding splits columns into separate tables; partitioning splits rows

Partitioning gives pruning and cheap retention on one machine. Sharding buys write throughput, storage and connections beyond one machine.

### An `events` table is range-partitioned by month with 13 months of retention. How do you delete the oldest month?
- [ ] `DELETE FROM events WHERE occurred_at < $1`, in batches
- [ ] `TRUNCATE events`, then reload the last 12 months
- [x] Detach the oldest partition and drop it
- [ ] `VACUUM FULL` on the oldest partition

Dropping a partition removes the data as a file, with no dead tuples, WAL flood or vacuum afterwards. That is half the reason to partition by time.

### Orders are sharded by `hash(customer_id)`. Which query gets harder?
- [ ] One customer's order history
- [x] All orders for one merchant last week
- [ ] Inserting a new order for a customer
- [ ] Updating the status of a customer's order

The merchant's orders are spread across every shard, so the query fans out and merges. Plan a lookup table or an analytics store for it.

### Shards are chosen by `hash(key) % 8`, and you add a ninth server. What happens?
- [ ] Only the keys of one shard move to the new server
- [ ] Nothing moves; new keys start using the ninth shard
- [ ] Each shard sends one ninth of its keys to the new server
- [x] Most keys now map to a different shard and must move

Changing the modulus remaps almost everything. Many logical shards behind a directory, or consistent hashing, keep moves small.

### Orders are range-sharded by their auto-increment id. What goes wrong?
- [ ] Reads become scatter-gather across every shard
- [x] Every new insert lands on the last shard, which becomes a hot spot
- [ ] Ids collide across shards
- [ ] Old shards can no longer be read

A growing key concentrates all new writes in one range. Hash the key, or choose one that spreads.

### On a table partitioned by `created_at`, `ALTER TABLE orders ADD UNIQUE (order_number)` fails. Why?
- [ ] Unique constraints are not supported on partitioned tables at all
- [ ] The column needs an index first
- [x] Uniqueness is only enforced per partition, so the constraint must include the partition key
- [ ] Partitioned tables only support primary keys on `id`

There are no global indexes across partitions. Enforce global uniqueness another way, such as a separate lookup table.

## Exam questions
- How would you shard an orders table, and what queries get harder?
- What is a hot partition, and how do you detect and fix one?
- Partitioning vs sharding: what problem does each solve?
