# Caching Patterns and Invalidation

> **Why this matters for you:** Caching is easy to add and hard to keep correct; stampedes and stale data are senior-level failure stories.

## You should be able to
- Compare cache-aside, read-through, write-through and write-behind
- Invalidate correctly, and choose TTLs deliberately
- Prevent cache stampedes and handle a cold cache

## Exam questions
- A hot key expires and 5,000 requests hit the database at once. What now?
- How do you keep a cache consistent with PostgreSQL on writes?
- When is a cache the wrong answer to a slow endpoint?
