# Rate Limiting and Quotas

> **Why this matters for you:** Protecting shared services from noisy clients needs the right algorithm in the right place.

## You should be able to
- Compare token bucket, leaky bucket, fixed and sliding windows
- Implement distributed rate limiting and accept its inaccuracy
- Decide where to limit: gateway, service or both

## Exam questions
- Token bucket vs sliding window log: what does each get right?
- How do you rate limit across 20 API instances?
- What should a client see when it is limited?
