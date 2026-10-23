# asyncio Internals

> **Why this matters for you:** FastAPI hides the event loop; seniors know what happens when a coroutine blocks it, or a task is cancelled.

## You should be able to
- Explain the event loop, tasks, futures and how `await` yields control
- Handle cancellation, timeouts and `TaskGroup` (structured concurrency) correctly
- Find and fix code that blocks the loop

## Lesson
An event loop is a single thread running one callback at a time. A coroutine runs until it awaits something that is not ready yet. At that point it is suspended, and control goes back to the loop, which runs whatever else is ready. Nothing preempts a coroutine: it only gives up the thread at an `await`.

That is the whole danger. A call that blocks without awaiting, such as `time.sleep(1)`, a synchronous HTTP client or a long CPU loop, freezes *every* task on that loop. In FastAPI, an `async def` handler that calls blocking code stalls every request on that worker, so ten concurrent requests take ten seconds. A plain `def` handler is safer for blocking code, because FastAPI runs it in a thread pool.

**Tasks and futures.** A `Future` is a placeholder for a result that does not exist yet. A `Task` is a future that drives a coroutine: `asyncio.create_task(coro())` schedules it on the loop. Keep a reference to every task you create. The loop only holds a weak reference, so an unreferenced task can be garbage-collected mid-flight, and its exception is never seen.

**Cancellation.** `task.cancel()` raises `CancelledError` inside the task at its next `await`. The error unwinds through every `await` up the stack, running `finally` blocks on the way. Since Python 3.8 it is a `BaseException`, so `except Exception` does not catch it. Code that catches `BaseException` (or uses a bare `except:`) and carries on breaks timeouts and shutdowns. If you must catch it, clean up and re-raise. `async with asyncio.timeout(2):` cancels the block when time runs out and turns that into `TimeoutError`.

**gather vs TaskGroup.** With `asyncio.gather`, the first exception propagates, but the other tasks keep running in the background. `asyncio.TaskGroup` (3.11+) is structured concurrency: when one child fails, the group cancels its siblings, waits for them, and raises every failure together as an `ExceptionGroup`. Nothing outlives the `async with` block.

```python
async with asyncio.TaskGroup() as tg:
    user = tg.create_task(fetch_user(uid))
    orders = tg.create_task(fetch_orders(uid))
# both are done here, or the block raised
```

**Getting work off the loop.** For blocking I/O you cannot replace, use `await asyncio.to_thread(fn)`. For CPU-heavy work, threads still contend for the GIL, so use a process pool through `loop.run_in_executor(pool, fn)`, or hand the job to a separate worker through a queue.

## Quiz
### An `async def` FastAPI handler calls `time.sleep(1)`. Ten requests arrive at once on one worker. What happens?
- [ ] They all finish after about one second, because the handler is async
- [x] The loop is blocked, so they are served one after another: about ten seconds
- [ ] FastAPI notices the blocking call and moves it to a thread pool
- [ ] Python raises an error for a blocking call inside a coroutine

Only `def` handlers go to the thread pool. In an `async def` handler, `time.sleep` holds the only thread the loop has.

### What does `await` do when the awaited result is not ready yet?
- [x] Suspends the coroutine and hands control back to the event loop
- [ ] Starts a new thread to wait for the result
- [ ] Blocks the thread until the result arrives
- [ ] Moves the coroutine to a different event loop

Yielding at `await` is what lets one thread serve thousands of waiting requests.

### Inside an `asyncio.TaskGroup`, one child task raises. What happens to the others?
- [ ] They keep running, and the error is raised when they finish
- [ ] The error is logged and swallowed
- [x] The siblings are cancelled, and the failures are raised as an `ExceptionGroup`
- [ ] The whole event loop stops

That is structured concurrency. `gather` without `return_exceptions` would let the siblings keep running unattended.

### A helper wraps an `await` in `except BaseException: log(); return None`. What breaks?
- [ ] Nothing: it is just defensive coding
- [x] It swallows `CancelledError`, so timeouts and shutdowns can no longer cancel that task
- [ ] It also catches `KeyboardInterrupt`, which is never raised in servers
- [ ] mypy rejects catching `BaseException`

Clean up if you must, but re-raise `CancelledError`, or `asyncio.timeout` silently stops working.

### What is the best way to run a CPU-heavy image resize from an async service?
- [ ] Mark the resize function `async def`
- [ ] Insert `await asyncio.sleep(0)` between the steps
- [ ] `asyncio.to_thread`, which gives true parallelism
- [x] A process pool through `run_in_executor`, or a separate worker behind a queue

A thread still competes for the GIL with the loop. A process does not.

### You call `asyncio.create_task(send_email())` and keep no reference to it. What is the risk?
- [x] The task can be garbage-collected before it finishes, and its exception is never seen
- [ ] The task runs twice
- [ ] The task blocks the handler until it completes
- [ ] Nothing: the loop keeps a strong reference to every task

Keep tasks in a set, or use a `TaskGroup`, so they cannot vanish.

## Exam questions
- What exactly happens when a coroutine calls `time.sleep(1)` inside a FastAPI handler?
- How does cancellation propagate through awaits, and what can swallow it?
- gather vs TaskGroup: what changes when one task fails?
- How would you run a CPU-heavy step from an async service?
