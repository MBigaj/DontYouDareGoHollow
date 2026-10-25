# Idempotent Consumers

> **Why this matters for you:** At-least-once delivery means duplicates; consumers must make them harmless.

## You should be able to
- Deduplicate with message ids and processed-message tables
- Design naturally idempotent operations
- Handle out-of-order messages

## Exam questions
- How do you store processed message ids without the table growing forever?
- Give an operation that is naturally idempotent and one that is not.
- Messages arrive out of order. When does it matter and what do you do?
