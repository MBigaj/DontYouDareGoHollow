# MVCC and Isolation Levels

> **Why this matters for you:** Most subtle data bugs you will meet are isolation bugs; MVCC explains why PostgreSQL behaves as it does.

## You should be able to
- Explain MVCC: tuple versions, snapshots, visibility and vacuum
- Name the anomalies each isolation level allows, with examples
- Pick an isolation level (or explicit locking) for a given race

## Exam questions
- Two requests read a balance and both subtract 100. Which isolation level stops it, and how?
- What is write skew, and why does REPEATABLE READ not prevent it?
- Why do long-running transactions cause table bloat?
- SERIALIZABLE vs SELECT ... FOR UPDATE: when would you pick each?
