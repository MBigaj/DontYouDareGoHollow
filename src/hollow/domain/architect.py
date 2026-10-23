"""The Architect track: eight skill regions built from the Obsidian roadmap vault, and the
nine Lords of Design that need them.

The curriculum is personal: it starts from three years of backend work (Python, FastAPI,
PostgreSQL, MongoDB, RabbitMQ, Kubernetes, Docker, AWS) and keeps only what is left to earn,
weighted towards distributed systems and architecture. Each topic is one note in the
restructured vault (regions in numbered folders; the old notes live in Archive/).

Gates (from the plan): Learn is your own writing in the note (checked by scanning the vault,
pays a little, unlocks nothing); Prove is a Tech Lead exam at 80% or better, or a placement
trial, and clears the topic; Build (CI-checked challenges) comes later.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from hollow.domain.calendar import GameCalendar
from hollow.domain.events import AgentResult, Event, NoteWritten

LEARN_WORDS = 150
"""Your own words in a note (template text not counted) for the Learn gate."""
PROVE_MARK = 0.8
LEARN_SOULS = 30
PROVE_SOULS = 120
REGION_CLEAR = 0.8
"""Share of a region's topics proved for the region to count as cleared."""


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    region: str
    note: str
    """Vault path, relative to the vault root."""


@dataclass(frozen=True)
class SkillRegion:
    id: str
    name: str
    covers: str
    build_boss: str
    start: str
    """Where you start in this region."""
    topics: tuple[Topic, ...]


@dataclass(frozen=True)
class Lord:
    id: str
    name: str
    tier: int
    regions: tuple[str, ...]
    forces: str
    note: str


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _region(
    region_id: str, name: str, covers: str, build: str, start: str, notes: tuple[str, ...]
) -> SkillRegion:
    topics = tuple(
        Topic(slug(note.rsplit("/", 1)[-1].removesuffix(".md")), title, region_id, note)
        for title, note in zip(TITLES[region_id], notes, strict=True)
    )
    return SkillRegion(region_id, name, covers, build, start, topics)


TITLES: dict[str, tuple[str, ...]] = {
    "forge": (
        "mypy --strict in Practice",
        "asyncio Internals",
        "Concurrency Choices: Threads, Processes, async",
        "Profiling and Performance",
        "Property-Based Testing",
        "Test Architecture",
        "Packaging and Tooling with uv",
        "Python Memory Model",
    ),
    "data-depths": (
        "MVCC and Isolation Levels",
        "Locks, Deadlocks and Contention",
        "Reading Query Plans",
        "Index Design",
        "Zero-Downtime Migrations",
        "Replication and Read Replicas",
        "Partitioning and Sharding",
        "Caching Patterns and Invalidation",
        "Redis Beyond Caching",
        "PostgreSQL vs MongoDB Modelling",
        "Connection Pooling Under Load",
    ),
    "api-citadel": (
        "Idempotency Keys and Safe Retries",
        "API Versioning and Evolution",
        "Pagination at Scale",
        "OAuth2 and OpenID Connect",
        "Authorisation Models",
        "OWASP API Security",
        "Rate Limiting and Quotas",
        "REST, gRPC and Async APIs",
        "Secrets and Key Management",
    ),
    "async-ruins": (
        "Delivery Guarantees",
        "The Outbox Pattern",
        "Idempotent Consumers",
        "Retries, Backoff and Dead Letters",
        "Backpressure and Flow Control",
        "Kafka vs RabbitMQ",
        "Event-Driven Design",
        "Sagas and Long-Running Processes",
    ),
    "watchtower": (
        "SLIs, SLOs and Error Budgets",
        "Distributed Tracing with OpenTelemetry",
        "Metrics That Matter",
        "Structured Logging and Correlation",
        "Alerting on Symptoms",
        "Latency, Percentiles and Queueing",
        "Load Testing and Capacity Planning",
        "Incidents and Postmortems",
        "Graceful Degradation and Failover",
    ),
    "iron-keep": (
        "Terraform Fundamentals",
        "Compute on AWS: Lambda, ECS and EKS",
        "AWS Networking",
        "IAM Done Right",
        "Kubernetes Failure Modes",
        "Autoscaling",
        "Deployment Strategies",
        "Cloud Cost Thinking",
        "Managed Data Services",
    ),
    "undercroft": (
        "TCP in Practice",
        "TLS",
        "DNS",
        "HTTP/1.1, HTTP/2 and HTTP/3",
        "Load Balancers and Proxies",
        "Timeouts Across the Stack",
        "Processes, Threads and File Descriptors",
        "Memory and the OOM Killer",
        "A Request, Hop by Hop",
    ),
    "distributed-abyss": (
        "Why Distributed Systems Are Hard",
        "Time, Clocks and Ordering",
        "Consistency Models",
        "CAP and PACELC",
        "Replication Strategies",
        "Consensus and Leader Election",
        "Partitioning, Rebalancing and Hot Keys",
        "Distributed Transactions",
        "Failure Amplification",
        "Resilience Patterns",
        "Split Brain and Fencing",
        "Exactly-Once, End to End",
        "Monolith, Modular Monolith or Microservices",
        "Service Boundaries and DDD",
        "Hexagonal and Clean Architecture",
        "CQRS and Event Sourcing",
        "Migrations and the Strangler Fig",
        "Capacity Estimation",
        "Writing Decisions: ADRs and Trade-offs",
    ),
}  # fmt: skip

