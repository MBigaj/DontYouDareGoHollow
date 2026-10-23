# Exactly-Once, End to End

> **Why this matters for you:** Exactly-once is achieved by idempotency and deduplication across the whole pipeline, never by the broker alone.

## You should be able to
- Design end-to-end idempotency across API, queue and database
- Explain what Kafka's exactly-once really covers
- Reconcile when things still go wrong

## Exam questions
- Design a pipeline where each survey response is counted exactly once.
- What does 'effectively once' mean?
- How would a nightly reconciliation job help?
