# Replication and Read Replicas

> **Why this matters for you:** Read replicas are an easy scaling win until replication lag breaks read-your-writes.

## You should be able to
- Explain streaming replication, synchronous vs asynchronous
- Handle replication lag in the application
- Plan failover and know what can be lost

## Lesson
**Streaming replication** ships the primary's write-ahead log to standbys, which replay it continuously. It copies the whole cluster byte for byte, so a standby is an exact copy, just behind. With `hot_standby` on, the standby serves read-only queries: that is a read replica. RDS read replicas for PostgreSQL work this way. RDS Multi-AZ standbys are the other use: a synchronous copy kept for failover, not readable in the classic single-standby setup. Aurora differs again, with shared storage and typically millisecond lag, but the application rules below still apply.

**Asynchronous vs synchronous.** By default replication is asynchronous: the primary commits, answers the client, and ships the WAL whenever it can. Replicas lag by milliseconds normally, and by seconds or minutes under a bulk load, a long query on the replica, or a network blip. With `synchronous_standby_names` set, a commit waits for a standby, and `synchronous_commit` decides how far:

- `on`: the standby has flushed the WAL to disk. No committed transaction is lost on failover.
- `remote_apply`: the standby has also replayed it, so a read there sees the write.

You pay for this on every commit, with a network round trip of latency. And if the only synchronous standby goes down, writes stop. `ANY 1 (s1, s2)` lets either of two standbys acknowledge.

**What failover loses.** Under async replication, transactions the primary committed but had not yet shipped are gone when a replica is promoted. Your RPO is your replication lag at that moment. Two more things happen in the application: the writer endpoint moves, so the pool must drop dead connections instead of handing them out, and in-flight transactions fail and must be retried by the caller.

**Read-your-writes is the bug everyone ships.** A user saves their profile; the redirect loads the page from a replica that has not replayed the update yet; the old profile appears and the user saves again. The fixes, from blunt to precise:

1. **Stick to the primary after a write.** For a few seconds after a user writes, route their reads to the primary, using a cookie or a short-lived key.
2. **Wait for the replica to catch up.** After the write, record `pg_current_wal_lsn()`. Before reading from a replica, check `pg_last_wal_replay_lsn() >= that_lsn`, and fall back to the primary if it has not.
3. **`remote_apply`** on the replicas you read from, if you accept the write latency.

**Some reads never belong on a replica:**

- reads that decide a write, such as "is there stock left?" before reserving it;
- reads inside a transaction that also writes;
- anything that must reflect the user's last action;
- uniqueness or permission checks.

Replicas suit dashboards, search, feeds, exports and reports: reads where a few seconds of staleness is invisible.

**Replicas push back.** A long analytics query on a replica can fail with *canceling statement due to conflict with recovery*. Vacuum on the primary removed row versions the query could still see, and replay has to apply that removal. You can make the replica wait (`max_standby_streaming_delay`, at the cost of lag), or report its oldest snapshot to the primary (`hot_standby_feedback = on`, at the cost of bloat on the primary). Heavy analytics belong on a dedicated replica with those settings, or in a warehouse.

**Measure lag where it hurts.** On the primary, `pg_stat_replication.replay_lag`; on RDS, the `ReplicaLag` metric. On a replica, `now() - pg_last_xact_replay_timestamp()` reads high when the primary is simply idle, so read it alongside write activity. Alert on lag, and make the application degrade gracefully (route to the primary) when a replica falls behind.

## Quiz
### A user saves their profile, and the next page, read from an async replica, shows the old one. What fixes it?
- [ ] Raise the replica's instance size so it replays faster
- [ ] Add a cache in front of the replica
- [ ] Switch the replica to logical replication
- [x] Read from the primary for that user right after a write, or wait until the replica has replayed the write's LSN

Async replicas are always somewhat behind. The application has to route around the lag where a user expects to see their own write.

### The primary dies under asynchronous replication and a replica is promoted. What can be lost?
- [x] Transactions the primary had committed but not yet shipped to the replica
- [ ] Nothing: a commit only returns after the replica has the WAL
- [ ] Only uncommitted transactions, which would be rolled back anyway
- [ ] The whole replica, which must be rebuilt from a snapshot

Async means the client heard "committed" before any standby had the data. The window is your replication lag.

### Which read should stay on the primary?
- [ ] A dashboard of yesterday's signups
- [x] Checking stock before reserving the last item
- [ ] A full-text search over product descriptions
- [ ] A nightly CSV export for finance

A read that decides a write must see the latest data. A stale "1 in stock" sells the same item twice.

### How do you guarantee read-your-writes from a replica exactly, without pinning the user to the primary?
- [ ] Sleep for one second after every write
- [ ] Read from the replica twice and compare the results
- [x] Record `pg_current_wal_lsn()` after the write, and read from the replica only once `pg_last_wal_replay_lsn()` has passed it
- [ ] Use `SERIALIZABLE` on the replica

The LSN marks a position in the WAL. Once the replica has replayed past it, it contains the write.

### A long report on a replica fails with "canceling statement due to conflict with recovery". Why?
- [x] Replay had to remove row versions the query could still see, because vacuum on the primary cleaned them up
- [ ] Replicas cannot run queries longer than 30 seconds
- [ ] The report tried to write to the replica
- [ ] The replica ran out of `work_mem`

Replay cannot pause forever for one query. `max_standby_streaming_delay` and `hot_standby_feedback` trade that cancellation for lag or primary bloat.

### You set `synchronous_commit = remote_apply` with a single synchronous standby. What does it cost?
- [ ] Nothing measurable: replication runs in the background
- [ ] Reads on the primary become slower
- [ ] The standby can no longer serve reads
- [x] Every commit waits for the standby to apply it, and writes stop if that standby goes down

You buy consistent reads on the standby with write latency and availability. Listing several candidates with `ANY 1` softens the availability cost.

## Exam questions
- A user saves a profile and the next page shows the old one. Why, and how do you fix it?
- What do you lose if the primary dies under async replication?
- When would you not route reads to a replica?