REGIONS: tuple[SkillRegion, ...] = (
    _region(
        "forge",
        "The Forge",
        "Python craft beyond everyday FastAPI work",
        "A fully tested and typed souls ledger: mypy --strict, 90% coverage, Hypothesis",
        "Mostly cleared: you ship typed, tested Python daily.",
        (
            "01 - The Forge/mypy --strict in Practice.md",
            "01 - The Forge/asyncio Internals.md",
            "01 - The Forge/Concurrency Choices - Threads, Processes, async.md",
            "01 - The Forge/Profiling and Performance.md",
            "01 - The Forge/Property-Based Testing.md",
            "01 - The Forge/Test Architecture.md",
            "01 - The Forge/Packaging and Tooling with uv.md",
            "01 - The Forge/Python Memory Model.md",
        ),
    ),
    _region(
        "data-depths",
        "Data Depths",
        "PostgreSQL internals, data modelling at scale, caching",
        "A schema with a zero-downtime Alembic migration, and a slow query fixed with EXPLAIN",
        "Half cleared: you model and query PostgreSQL and MongoDB daily.",
        (
            "02 - Data Depths/MVCC and Isolation Levels.md",
            "02 - Data Depths/Locks, Deadlocks and Contention.md",
            "02 - Data Depths/Reading Query Plans.md",
            "02 - Data Depths/Index Design.md",
            "02 - Data Depths/Zero-Downtime Migrations.md",
            "02 - Data Depths/Replication and Read Replicas.md",
            "02 - Data Depths/Partitioning and Sharding.md",
            "02 - Data Depths/Caching Patterns and Invalidation.md",
            "02 - Data Depths/Redis Beyond Caching.md",
            "02 - Data Depths/PostgreSQL vs MongoDB Modelling.md",
            "02 - Data Depths/Connection Pooling Under Load.md",
        ),
    ),
    _region(
        "api-citadel",
        "The API Citadel",
        "API design, evolution and security",
        "DontYouDareGoHollow's API with OAuth2, idempotency keys and a rate limiter",
        "Mostly cleared: you build FastAPI services and led an RPC to API migration.",
        (
            "03 - The API Citadel/Idempotency Keys and Safe Retries.md",
            "03 - The API Citadel/API Versioning and Evolution.md",
            "03 - The API Citadel/Pagination at Scale.md",
            "03 - The API Citadel/OAuth2 and OpenID Connect.md",
            "03 - The API Citadel/Authorisation Models.md",
            "03 - The API Citadel/OWASP API Security.md",
            "03 - The API Citadel/Rate Limiting and Quotas.md",
            "03 - The API Citadel/REST, gRPC and Async APIs.md",
            "03 - The API Citadel/Secrets and Key Management.md",
        ),
    ),
    _region(
        "async-ruins",
        "The Async Ruins",
        "Messaging, delivery guarantees and event-driven design",
        "Anki and GitHub sync moved onto a queue with an outbox, surviving crashes",
        "Half cleared: RabbitMQ is daily work; the guarantees and patterns are the gap.",
        (
            "04 - The Async Ruins/Delivery Guarantees.md",
            "04 - The Async Ruins/The Outbox Pattern.md",
            "04 - The Async Ruins/Idempotent Consumers.md",
            "04 - The Async Ruins/Retries, Backoff and Dead Letters.md",
            "04 - The Async Ruins/Backpressure and Flow Control.md",
            "04 - The Async Ruins/Kafka vs RabbitMQ.md",
            "04 - The Async Ruins/Event-Driven Design.md",
            "04 - The Async Ruins/Sagas and Long-Running Processes.md",
        ),
    ),
    _region(
        "watchtower",
        "The Watchtower",
        "Observability, SLOs, performance and incidents",
        "Dashboards, burn-rate alerts and a postmortem of a deliberate outage",
        "Partly cleared: you use dashboards and logs; SLOs and tracing are the gap.",
        (
            "05 - The Watchtower/SLIs, SLOs and Error Budgets.md",
            "05 - The Watchtower/Distributed Tracing with OpenTelemetry.md",
            "05 - The Watchtower/Metrics That Matter.md",
            "05 - The Watchtower/Structured Logging and Correlation.md",
            "05 - The Watchtower/Alerting on Symptoms.md",
            "05 - The Watchtower/Latency, Percentiles and Queueing.md",
            "05 - The Watchtower/Load Testing and Capacity Planning.md",
            "05 - The Watchtower/Incidents and Postmortems.md",
            "05 - The Watchtower/Graceful Degradation and Failover.md",
        ),
    ),
    _region(
        "iron-keep",
        "The Iron Keep",
        "AWS architecture, infrastructure as code and Kubernetes in production",
        "DontYouDareGoHollow deployed with Terraform",
        "Mostly cleared: Docker and Kubernetes are daily; Terraform and AWS depth are the gap.",
        (
            "06 - The Iron Keep/Terraform Fundamentals.md",
            "06 - The Iron Keep/Compute on AWS - Lambda, ECS and EKS.md",
            "06 - The Iron Keep/AWS Networking.md",
            "06 - The Iron Keep/IAM Done Right.md",
            "06 - The Iron Keep/Kubernetes Failure Modes.md",
            "06 - The Iron Keep/Autoscaling.md",
            "06 - The Iron Keep/Deployment Strategies.md",
            "06 - The Iron Keep/Cloud Cost Thinking.md",
            "06 - The Iron Keep/Managed Data Services.md",
        ),
    ),
    _region(
        "undercroft",
        "The Undercroft",
        "Networking and Linux, deep enough to reason about latency and failure",
        "One request traced from DNS to a Python handler, every hop explained",
        "Fresh: enough depth to explain every hop of a request.",
        (
            "07 - The Undercroft/TCP in Practice.md",
            "07 - The Undercroft/TLS.md",
            "07 - The Undercroft/DNS.md",
            "07 - The Undercroft/HTTP1.1, HTTP2 and HTTP3.md",
            "07 - The Undercroft/Load Balancers and Proxies.md",
            "07 - The Undercroft/Timeouts Across the Stack.md",
            "07 - The Undercroft/Processes, Threads and File Descriptors.md",
            "07 - The Undercroft/Memory and the OOM Killer.md",
            "07 - The Undercroft/A Request, Hop by Hop.md",
        ),
    ),
    _region(
        "distributed-abyss",
        "The Distributed Abyss",
        "Distributed systems depth and architecture reasoning: the main gap",
        "The consistency choices of a tier 3 design, explained and defended in writing",
        "Fresh: this is the gap between associate and senior.",
        (
            "08 - The Distributed Abyss/Why Distributed Systems Are Hard.md",
            "08 - The Distributed Abyss/Time, Clocks and Ordering.md",
            "08 - The Distributed Abyss/Consistency Models.md",
            "08 - The Distributed Abyss/CAP and PACELC.md",
            "08 - The Distributed Abyss/Replication Strategies.md",
            "08 - The Distributed Abyss/Consensus and Leader Election.md",
            "08 - The Distributed Abyss/Partitioning, Rebalancing and Hot Keys.md",
            "08 - The Distributed Abyss/Distributed Transactions.md",
            "08 - The Distributed Abyss/Failure Amplification.md",
            "08 - The Distributed Abyss/Resilience Patterns.md",
            "08 - The Distributed Abyss/Split Brain and Fencing.md",
            "08 - The Distributed Abyss/Exactly-Once, End to End.md",
            "08 - The Distributed Abyss/Monolith, Modular Monolith or Microservices.md",
            "08 - The Distributed Abyss/Service Boundaries and DDD.md",
            "08 - The Distributed Abyss/Hexagonal and Clean Architecture.md",
            "08 - The Distributed Abyss/CQRS and Event Sourcing.md",
            "08 - The Distributed Abyss/Migrations and the Strangler Fig.md",
            "08 - The Distributed Abyss/Capacity Estimation.md",
            "08 - The Distributed Abyss/Writing Decisions - ADRs and Trade-offs.md",
        ),
    ),
)  # fmt: skip

