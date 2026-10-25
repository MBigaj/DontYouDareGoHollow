# Pagination at Scale

> **Why this matters for you:** OFFSET pagination quietly gets slow and inconsistent as tables grow.

## You should be able to
- Implement cursor (keyset) pagination
- Explain the consistency problems of offset pagination
- Design stable cursors over sorted, filtered data

## Exam questions
- Why does OFFSET 1,000,000 get slow, and what replaces it?
- How do you paginate by created_at when timestamps collide?
- What breaks in pagination when rows are inserted mid-scroll?
