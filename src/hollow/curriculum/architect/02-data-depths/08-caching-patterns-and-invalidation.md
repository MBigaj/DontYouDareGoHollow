# Caching Patterns and Invalidation

> **Why this matters for you:** Caching is easy to add and hard to keep correct; stampedes and stale data are senior-level failure stories.

## You should be able to
- Compare cache-aside, read-through, write-through and write-behind
- Invalidate correctly, and choose TTLs deliberately
- Prevent cache stampedes and handle a cold cache

## Lesson
A cache trades correctness for speed. The senior work is choosing how much staleness you accept, keeping writes from leaving it wrong, and surviving the moments it is empty.

**The four patterns.**

- **Cache-aside** (lazy loading): the application checks the cache; on a miss it reads the database and stores the result with a TTL. It is the default, and what nearly every FastAPI-plus-Redis service runs.
- **Read-through**: the same flow, but a caching layer or library loads misses itself, and the app only talks to the cache.
- **Write-through**: every write goes to the cache and the database synchronously. Reads are always warm, but writes are slower and the cache fills with data nobody reads.
- **Write-behind** (write-back): writes land in the cache and reach the database later, in batches. Very fast, until a cache node dies with acknowledged writes the database never got. Use it only for data you can afford to lose, such as view counters.

**Invalidation: delete, don't set, and do it after commit.**

```python
async with session.begin():
    product.price = new_price
# the transaction has committed here
await redis.delete(f"product:{product.id}")
```

Why *delete* rather than writing the new value? Two concurrent writers can set the cache in the opposite order from their commits and leave the older value cached for a full TTL. A delete just forces the next reader to load fresh. Why *after* commit? Delete inside the transaction, and a reader arriving between the delete and the commit loads the *old* row and caches it again.

Even this has a race: a reader misses, loads the old row, the writer commits and deletes, and only then does the slow reader store its stale copy. The TTL is your safety net, so never cache without one. For important data, add a delayed second delete, or put a version in the key. When invalidation must survive crashes (the process dies between commit and delete), publish it reliably through an outbox or change data capture, the same way you publish any other event.

**Choose TTLs deliberately.** A TTL is a promise: "this can be up to N seconds stale." Pick N from what the product tolerates, not from habit. A price might get 30 seconds; a feature-flag set gets 5 seconds; a user's own profile is better not cached, or invalidated on every write. Add jitter (`ttl = 300 + random.randint(0, 60)`) so keys cached together, after a deploy or warm-up, do not all expire together.

**Stampedes.** A hot key expires, and 5,000 requests miss in the same second and all run the expensive query. The database falls over, and the cache stays empty because nothing finishes. The defences:

- **Single flight.** The first request to miss takes a short lock (`SET key:lock 1 NX PX 5000`) and recomputes; the others wait briefly and reread, or get the stale value.
- **Stale while revalidate.** Store a soft expiry inside the value, and a longer hard TTL on the key. After the soft expiry, one request refreshes in the background while everyone keeps getting the slightly old value.
- **Early refresh.** Refresh hot keys shortly before they expire, either probabilistically or from a background job.

A **cold cache** after a Redis restart or flush is a stampede on every key at once. Warm the hottest keys before taking traffic, and make sure the database can survive a short period at a 0% hit rate.

**Negative caching.** Cache "not found" for a short TTL too. Otherwise requests for ids that do not exist, such as bots probing `/users/999999999`, always reach the database.

**When a cache is the wrong answer:**

- The query is slow because it is wrong, for example a missing index. Fix it with `EXPLAIN` first.
- The data must be exact: balances, stock reservations, permissions.
- The hit rate would be low: long-tail keys, or per-user results nobody rereads.
- Staleness would confuse users more than slowness.

Every cache adds a failure mode, an invalidation path and something more to monitor. Measure the hit rate after you add one; a cache at 20% hits is mostly overhead.

## Quiz
### In a cache-aside service, what should the code do after updating a product's price in PostgreSQL?
- [ ] Write the new price into the cache, then commit
- [x] Commit, then delete the cache key, so the next read loads fresh data
- [ ] Nothing: the TTL will refresh it eventually
- [ ] Delete the key, then commit

Deleting after commit avoids caching the old row, and deleting rather than setting avoids two writers caching in the wrong order.

### A hot key expires, and 5,000 requests hit the database in the same second. What is the right fix?
- [ ] Raise the TTL to 24 hours
- [ ] Scale up the database instance
- [x] Let one request recompute under a short lock while the others wait or get the stale value
- [ ] Remove the TTL so the key never expires

Single-flight recomputation, or serving stale while one request refreshes, turns 5,000 identical queries into one.

### Why delete the cache key *after* the transaction commits, not inside it?
- [x] A reader arriving between the delete and the commit would load the old row and cache it again
- [ ] Redis rejects deletes during an open database transaction
- [ ] Deleting first is slower
- [ ] The commit could fail, and then you would have to restore the key

Inside the transaction, the old row is still the committed one, so any reader in that gap re-caches stale data for a full TTL.

### What is the main risk of a write-behind cache?
- [ ] Reads are slower than with cache-aside
- [ ] The cache fills with data nobody reads
- [ ] Every write waits for the database
- [x] Writes acknowledged to the client can be lost if the cache node dies before flushing them

Write-behind acknowledges before the database has the data. Use it only for data you can afford to lose.

### Why add random jitter to TTLs?
- [ ] It improves the hit rate on rarely used keys
- [ ] Redis evicts keys with identical TTLs first
- [x] Keys cached at the same moment, such as after a deploy, would otherwise expire together and stampede
- [ ] It hides staleness from users

Synchronised expiry turns a warm cache into many simultaneous misses. Jitter spreads them out.

### An endpoint is slow because its query sequentially scans a 40-million-row table, and each user's filter is different. What do you do first?
- [x] Fix the query with `EXPLAIN` and an index; a cache would have a low hit rate here
- [ ] Put the endpoint's response in Redis for 10 minutes
- [ ] Add a read replica for the endpoint
- [ ] Cache the whole table in application memory

With per-user filters the cache would rarely hit, and the scan would still run on every miss. Fix the query itself.

## Exam questions
- A hot key expires and 5,000 requests hit the database at once. What now?
- How do you keep a cache consistent with PostgreSQL on writes?
- When is a cache the wrong answer to a slow endpoint?
