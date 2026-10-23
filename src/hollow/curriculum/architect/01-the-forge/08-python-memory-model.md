# Python Memory Model

> **Why this matters for you:** Leaks and bloat in long-running workers come from reference counting and the GC's blind spots.

## You should be able to
- Explain reference counting, the cyclic GC and when memory is returned to the OS
- Spot common leak patterns (caches, closures, globals)
- Measure the memory of objects and processes

## Lesson
CPython frees most objects through **reference counting**. Every object counts the references to it, and the moment that count reaches zero, the object is freed, right there in the middle of your code. No collector pause is involved.

Reference counting cannot free a **cycle**: `a.child = b; b.parent = a`. Each keeps the other's count above zero even when nothing else can reach them. The **cyclic garbage collector** exists for exactly this. It periodically looks for groups of objects that only reference each other, and frees them. It runs in three generations, checking young objects often and old ones rarely. It never frees anything your code can still reach.

That is why a real Python "leak" is almost always a reference you are still holding:
- A module-level dict or list used as a cache that only grows.
- `@lru_cache(maxsize=None)` on a function with unbounded inputs.
- `@lru_cache` on a method: the cache key includes `self`, so every instance stays alive as long as the cache does.
- Closures and callbacks registered on long-lived objects (signal handlers, event buses) that capture big objects.
- Exceptions kept with their tracebacks, which keep every frame's locals alive.

**Why RSS does not shrink.** Your worker processes a 2 GB job, the objects are freed, and yet the resident memory stays high. That is usually not a leak. CPython's small-object allocator (pymalloc) takes memory from the OS in arenas, and can only give an arena back when *every* object in it is free. A few survivors scattered across arenas pin them all. The C `malloc` underneath behaves similarly. The memory is reused for the next job, but it is not returned. The practical fixes:
- Avoid the spike: stream and paginate instead of loading everything.
- Recycle the process: Celery's `worker_max_tasks_per_child`, Gunicorn's `--max-requests`, or a fresh pod.

**Measuring.**
- `sys.getsizeof(obj)` is *shallow*: a list's size excludes the objects in it.
- `tracemalloc` snapshots show which lines allocated what is still alive.
- `memray` adds native allocations and flame graphs.
- Process RSS (from `psutil`, or container metrics) is the number the OOM killer uses. Watch its trend across many jobs, not one.

## Quiz
### What frees most objects in CPython?
- [x] Reference counting, the moment an object's count reaches zero
- [ ] The cyclic garbage collector, every few seconds
- [ ] The operating system when the function returns
- [ ] A background thread that sweeps the heap

The cyclic GC is only the backup for cycles.

### What does the cyclic garbage collector collect?
- [ ] Every object that has not been used for a while
- [ ] Objects still referenced from a global dict
- [x] Groups of objects that reference each other but are unreachable from your code
- [ ] Large objects over a size limit

Reachable objects are never collected, which is why caches leak.

### A worker's RSS stays high after a big job, even though the objects were freed. Why, usually?
- [ ] The cyclic GC never runs in workers
- [x] The allocator keeps freed memory for reuse; partly used arenas cannot go back to the OS
- [ ] Python memory can never be freed
- [ ] The job's objects are still referenced by the logging module

It is reused memory, not leaked memory. Streaming or recycling the process fixes the footprint.

### Why can `@lru_cache` on an instance method cause a leak?
- [ ] It caches the method's bytecode
- [x] `self` is part of the cache key, so the cache keeps every instance alive
- [ ] `lru_cache` disables reference counting
- [ ] It creates a reference cycle the GC cannot see

The cache outlives the instances it holds. Use a per-instance cache, or bound and clear it.

### `sys.getsizeof(rows)` on a list of 10,000 dicts returns about 80 KB. Why so small?
- [ ] The dicts are compressed in memory
- [x] It is shallow: it counts the list's pointer array, not the dicts it holds
- [ ] Small dicts share one hash table
- [ ] getsizeof only counts strings

Use `tracemalloc` or `memray` for the real footprint.

### Memory in a long-running worker creeps up from fragmentation. What is the practical fix?
- [ ] Call `gc.collect()` after every task
- [ ] Turn the GC off
- [x] Recycle worker processes after N tasks, and stream large data instead of loading it all
- [ ] Use `del` on every variable

Recycling gives the memory back for certain. Streaming avoids the spike in the first place.

## Exam questions
- Why might a worker's RSS never shrink after a big job?
- How can an `lru_cache` become a memory leak?
- What does the cyclic garbage collector actually collect?
