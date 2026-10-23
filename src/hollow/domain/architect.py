"""The Architect track: eight skill regions built from the Obsidian roadmap vault, and the
nine Lords of Design that need them.

Each topic is one vault note. Notes that exist twice in the vault (retries, timeouts, rate
limiting, Kafka, caching, TLS, load balancing, profiling) live in one region only. Service
mesh, Azure and Google Cloud are left out for now.

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
    note: str | None
    """Vault path, relative to the vault root; None for topics with no note yet."""


@dataclass(frozen=True)
class SkillRegion:
    id: str
    name: str
    covers: str
    build_boss: str
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
    region_id: str,
    name: str,
    covers: str,
    build: str,
    notes: list[str],
    extra: tuple[str, ...] = (),
) -> SkillRegion:
    topics = [Topic(slug(n.rsplit("/", 1)[-1]), n.rsplit("/", 1)[-1], region_id, f"{n}.md")
              for n in notes]  # fmt: skip
    topics += [Topic(slug(title), title, region_id, None) for title in extra]
    return SkillRegion(region_id, name, covers, build, tuple(topics))


BF, DB, DS, SD, AR, RP, CI, SE = (
    "01 - Backend Fundamentals",
    "02 - Databases & Data",
    "03 - Distributed Systems",
    "04 - System Design",
    "05 - Architecture",
    "06 - Reliability & Production",
    "07 - Cloud & Infrastructure",
    "08 - Security",
)


def _in(folder: str, *names: str) -> list[str]:
    return [f"{folder}/{n}" for n in names]


REGIONS: tuple[SkillRegion, ...] = (
    _region(
        "forge", "The Forge", "Python craft: testing, strict typing, packaging, internals",
        "A fully tested and typed souls ledger",
        _in(f"{BF}/03 - Python Internals", "CPython", "GIL", "Threads", "Multiprocessing",
            "AsyncIO", "Event Loop", "Coroutines", "Generators", "Memory Management", "Profiling"),
        extra=("Testing with pytest", "Strict Typing", "Packaging"),
    ),
    _region(
        "data-depths", "Data Depths", "PostgreSQL, Redis, data modelling, search and storage",
        "A schema with a live Alembic migration, and a slow query fixed with EXPLAIN",
        _in(f"{DB}/01 - PostgreSQL", "ACID", "Transactions", "Isolation Levels", "MVCC", "Locks",
            "Deadlocks", "Indexes", "Composite Indexes", "EXPLAIN", "Query Planner",
            "Data Modelling", "Replication", "Read Replicas", "Partitioning", "Sharding")
        + _in(f"{DB}/02 - Redis", "Caching", "Data Structures", "Expiration", "Eviction Policies",
              "Distributed Locks")
        + _in(f"{DB}/03 - Other Data Systems", "Elasticsearch", "Object Storage")
        + _in(f"{SD}/03 - Scalability", "Database Scaling")
        + _in(f"{AR}/04 - Architecture Case Studies", "SQL vs NoSQL"),
    ),
    _region(
        "api-citadel", "The API Citadel", "API design and security",
        "DontYouDareGoHollow's API with auth and a rate limiter",
        _in(f"{SD}/02 - API Design", "REST API Design", "API Versioning", "Pagination",
            "Idempotency Keys", "Rate Limiting")
        + _in(f"{DS}/03 - Communication", "gRPC")
        + _in(f"{AR}/04 - Architecture Case Studies", "REST vs gRPC")
        + _in(f"{SE}/01 - Authentication", "Sessions", "JWT", "OAuth2")
        + _in(f"{SE}/02 - Authorisation", "RBAC", "ABAC")
        + _in(f"{SE}/03 - Cryptography", "Hashing", "Encryption")
        + _in(f"{SE}/04 - Application Security", "Secure API Design", "OWASP Top 10",
              "Secrets Management"),
    ),
    _region(
        "async-ruins", "The Async Ruins", "Queues, events, retries, dead letters, backpressure",
        "Anki and GitHub sync on a queue that survives crashes",
        _in(f"{DS}/03 - Communication", "Synchronous Communication", "Asynchronous Communication",
            "Message Queues", "Event Streaming")
        + _in(f"{DB}/03 - Other Data Systems", "RabbitMQ", "Kafka")
        + _in(f"{SD}/04 - Messaging", "Queues", "Pub Sub")
        + _in(f"{DS}/05 - Distributed Patterns", "Idempotency", "Dead Letter Queues",
              "Backpressure")
        + _in(f"{AR}/04 - Architecture Case Studies", "Kafka vs Message Queue",
              "Synchronous vs Asynchronous"),
        extra=("Outbox Pattern",),
    ),
    _region(
        "watchtower", "The Watchtower", "Observability, SLOs, performance, resilience, incidents",
        "Dashboards and alerts, plus a postmortem of a deliberate outage",
        _in(f"{RP}/01 - Observability", "Logs", "Metrics", "Distributed Tracing", "OpenTelemetry",
            "Prometheus", "Grafana")
        + _in(f"{RP}/02 - SRE", "SLI", "SLO", "SLA", "Error Budgets")
        + _in(f"{RP}/04 - Performance", "Latency", "Throughput", "Benchmarking")
        + _in(f"{RP}/03 - Resilience", "High Availability", "Failover", "Graceful Degradation",
              "Disaster Recovery")
        + _in(f"{RP}/05 - Incidents", "Incident Response", "Root Cause Analysis", "Postmortems"),
    ),
    _region(
        "iron-keep", "The Iron Keep", "Docker, Kubernetes, Terraform, AWS",
        "DontYouDareGoHollow deployed with infrastructure as code",
        _in(f"{CI}/01 - Docker", "Docker", "Docker Images", "Docker Containers",
            "Docker Networking", "Docker Volumes")
        + _in(f"{CI}/02 - Kubernetes", "Kubernetes", "Scheduling", "Services", "Networking",
              "Ingress", "Autoscaling", "Failure Modes")
        + _in(f"{CI}/05 - Infrastructure as Code", "Terraform")
        + _in(f"{CI}/06 - Cloud Architecture", "AWS", "Cloud IAM", "Cloud Networking",
              "Cloud Storage", "Managed Databases", "Cloud Cost Management"),
    ),
    _region(
        "undercroft", "The Undercroft", "Networking and Linux",
        "One request traced from DNS to a Python handler, every hop explained",
        _in(f"{BF}/01 - Networking", "TCP vs UDP", "IP Addressing", "DNS", "HTTP",
            "HTTP 1.1 vs HTTP 2 vs HTTP 3", "TLS", "NAT", "Reverse Proxies", "Load Balancing",
            "Connection Pooling")
        + _in(f"{CI}/04 - Load Balancing", "L4 vs L7", "Load Balancing Algorithms",
              "Health Checks")
        + _in(f"{BF}/02 - Linux & Operating Systems", "Processes", "Threads", "CPU Scheduling",
              "Memory", "Virtual Memory", "File Descriptors", "System Calls", "Sockets"),
    ),
    _region(
        "distributed-abyss", "The Distributed Abyss",
        "Consistency, failure, scaling and architecture styles",
        "The consistency choices of a tier 3 design, explained and defended",
        _in(f"{DS}/01 - Core Concepts", "What is a Distributed System", "Partial Failures",
            "Network Partitions", "Time in Distributed Systems", "CAP Theorem")
        + _in(f"{DS}/02 - Consistency", "Strong Consistency", "Eventual Consistency",
              "Read After Write", "Causal Consistency")
        + _in(f"{DS}/04 - Failure", "Timeouts", "Retries", "Retry Storms", "Thundering Herd",
              "Cascading Failures", "Split Brain")
        + _in(f"{DS}/05 - Distributed Patterns", "Circuit Breaker", "Bulkhead", "Load Shedding")
        + _in(f"{SD}/01 - Fundamentals", "Requirements Gathering", "Functional Requirements",
              "Non Functional Requirements", "Capacity Estimation", "Trade Offs")
        + _in(f"{SD}/03 - Scalability", "Vertical Scaling", "Horizontal Scaling",
              "Stateless Services")
        + _in(f"{AR}/01 - Architectural Styles", "Monolith", "Modular Monolith", "Microservices",
              "Event Driven Architecture", "CQRS", "Event Sourcing")
        + _in(f"{AR}/02 - Microservices", "Service Boundaries", "API Gateway",
              "Service Discovery", "Distributed Transactions")
        + _in(f"{AR}/03 - Architecture Patterns", "Hexagonal Architecture", "Clean Architecture",
              "Saga Pattern", "Strangler Pattern")
        + _in(f"{AR}/04 - Architecture Case Studies", "Monolith vs Microservices"),
    ),
)  # fmt: skip

LORDS: tuple[Lord, ...] = tuple(
    Lord(slug(name), name, tier, regions, forces,
         f"{note}.md" if note.startswith("04 - ") else f"11 - System Design Practice/{note}.md")
    for name, tier, regions, forces, note in (
        ("URL Shortener", 1, ("data-depths", "api-citadel"),
         "Estimation, key generation, read-heavy caching", "01 - Beginner/URL Shortener"),
        ("Rate Limiter", 1, ("data-depths",),
         "Algorithms, distributed counters, accepting inaccuracy", "01 - Beginner/Rate Limiter"),
        ("File Upload", 1, ("api-citadel",),
         "Object storage, presigned URLs, async processing", "01 - Beginner/File Upload"),
        ("Notification System", 2, ("async-ruins",),
         "Fan-out, retries, DLQs, delivery guarantees", "02 - Intermediate/Notification System"),
        ("Payment System", 2, ("async-ruins", "data-depths"),
         "Idempotency, transactions, sagas, reconciliation", "02 - Intermediate/Payment System"),
        ("Search System", 2, ("data-depths",),
         "Indexing pipelines, Elasticsearch, consistency lag", "02 - Intermediate/Search System"),
        ("Social Feed", 3, ("distributed-abyss",),
         "Fan-out on write vs read, caching at scale",
         "04 - System Design/05 - Design Exercises/Social Media Feed"),
        ("Large E-commerce", 3, tuple(r.id for r in REGIONS),
         "Service boundaries, inventory consistency, peak traffic",
         "03 - Advanced/Large Scale E-commerce"),
        ("Uber- or Netflix-like Platform", 3, tuple(r.id for r in REGIONS),
         "Geo data or streaming, multi-region, cost", "03 - Advanced/Uber-like Platform"),
    )
)  # fmt: skip

TOPICS: dict[str, Topic] = {}
for _r in REGIONS:
    for _t in _r.topics:
        key = _t.id if _t.id not in TOPICS else f"{_r.id}-{_t.id}"
        TOPICS[key] = Topic(key, _t.title, _t.region, _t.note)
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