ALL_REGIONS = tuple(r.id for r in REGIONS)
LORDS: tuple[Lord, ...] = (
    Lord("url-shortener", "URL Shortener", 1, ("data-depths", "api-citadel"),
         "Estimation, key generation, read-heavy caching",
         "09 - Lords of Design/URL Shortener.md"),
    Lord("rate-limiter", "Rate Limiter", 1, ("data-depths",),
         "Algorithms, distributed counters, accepting inaccuracy",
         "09 - Lords of Design/Rate Limiter.md"),
    Lord("file-upload", "File Upload", 1, ("api-citadel",),
         "Object storage, presigned URLs, async processing",
         "09 - Lords of Design/File Upload.md"),
    Lord("notification-system", "Notification System", 2, ("async-ruins",),
         "Fan-out, retries, DLQs, delivery guarantees",
         "09 - Lords of Design/Notification System.md"),
    Lord("payment-system", "Payment System", 2, ("async-ruins", "data-depths"),
         "Idempotency, transactions, sagas, reconciliation",
         "09 - Lords of Design/Payment System.md"),
    Lord("search-system", "Search System", 2, ("data-depths",),
         "Indexing pipelines, Elasticsearch, consistency lag",
         "09 - Lords of Design/Search System.md"),
    Lord("social-feed", "Social Feed", 3, ("distributed-abyss",),
         "Fan-out on write vs read, caching at scale",
         "09 - Lords of Design/Social Feed.md"),
    Lord("large-e-commerce", "Large E-commerce", 3, ALL_REGIONS,
         "Service boundaries, inventory consistency, peak traffic",
         "09 - Lords of Design/Large E-commerce.md"),
    Lord("uber-or-netflix-like-platform", "Uber- or Netflix-like Platform", 3, ALL_REGIONS,
         "Geo data or streaming, multi-region, cost",
         "09 - Lords of Design/Uber- or Netflix-like Platform.md"),
)  # fmt: skip

