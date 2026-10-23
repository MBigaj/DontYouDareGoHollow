# Profiling and Performance

> **Why this matters for you:** 'It is slow' is a senior's problem to diagnose with evidence, not guesses.

## You should be able to
- Profile CPU with cProfile and py-spy, and memory with tracemalloc
- Read a flame graph and find the real hotspot
- Tell a Python bottleneck from a database or network one

## Lesson
Before profiling anything, split the request: where does the time go? Tracing spans (OpenTelemetry, your APM) show handler time, each database query, each outbound call and any wait for a connection from the pool. Then compare *wall time* with *CPU time*. If p95 latency jumped but CPU did not, the process is waiting: on the database, the network, a lock or an exhausted pool. A Python profiler will not find that. If CPU rose with latency, it is Python work, and it is time to profile.

**Two kinds of profiler.**
- `cProfile` is deterministic: it hooks every function call. The counts are exact, but the per-call overhead inflates code made of many tiny calls. Use it in tests and locally (`python -m cProfile -o out.prof`, then `snakeviz`).
- `py-spy` is a sampling profiler. It reads the stack of a running process from outside, with no code change and no restart:
  - `py-spy top --pid 1234` gives a live view.
  - `py-spy record -o flame.svg --pid 1234` records a flame graph.
  - `py-spy dump --pid 1234` shows where a stuck process is.

  This is how you profile production.

**Reading a flame graph.** Each box is a function. Its width is the share of samples in which it was on the stack, children included. The x-axis is *not* time order, and the colours mean nothing. Look for the widest boxes near the top of the stacks: that is where the CPU actually burns (self time). Tall stacks are just deep call chains, and are not slow in themselves.

**The usual suspects.**
- *N+1 queries:* the query count grows with the size of the result. An ORM lazily loads a relation per row. Fix it with a join, `selectinload` or a batched query.
- *Serialisation:* large Pydantic models being validated twice, or JSON encoded twice.
- *Pool waits:* the time is spent before the query even starts.
- *Plan changes:* data grew, and a query switched to a sequential scan. That is a database job for `EXPLAIN ANALYZE`.

**Memory.** `tracemalloc` records where allocations come from. Take a snapshot, run the workload for a while, take another, and compare them with `snapshot.compare_to(old, "lineno")`. The lines whose memory keeps growing are your leak. `memray` gives richer reports, including native allocations.

When you report a fix, report numbers: p50 and p95 before and after, and under what load.

## Quiz
### How do you profile a production Python service without restarting or changing it?
- [ ] Wrap the app in `cProfile` and redeploy
- [ ] Add timing prints and redeploy
- [x] Attach `py-spy` to the running process ID
- [ ] Use `line_profiler` decorators

py-spy samples the stack from outside the process. Every other option needs a deploy.

### In a flame graph, what does a box's width tell you?
- [x] The share of samples in which that function was on the stack, children included
- [ ] When the function ran: left is earlier
- [ ] How deeply nested the call was
- [ ] How hot the function is, shown by its colour

The x-axis is sorted alphabetically, not by time, and the colours are random.

### p95 went from 80 ms to 400 ms, but CPU usage stayed flat. Where do you look first?
- [ ] At the hottest Python functions in cProfile
- [x] At waiting: database queries, outbound calls, locks and connection-pool waits in the trace
- [ ] At the GIL
- [ ] At garbage collection pauses

Flat CPU with higher latency means the process is waiting, not computing.

### Which symptom points to an N+1 query problem?
- [ ] One slow query that always takes about the same time
- [x] The number of queries per request grows with the number of rows returned
- [ ] High CPU in JSON encoding
- [ ] Timeouts only at night

One query for the list, plus one per row. A join or a batched load fixes it.

### How do you find a memory leak in a long-running worker?
- [ ] Watch RSS in the dashboard until it stops growing
- [x] Take `tracemalloc` snapshots over time and compare which lines keep growing
- [ ] Call `gc.collect()` in a loop
- [ ] Use `sys.getsizeof` on the main objects

Comparing snapshots points straight at the allocation sites that keep growing.

### Why can cProfile mislead you about where time goes?
- [ ] It only samples every 10 ms
- [ ] It ignores C extensions entirely
- [x] Its per-call overhead inflates code made of many small function calls
- [ ] It measures wall time only

A deterministic profiler pays a cost on every call, so chatty code looks worse than it is.

## Exam questions
- An endpoint went from 80 ms to 400 ms p95. Walk through how you find out why.
- How do you profile a production service without restarting it?
- How would you find a memory leak in a long-running worker?
