# Split Brain and Fencing

> **Why this matters for you:** Two leaders at once corrupts data; fencing tokens are the fix most designs miss.

## You should be able to
- Explain split brain and how it happens
- Use fencing tokens and leases
- Explain why a lock service alone is not enough

## Exam questions
- A worker holding a lock pauses for GC and wakes after the lease expired. What happens?
- How do fencing tokens prevent that?
- How does Kubernetes leader election avoid split brain?