TOPICS: dict[str, Topic] = {t.id: t for r in REGIONS for t in r.topics}
REGION_BY_ID = {r.id: r for r in REGIONS}


def region_topics(region_id: str) -> list[Topic]:
    return [t for t in TOPICS.values() if t.region == region_id]


# --- progress -----------------------------------------------------------------


@dataclass
class TopicState:
    topic: Topic
    words: int = 0
    learned: bool = False
    proved: bool = False
    placed: bool = False
    """Cleared by a placement trial rather than an exam."""
    best: float | None = None
    """Best exam score, 0 to 1."""
    exams: int = 0


@dataclass(frozen=True)
class ArchitectReward:
    day: date
    souls: int
    lights: bool


@dataclass
class ArchitectState:
    topics: dict[str, TopicState]
    placed_regions: set[str]
    rewards: list[ArchitectReward]

    def region(self, region_id: str) -> list[TopicState]:
        return [s for s in self.topics.values() if s.topic.region == region_id]

    def cleared_share(self, region_id: str) -> float:
        states = self.region(region_id)
        return sum(s.proved for s in states) / len(states)

    def region_cleared(self, region_id: str) -> bool:
        return self.cleared_share(region_id) >= REGION_CLEAR

    def lord_open(self, lord: Lord) -> bool:
        return all(self.region_cleared(r) for r in lord.regions)


def exam_score(payload: Mapping[str, Any]) -> float:
    if payload.get("total") is not None:
        return float(payload["total"])
    scored = [q for q in payload.get("questions", []) if isinstance(q, Mapping)]
    if not scored:
        return 0.0
    return sum(int(q["score"]) for q in scored) / (3 * len(scored))


def track(events: Iterable[Event], calendar: GameCalendar, today: date) -> ArchitectState:
    state = ArchitectState({t: TopicState(topic) for t, topic in TOPICS.items()}, set(), [])
    for event in sorted(events, key=lambda e: e.occurred_at):
        day = calendar.day_of(event.occurred_at)
        if day > today:
            continue
        if isinstance(event, NoteWritten) and event.topic_id in state.topics:
            topic = state.topics[event.topic_id]
            topic.words = event.words
            if event.words >= LEARN_WORDS and not topic.learned:
                topic.learned = True
                state.rewards.append(ArchitectReward(day, LEARN_SOULS, lights=True))
        elif isinstance(event, AgentResult) and event.agent == "tech-lead":
            kind, _, key = event.task.partition(":")
            if kind == "exam" and key in state.topics:
                topic = state.topics[key]
                score = exam_score(event.payload)
                topic.exams += 1
                topic.best = max(topic.best or 0.0, score)
                if score >= PROVE_MARK and not topic.proved:
                    topic.proved = True
                    state.rewards.append(ArchitectReward(day, PROVE_SOULS, lights=True))
            elif kind == "placement" and key in REGION_BY_ID:
                state.placed_regions.add(key)
                for topic_id in event.payload.get("cleared", []):
                    placed = state.topics.get(str(topic_id))
                    if placed is not None and placed.topic.region == key and not placed.proved:
                        placed.proved = placed.placed = True
    return state
