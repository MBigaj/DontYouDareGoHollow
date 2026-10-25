# The Outbox Pattern

> **Why this matters for you:** Writing to the database and publishing a message are two systems; the outbox makes them agree.

## You should be able to
- Explain the dual-write problem
- Implement a transactional outbox with a relay or CDC
- Handle ordering and duplicates from the outbox

## Exam questions
- Why is 'commit, then publish' unsafe?
- Polling relay vs change data capture: trade-offs?
- How does the outbox interact with your consumer's idempotency?
