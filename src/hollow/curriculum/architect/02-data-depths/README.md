---
id: data-depths
name: Data Depths
covers: PostgreSQL internals, data modelling at scale, caching
start: Half cleared: you model and query PostgreSQL and MongoDB daily.
boss: The Lock Wyrm
boss_blurb: Coiled around the rows it holds, it waits for you to take the wrong lock.
build: A schema with a zero-downtime Alembic migration, and a slow query fixed with EXPLAIN
---
# 2. Data Depths

Flooded vaults of rows and versions. Every read sees its own snapshot of the world.

**Covers:** PostgreSQL internals, data modelling at scale, caching  
**Where you start:** Half cleared: you model and query PostgreSQL and MongoDB daily.  
**Boss:** The Lock Wyrm  
**Build challenge (later):** A schema with a zero-downtime Alembic migration, and a slow query fixed with EXPLAIN

## Steps
1. [MVCC and Isolation Levels](01-mvcc-and-isolation-levels.md)
2. [Locks, Deadlocks and Contention](02-locks-deadlocks-and-contention.md)
3. [Reading Query Plans](03-reading-query-plans.md)
4. [Index Design](04-index-design.md)
5. [Zero-Downtime Migrations](05-zero-downtime-migrations.md)
6. [Replication and Read Replicas](06-replication-and-read-replicas.md)
7. [Partitioning and Sharding](07-partitioning-and-sharding.md)
8. [Caching Patterns and Invalidation](08-caching-patterns-and-invalidation.md)
9. [Redis Beyond Caching](09-redis-beyond-caching.md)
10. [PostgreSQL vs MongoDB Modelling](10-postgresql-vs-mongodb-modelling.md)
11. [Connection Pooling Under Load](11-connection-pooling-under-load.md)
