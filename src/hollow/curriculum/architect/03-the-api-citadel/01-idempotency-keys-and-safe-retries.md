# Idempotency Keys and Safe Retries

> **Why this matters for you:** Clients and proxies retry; without idempotency a timeout becomes a double charge.

## You should be able to
- Design idempotency keys: storage, scope, expiry and responses
- Handle concurrent requests with the same key
- Explain which HTTP methods are idempotent and why it matters

## Exam questions
- A payment request times out and the client retries. Walk through what your API does.
- Two requests with the same idempotency key arrive at once. What happens?
- How long do you keep idempotency keys, and why?
