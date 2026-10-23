# Retries, Backoff and Dead Letters

> **Why this matters for you:** Retries turn blips into success and real bugs into storms; DLQs are where failures wait for humans.

## You should be able to
- Design retry policies with backoff and jitter
- Use dead-letter queues and a redrive process
- Tell transient from permanent failures

## Exam questions
- Why jitter?
- A poison message is retried forever and blocks the queue. Design the fix.
- Who looks at the DLQ, and what happens to those messages?
