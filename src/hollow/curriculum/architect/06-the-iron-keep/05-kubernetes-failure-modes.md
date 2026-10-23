# Kubernetes Failure Modes

> **Why this matters for you:** Kubernetes is daily work; seniors know how it fails: probes, OOM kills, evictions, crash loops.

## You should be able to
- Configure liveness, readiness and startup probes correctly
- Explain requests, limits, QoS and OOM kills
- Use PodDisruptionBudgets and graceful shutdown

## Exam questions
- A bad liveness probe takes the whole service down. How?
- Pods are OOMKilled with no error in logs. Diagnose it.
- What happens to in-flight requests during a rolling update?
