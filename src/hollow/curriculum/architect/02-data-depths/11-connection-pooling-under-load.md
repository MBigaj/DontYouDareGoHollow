# Connection Pooling Under Load

> **Why this matters for you:** Many outages are pool exhaustion, not the database itself.

## You should be able to
- Size pools across app workers and database limits
- Explain PgBouncer modes and what transaction pooling breaks
- Diagnose pool exhaustion from metrics

## Exam questions
- 40 ECS tasks with 4 workers and a pool of 10 each: what happens to max_connections?
- What breaks under PgBouncer transaction pooling?
- Requests hang for 30 s then fail. How do you tell pool exhaustion from a slow query?
