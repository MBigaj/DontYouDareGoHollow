# Redis Beyond Caching

> **Why this matters for you:** Redis also does rate limiting, locks and streams, each with sharp edges.

## You should be able to
- Use Redis data structures for counters, leaderboards and queues
- Explain why Redis locks are not safe for correctness without fencing
- Know Redis persistence and eviction trade-offs

## Lesson
Redis runs commands one at a time on a single thread. Every command is atomic, and one slow command (`KEYS *`, deleting a million-member set with `DEL`) stalls every client. Use `SCAN` and `UNLINK` instead. Its value beyond caching comes from its data structures, and each one has a sharp edge.

**Counters and leaderboards.**

- `INCR` and `INCRBY` are atomic, so they make counters that need no locks.
- **Sorted sets** keep members ordered by score. `ZINCRBY lb 50 user:7` updates a leaderboard, `ZREVRANGE lb 0 9 WITHSCORES` gives the top ten, and `ZREVRANK` gives one user's position. All are O(log N).
- HyperLogLog (`PFADD`, `PFCOUNT`) counts unique visitors in 12 KB with about 1% error.

**Rate limiting.** The fixed window is `INCR rl:user:7:202610261805` plus `EXPIRE 60`, allowing 100 per key. It is cheap but leaky: 100 requests at 18:05:59 and 100 more at 18:06:00 pass, which is 200 in two seconds. A **sliding window log** keeps one sorted-set entry per request, scored by timestamp, and must run as one atomic unit:

```lua
-- KEYS[1] = rl:user:7   ARGV: now_ms, window_ms, limit, request_id
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1] - ARGV[2])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then return 0 end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return 1
```

A Lua script (or a Redis Function) runs without interleaving, which a check-then-add from Python never can. When per-request memory is too much, a sliding-window *counter* (two fixed windows, weighted) or a token bucket in Lua gives a close approximation.

**Queues.**

- **Lists**: `LPUSH` plus `BRPOP` is a queue, but a worker that crashes after popping loses the job. `LMOVE` into a processing list makes it recoverable.
- **Streams** are the real tool. `XADD` appends; consumer groups (`XREADGROUP`) share entries between workers. Each entry stays in a pending list until `XACK`, and `XAUTOCLAIM` hands stuck entries to a live worker. That is at-least-once delivery, so consumers must be idempotent, exactly as with RabbitMQ.
- **Pub/Sub** is fire-and-forget: a subscriber that is down misses the message for good. Use it for cache-invalidation hints, never for work.

**Locks are where Redis bites.** The basic lock is `SET lock:report <random token> NX PX 30000`. Release it with a Lua script that deletes the key *only if it still holds your token*. A plain `DEL` can delete a lock someone else acquired after yours expired.

Even done right, a lease lock is not a correctness guarantee. Your process takes the lock, then pauses: a GC stop, a CPU-starved container, a slow network. The lease expires, another worker takes the lock, and your process wakes up and writes anyway. Two holders, one resource. **Redlock**, which acquires the lock on a majority of independent Redis nodes, does not fix this. Its safety still rests on timing assumptions (bounded pauses and clock drift), and that is the core of Martin Kleppmann's well-known critique. The fix is a **fencing token**: a number that increases with every acquisition, sent with each write, and checked by the storage, which rejects anything older than the last token it saw. Redis cannot enforce that on your database. So the rule:

- Redis locks are fine for **efficiency**, such as not running the same expensive job twice.
- For **correctness**, such as not charging a card twice, use the database: a row lock, an advisory lock, a unique constraint or a version check.

**Persistence.**

- **RDB** writes a point-in-time snapshot every few minutes. A crash loses everything since the last snapshot.
- **AOF** logs every write. With the default `appendfsync everysec`, a crash loses about a second; `always` loses nothing but costs write throughput.

With both enabled, Redis restores from the AOF on restart, since it is more complete. Replication to replicas is asynchronous, so a failover can lose recent writes whatever the persistence setting.

**Eviction.** When `maxmemory` is reached, `maxmemory-policy` decides. `noeviction` rejects writes; `allkeys-lru` or `allkeys-lfu` evicts any key; `volatile-*` policies evict only keys with a TTL. A pure cache wants `allkeys-lru`. But put rate-limit counters, locks or stream data on the same instance under `allkeys-lru`, and memory pressure silently evicts them like any cache entry. Give queues and locks their own instance with `noeviction`, and keep the cache separate.

## Quiz
### A rate limiter allows 100 requests per minute using `INCR` on a per-minute key with `EXPIRE 60`. What is its flaw?
- [ ] `INCR` is not atomic under concurrent requests
- [x] A client can send 100 requests at the end of one minute and 100 at the start of the next: 200 in two seconds
- [ ] The key never expires if the client stops sending
- [ ] It needs a lock around every `INCR`

Fixed windows reset at the boundary. A sliding window counts the last 60 seconds from now, wherever that falls.

### A sliding-window limiter stores each request in a sorted set scored by timestamp. How should a check run?
- [ ] `ZCARD` from Python, then `ZADD` if under the limit
- [ ] `ZADD` first, then delete the entry if the count is over the limit
- [ ] `ZRANGE` the whole set and count in Python
- [x] Trim old entries, count, add and set the expiry in one Lua script

Separate round trips let two requests both see 99 and both pass. A script runs as one atomic unit.

### Why release a Redis lock with a compare-and-delete script instead of a plain `DEL`?
- [x] If your lease expired and another client took the lock, `DEL` would delete *their* lock
- [ ] `DEL` is slower than a Lua script
- [ ] `DEL` does not work on keys set with `NX`
- [ ] A plain `DEL` leaves the key's TTL behind

Store a random token as the value and delete only if it still matches. Otherwise one slow worker frees the lock for everyone.

### Why is a Redis lock, Redlock included, not enough to protect correctness on its own?
- [ ] Redis loses all keys on restart
- [ ] Locks cannot have an expiry
- [x] A paused holder can act after its lease expired while a new holder runs; only storage that checks a fencing token stops the stale write
- [ ] Redis is single-threaded, so locks are never needed

Lease locks assume bounded pauses and clock drift. When those assumptions break, the database must reject the stale writer.

### Redis runs AOF with `appendfsync everysec` and crashes. How much data can be lost?
- [x] About the last second of writes
- [ ] Nothing: AOF logs every write before replying
- [ ] Everything since the last RDB snapshot
- [ ] All data, because AOF is only replayed on replicas

`everysec` flushes the log to disk once a second. `always` closes that gap at a large throughput cost.

### One Redis instance holds the cache, the rate-limit counters and job locks, with `maxmemory-policy allkeys-lru`. Memory fills up. What happens?
- [ ] Writes are rejected until memory is freed
- [ ] Only the cache keys are evicted, because they have TTLs
- [ ] Redis swaps the oldest keys to disk
- [x] Counters and locks can be evicted like any cache entry, silently resetting limits and freeing locks

`allkeys-lru` evicts any key. Keep the cache on its own instance, and run queues and locks with `noeviction`.

## Exam questions
- How would you build a sliding-window rate limiter in Redis?
- Why is Redlock controversial?
- What happens to your data when Redis restarts with AOF vs RDB?
