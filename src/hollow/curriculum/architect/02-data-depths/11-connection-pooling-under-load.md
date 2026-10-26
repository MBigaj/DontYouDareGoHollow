# Connection Pooling Under Load

> **Why this matters for you:** Many outages are pool exhaustion, not the database itself.

## You should be able to
- Size pools across app workers and database limits
- Explain PgBouncer modes and what transaction pooling breaks
- Diagnose pool exhaustion from metrics

## Lesson
Each PostgreSQL connection is a separate server process with its own memory. `max_connections` is a hard ceiling, and on RDS its default is derived from instance memory. Past a few times the number of CPU cores of *active* queries, more connections add contention, not throughput. So the pool is a throttle you configure, not an implementation detail.

**Do the multiplication.** SQLAlchemy's default `QueuePool` is `pool_size=5` plus `max_overflow=10`: up to 15 connections per process. Now count the processes. 40 ECS tasks, each running 4 uvicorn workers with `pool_size=10`, can open 40 × 4 × 10 = **1,600** connections. During a rolling deploy, old and new tasks overlap, so the figure briefly doubles. An autoscaling event adds more, and the Celery workers and the migration job count too. Past the limit, new connections fail with `FATAL: sorry, too many clients already`, and every service sharing the database suffers, not just the one that grew.

**Size by Little's law, not by guesswork.** Connections in use = request rate × time each request holds a connection. 500 requests per second holding a connection for 20 ms keep about 10 connections busy. Hold it for 200 ms instead, because the handler calls a payment API while its session is open, and you need 100. The cheapest pool fix is usually in the code: take the connection late, give it back early, and never hold a transaction across an HTTP call or a queue publish.

```python
async def checkout(cart_id: int, payments: PaymentsClient, db: async_sessionmaker) -> None:
    async with db() as session:  # read what you need, then release the connection
        cart = await load_cart(session, cart_id)
    charge = await payments.charge(cart.total)  # 2 s, holding no connection
    async with db.begin() as session:  # short write transaction
        await record_payment(session, cart_id, charge.id)
```

**PgBouncer** sits between the services and PostgreSQL, accepting thousands of client connections and multiplexing them onto a few dozen server connections. Its mode decides how:

- **session**: a server connection for the client's whole session. Safe, and saves almost nothing.
- **transaction**: a server connection only for the duration of each transaction. This is the useful mode, and the one that breaks things.
- **statement**: per statement. Multi-statement transactions are impossible.

In transaction mode, consecutive transactions from one client can land on different server connections. Anything that relies on *session* state breaks: `SET` of session settings (use `SET LOCAL` inside the transaction), session-level advisory locks, `LISTEN`/`NOTIFY`, temporary tables used across transactions, and server-side prepared statements. The last one hits FastAPI services directly. asyncpg prepares statements and caches them per connection, so through transaction pooling you get `prepared statement "__asyncpg_stmt_1__" does not exist`. Either turn the cache off (`statement_cache_size=0` for asyncpg, `prepared_statement_cache_size=0` in SQLAlchemy's asyncpg URL), or use PgBouncer 1.21 or later with `max_prepared_statements` set. RDS Proxy plays the same role on AWS, and *pins* a client to one connection when it detects session state, which silently removes the benefit.

**Pool exhaustion vs a slow query.** The symptom is the same: requests hang, then fail. Tell them apart with evidence:

| Signal | Pool exhaustion | Slow query |
|---|---|---|
| App error | `QueuePool limit ... connection timed out, timeout 30.00` | statement timeout, or just a long response |
| Hang length | exactly `pool_timeout`, often 30 s | varies with the query |
| Database CPU and I/O | low | high |
| `pg_stat_activity` | connections `idle` or `idle in transaction` | `active`, with an old `query_start` |

Exhaustion means connections are held but not used: leaked sessions, transactions open across slow non-database work, or more concurrency than the pool. Export the pool's checked-out count as a metric; when it sits at `pool_size + max_overflow` while the database idles, you have your answer.

**Settings worth knowing:**

- `pool_pre_ping=True` checks a connection on checkout, so connections killed by a failover or a proxy are not handed out.
- `pool_recycle` closes connections older than N seconds.
- `pool_timeout` fails fast instead of queueing forever.
- On the server, `statement_timeout` and `idle_in_transaction_session_timeout` stop one bad request from holding a connection indefinitely.

## Quiz
### 40 ECS tasks each run 4 workers with a SQLAlchemy pool of 10 and no overflow. How many connections can they open?
- [x] Up to 1,600, and roughly double that briefly during a rolling deploy
- [ ] 10: the pool is shared across all tasks
- [ ] 40: one per task
- [ ] 160: one per worker

Pools are per process. Multiply tasks × workers × pool size, then remember deploys overlap old and new tasks.

### Which of these breaks under PgBouncer in transaction mode?
- [ ] Multi-statement transactions with `BEGIN` and `COMMIT`
- [ ] `SET LOCAL statement_timeout` inside a transaction
- [ ] Plain `SELECT` queries outside transactions
- [x] Session state: `SET` of session settings, session advisory locks, `LISTEN`/`NOTIFY`, temporary tables across transactions

Each transaction may run on a different server connection, so anything stored on the session is lost between them.

### A FastAPI service using asyncpg through PgBouncer in transaction mode logs `prepared statement "__asyncpg_stmt_1__" does not exist`. Why?
- [ ] PgBouncer does not support asyncpg at all
- [x] asyncpg caches prepared statements per connection, but PgBouncer hands each transaction a different server connection
- [ ] The statement was too long for PgBouncer's buffer
- [ ] PostgreSQL drops prepared statements after every query

Disable the statement cache (`statement_cache_size=0`), or use PgBouncer 1.21+ with `max_prepared_statements`, which tracks them for you.

### Requests hang exactly 30 seconds then fail. Database CPU is at 10%, and `pg_stat_activity` shows mostly `idle in transaction`. What is happening?
- [ ] A slow query is saturating the database
- [ ] The database has hit `max_connections`
- [x] Pool exhaustion: connections are held open across non-database work, and checkout waits out `pool_timeout`
- [ ] A deadlock between two requests

A 30-second ceiling matches `pool_timeout`, and idle-in-transaction sessions are connections held but not working. Find the code that holds them.

### A service handles 500 requests per second, and each request holds a database connection for 20 ms. How many connections are busy on average?
- [ ] 500
- [ ] 100
- [ ] 25
- [x] 10

Little's law: 500 per second × 0.02 seconds = 10. Hold each connection ten times longer, and you need ten times the pool.

### A checkout handler opens its session, calls a payment API that takes 2 seconds, then writes the result. What should change?
- [x] Make the payment call with no connection held, then open a short transaction to write the result
- [ ] Raise `pool_size` until requests stop waiting
- [ ] Increase `pool_timeout` to 60 seconds
- [ ] Switch PgBouncer to session mode

Holding a connection across slow non-database work multiplies the pool you need. Give the connection back before the external call.

## Exam questions
- 40 ECS tasks with 4 workers and a pool of 10 each: what happens to max_connections?
- What breaks under PgBouncer transaction pooling?
- Requests hang for 30 s then fail. How do you tell pool exhaustion from a slow query?
