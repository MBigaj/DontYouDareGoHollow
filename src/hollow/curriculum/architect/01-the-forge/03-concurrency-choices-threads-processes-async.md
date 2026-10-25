# Concurrency Choices: Threads, Processes, async

> **Why this matters for you:** Choosing the wrong model is a classic production mistake; the GIL (and free-threaded 3.13) decides a lot of it.

## You should be able to
- Pick threads, processes or async for I/O-bound vs CPU-bound work, and justify it
- Explain the GIL, what releases it, and what free-threading changes
- Size worker pools for a service under load

## Lesson
CPython's Global Interpreter Lock lets only one thread execute Python bytecode at a time. A thread releases it while it waits on blocking I/O (sockets, files, `time.sleep`), and many C extensions release it during heavy work (NumPy, hashing, compression). A pure Python loop never does.

That gives the three choices:

| Model | Good for | Costs |
|---|---|---|
| Threads | I/O-bound work with blocking libraries | GIL contention on CPU work, shared-state bugs |
| Processes | CPU-bound Python | Memory per process, pickling, start-up time |
| async | Thousands of concurrent I/O waits | Every library must be async; one blocking call stalls all |

Threads speed up an I/O-bound service because the threads mostly sit waiting with the GIL released. They do nothing for a CPU-bound one: four threads still take turns on one interpreter. Processes give real parallelism, because each has its own interpreter and GIL. async gives the cheapest concurrency for waiting: 5,000 open websockets are 5,000 suspended coroutines, not 5,000 threads.

**Free-threaded Python.** Python 3.13 ships an optional build without the GIL (PEP 703, `python3.13t`). Threads can then run Python bytecode in parallel. The catch is that code which silently relied on the GIL to serialise access to shared state now needs real locks. (`counter += 1` was never atomic anyway.) C extensions also have to declare support, or the interpreter turns the GIL back on. Single-threaded code is a little slower. It is a real option for CPU-heavy thread pools, not a reason to drop async for I/O.

**Sizing workers.** Each Uvicorn worker is a process with its own event loop.
- For an async service, start with one worker per vCPU, so four workers on a 4-vCPU ECS task. Then let a load test and memory per worker move that number.
- The `2 × cores + 1` rule is for *synchronous* Gunicorn workers, which spend their time blocked.
- The hidden limit is downstream: every worker opens its own database pool, so `tasks × workers × pool_size` must stay under PostgreSQL's `max_connections`. That is the moment to reach for PgBouncer.

## Quiz
### Why can threads speed up an I/O-bound Python service but not a CPU-bound one?
- [ ] Threads are always faster than processes
- [x] The GIL is released while a thread waits on I/O, but only one thread runs bytecode at a time
- [ ] CPU-bound code cannot be started in a thread
- [ ] The operating system gives I/O threads more cores

Waiting does not need the GIL. Computing does.

### Which of these releases the GIL while it runs?
- [ ] A pure Python `for` loop summing numbers
- [ ] A dict comprehension
- [x] A blocking `socket.recv()` call
- [ ] Sorting a list of Python objects

Blocking system calls drop the GIL while they wait. Bytecode never does.

### Async FastAPI on a 4-vCPU ECS task: how many Uvicorn workers do you start with?
- [x] About four, one per vCPU, then adjust from a load test and memory per worker
- [ ] One: async needs only a single process
- [ ] Nine, from the `2 × cores + 1` rule
- [ ] Sixty-four, so no request ever waits

`2 × cores + 1` is for synchronous workers that spend their time blocked. One async worker per core keeps every core busy.

### You scale out to more workers and tasks. Which limit is easiest to forget?
- [ ] The number of open files on the container
- [x] Every worker's database pool: `tasks × workers × pool_size` can exceed `max_connections`
- [ ] Uvicorn's maximum number of workers
- [ ] The GIL across processes

Connection exhaustion shows up as timeouts far from where you made the change.

### What changes for your code under free-threaded Python?
- [ ] async is no longer needed
- [ ] `counter += 1` becomes atomic
- [x] Threads run bytecode in parallel, so shared state needs real locks, and C extensions must support it
- [ ] `multiprocessing` is removed

Some code relied on the GIL to serialise access without meaning to. Without the GIL, those races appear.

### A service holds 5,000 mostly idle websocket connections. Which model fits?
- [ ] One thread per connection
- [ ] One process per connection
- [x] async: each connection is a cheap suspended coroutine
- [ ] A process pool sized to the connection count

Idle connections are pure waiting, and waiting is what async makes cheap.

## Exam questions
- Why can threads speed up an I/O-bound Python service but not a CPU-bound one?
- How many Uvicorn workers would you run on a 4-vCPU ECS task, and why?
- What changes for your code if the GIL goes away?
