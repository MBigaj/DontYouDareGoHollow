# Timeouts Across the Stack

> **Why this matters for you:** Mismatched timeouts across client, proxy, app and database cause hangs and wasted work.

## You should be able to
- Set connect, read and total timeouts deliberately
- Align timeouts across layers and propagate deadlines
- Explain what happens to work after a timeout

## Exam questions
- The load balancer times out at 60 s and the app at 120 s. What happens?
- How do you propagate a deadline through three services?
- Why can a timeout make an outage worse?
