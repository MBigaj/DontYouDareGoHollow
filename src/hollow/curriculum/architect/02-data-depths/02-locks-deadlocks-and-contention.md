# Locks, Deadlocks and Contention

> **Why this matters for you:** Under load, lock waits become latency and outages; seniors read pg_locks, not guesses.

## You should be able to
- Explain row and table locks, and which statements take which
- Diagnose and prevent deadlocks
- Spot migrations that take dangerous locks

## Exam questions
- Why can ALTER TABLE take your service down for minutes?
- Two transactions deadlock updating the same two rows. How do you prevent it?
- What does SKIP LOCKED let you build?
