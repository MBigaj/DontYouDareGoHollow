# Partitioning and Sharding

> **Why this matters for you:** Tier 3 designs need data split across machines; picking the key is the whole game.

## You should be able to
- Partition tables in PostgreSQL (range, list, hash) and know the trade-offs
- Choose a shard key and explain hot spots and resharding
- Explain what cross-shard queries and transactions cost

## Exam questions
- How would you shard an orders table, and what queries get harder?
- What is a hot partition, and how do you detect and fix one?
- Partitioning vs sharding: what problem does each solve?
