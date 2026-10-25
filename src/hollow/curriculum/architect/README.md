# The Architect's road

The senior backend roadmap, played on the Architect road of the map in DontYouDareGoHollow. It starts from where you already are (three years of Python, FastAPI, PostgreSQL, MongoDB, RabbitMQ, Kubernetes, Docker and AWS) and keeps only what is left to earn, weighted towards distributed systems and architecture.

Every step lives here, one Markdown file each. The game reads these files: edit a lesson or add quiz questions, and the game changes with it.

## How a step is cleared
1. **Read** the lesson in the game (the `## Lesson` section).
2. **Quiz**: answer the `## Quiz` questions at 80% or better. That clears the step and lights the bonfire; it then comes back as a refresher after 1, 3, 7, 21 and 60 days, like the Japanese lessons.
3. **Prove** (optional, worth more): pass the Tech Lead's exam at 80% in a Claude session, starting from `## Exam questions`. A region's placement trial can prove what you already know.

When every step of a region is cleared, its boss waits behind the fog. Felling the boss opens the next region, as on the Japanese road. Steps without a lesson yet stay in the fog until one is written.

## Regions (82 steps)
1. [The Forge](01-the-forge/README.md): Python craft beyond everyday FastAPI work (8 steps). Mostly cleared: you ship typed, tested Python daily.
2. [Data Depths](02-data-depths/README.md): PostgreSQL internals, data modelling at scale, caching (11 steps). Half cleared: you model and query PostgreSQL and MongoDB daily.
3. [The API Citadel](03-the-api-citadel/README.md): API design, evolution and security (9 steps). Mostly cleared: you build FastAPI services and led an RPC to API migration.
4. [The Async Ruins](04-the-async-ruins/README.md): Messaging, delivery guarantees and event-driven design (8 steps). Half cleared: RabbitMQ is daily work; the guarantees and patterns are the gap.
5. [The Watchtower](05-the-watchtower/README.md): Observability, SLOs, performance and incidents (9 steps). Partly cleared: you use dashboards and logs; SLOs and tracing are the gap.
6. [The Iron Keep](06-the-iron-keep/README.md): AWS architecture, infrastructure as code and Kubernetes in production (9 steps). Mostly cleared: Docker and Kubernetes are daily; Terraform and AWS depth are the gap.
7. [The Undercroft](07-the-undercroft/README.md): Networking and Linux, deep enough to reason about latency and failure (9 steps). Fresh: enough depth to explain every hop of a request.
8. [The Distributed Abyss](08-the-distributed-abyss/README.md): Distributed systems depth and architecture reasoning: the main gap (19 steps). Fresh: this is the gap between associate and senior.

## Lords of Design (main quest)
System design fights with the Tech Lead: design, then the rules change (10x traffic, multi-region), then failure injection. A win also needs a diagram and an ADR. Each Lord opens once the bosses of the regions it needs have fallen.

| Lord | Tier | Needs | Forces you to handle |
|---|---|---|---|
| URL Shortener | 1 | Data Depths, The API Citadel | Estimation, key generation, read-heavy caching |
| Rate Limiter | 1 | Data Depths | Algorithms, distributed counters, accepting inaccuracy |
| File Upload | 1 | The API Citadel | Object storage, presigned URLs, async processing |
| Notification System | 2 | The Async Ruins | Fan-out, retries, DLQs, delivery guarantees |
| Payment System | 2 | The Async Ruins, Data Depths | Idempotency, transactions, sagas, reconciliation |
| Search System | 2 | Data Depths | Indexing pipelines, Elasticsearch, consistency lag |
| Social Feed | 3 | The Distributed Abyss | Fan-out on write vs read, caching at scale |
| Large E-commerce | 3 | every region | Service boundaries, inventory consistency, peak traffic |
| Uber- or Netflix-like Platform | 3 | every region | Geo data or streaming, multi-region, cost |

A design is written in these steps: Requirements (functional and non-functional); Assumptions; Capacity estimates; API design; Data model and storage; High-level architecture; Scaling strategy; Failure modes; Observability; Security; Cost; Alternatives considered; Trade-offs; Final decision.

## Echoes
Your own past systems, rewritten as retrospective ADRs and challenged by the Tech Lead: context, decision, alternatives, consequences, and what breaks at 10x.

- **AI Chat API Layer**: The API layer you built in front of an AI chat service at YouGov.
- **RPC to API Migration**: Moving YouGov services from RPC calls to a proper API.
- **Lambda to ECS Migration**: Moving workloads from AWS Lambda to ECS.

## Trade-off Duels
Weekly 20-minute ADRs on one dilemma. Pick a concrete context first; the right answer depends on it.

- **PostgreSQL vs MongoDB** (Data Depths)
- **Kafka vs RabbitMQ** (The Async Ruins)
- **Microservices vs Modular Monolith** (The Distributed Abyss)
- **REST vs gRPC** (The API Citadel)
- **Synchronous vs Asynchronous Processing** (The Async Ruins)

## Writing a lesson
A step file has these sections, in order: a `# Title`, a `> **Why this matters for you:**` line, `## You should be able to` (a list), `## Lesson` (Markdown), `## Quiz` and `## Exam questions` (a list). Each quiz question is a `### Question` heading, its options as `- [ ]` lines with the right one marked `- [x]`, then a short explanation. A step needs at least four quiz questions to be playable. `tests/test_architect.py` checks every file.
