# PostgreSQL vs MongoDB Modelling

> **Why this matters for you:** You run both at work; the senior skill is choosing and modelling for access patterns, then defending it.

## You should be able to
- Model the same domain relationally and as documents
- Choose by access patterns, consistency and transactions, not fashion
- Know where each one hurts at scale

## Lesson
You run both at YouGov, so this step is not about syntax. It is about choosing one for a new piece of data and defending the choice in a design review.

**The modelling instinct differs.** Relational modelling starts from the *entities*: normalise, give each fact one home, and join at read time. Because the data is not shaped for any one query, tomorrow's unplanned report still works. Document modelling starts from the *access patterns*: what is read together is stored together, shaped for the queries you know. It is fast and simple for those, and awkward for the ones you did not plan.

**Embed or reference: the core document decision.** Embed a child in its parent when it is:

- **bounded**, such as an order's line items, or a survey response's answers;
- **owned** by the parent, with no life of its own;
- **read together** with the parent nearly every time.

Reference it, as a separate collection with an id, when it:

- **grows without bound**, such as comments on a post or events on a device;
- is **shared** by many parents, such as a product referenced by thousands of orders;
- is **updated or queried on its own**.

Unbounded embedding is the classic MongoDB failure. Documents creep towards the 16 MB limit. Every update rewrites a larger document. Multikey indexes on the growing array swell. Reads drag the whole history along to show the latest ten. The standard fixes are patterns:

- **subset**: embed the latest N, and keep the rest in their own collection;
- **bucket**: one document per device per hour, instead of one per reading;
- **extended reference**: copy the few fields you display, such as the customer name on an order, and accept that a rename must fan out.

**Transactions and consistency.** PostgreSQL gives you multi-table ACID transactions, foreign keys, unique and check constraints, and the database enforces your invariants. MongoDB makes a *single document* update atomic, and has had multi-document transactions since 4.0 (replica sets) and 4.2 (sharded clusters). They work, but cost latency, have a time limit, and contend on hot documents. Good document design makes single-document atomicity cover most writes. If your core operations keep needing multi-document transactions, the data is relational and you are fighting the database. Remember too that MongoDB reads from secondaries are eventually consistent, and that `writeConcern: majority` is what makes an acknowledged write survive a failover.

**JSONB is the middle road.** A PostgreSQL row with fixed, constrained columns plus a JSONB column for the flexible part covers many "we need Mongo for flexible schemas" arguments:

```sql
CREATE TABLE responses (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  survey_id bigint NOT NULL REFERENCES surveys,
  submitted_at timestamptz NOT NULL,
  answers jsonb NOT NULL
);
CREATE INDEX ON responses USING gin (answers jsonb_path_ops);  -- serves answers @> '{"q7": "yes"}'
```

Know its limits:

- **No statistics inside the document.** PostgreSQL keeps no per-key statistics inside JSONB, so filters on `answers->>'q7'` get rough guesses. Promote hot keys to real columns, or add an expression index, which gets its own statistics.
- **Updates rewrite the whole value.** Changing one key in a large JSONB document rewrites all of it, including its TOAST storage.
- **No constraints inside the JSON**, beyond `CHECK` expressions you write yourself.

**Where each one hurts at scale.** MongoDB has built-in sharding, flexible writes and a natural fit for document-shaped aggregates. It struggles with relational access through heavy `$lookup` joins, cross-document invariants, and ad-hoc analytics across collections. PostgreSQL gives you constraints, joins, a strong planner for unplanned queries, and the SQL ecosystem (BI tools, CDC, extensions). It struggles beyond one primary's write capacity, and with huge sparse documents. Citus or application sharding are real projects, not a setting.

**Moving from MongoDB to PostgreSQL**, you give up native sharding, schema-free writes and document-shaped reads without joins. You gain enforced integrity, transactions across entities, flexible querying and a single source of truth for reporting. Moving the other way, you give those up for horizontal scale and write flexibility. Defend the choice with the access patterns, the invariants, the expected growth and what the team can operate, never with "it's more modern".

## Quiz
### Blog posts collect comments that can grow to tens of thousands per post. How do you model comments in MongoDB?
- [ ] Embed all comments in the post document
- [ ] One document per post per comment author
- [x] A separate comments collection referencing the post, optionally embedding the latest few in the post
- [ ] Store comments in GridFS

Unbounded arrays push documents towards 16 MB and make every update rewrite more data. The subset pattern keeps the common read fast.

### When is embedding the right choice?
- [x] The child data is bounded, owned by the parent and read with it, like an order's line items
- [ ] Whenever the child data is small, even if many parents share it
- [ ] When the child data grows continuously
- [ ] When the child is queried on its own more often than with the parent

Bounded, owned and read together: then one document read serves the whole use case, and one atomic write updates it.

### A PostgreSQL `responses.answers` JSONB column is filtered with `answers @> '{"q7": "yes"}'`, and it is slow. What helps?
- [ ] A B-tree index on `answers`
- [x] A GIN index on `answers`, for example with `jsonb_path_ops`
- [ ] Converting the column to `json`
- [ ] A hash index on `answers`

GIN indexes the keys and values inside the document, which is what the containment operator `@>` needs.

### What is true of multi-document transactions in MongoDB?
- [ ] They do not exist; only single documents are atomic
- [ ] They are free, so there is no reason to embed
- [ ] They only work on standalone servers, not replica sets
- [x] They exist since 4.0, but cost latency and contention, so good models let single-document atomicity cover most writes

If your core writes keep needing them, the data is relational and you are fighting the database.

### The planner badly misestimates a filter on `answers->>'country'` in a JSONB column. Why?
- [x] PostgreSQL keeps no per-key statistics inside JSONB; promote the key to a column or add an expression index
- [ ] JSONB columns are never analysed
- [ ] The `->>` operator disables indexes
- [ ] JSONB stores keys in random order, so estimates are impossible

An expression index on `(answers->>'country')` gets its own statistics after `ANALYZE`, and the estimates improve.

### A team moves a service from MongoDB to PostgreSQL. What do they gain, and what do they give up?
- [ ] Gain horizontal sharding; give up transactions
- [ ] Gain schema-free writes; give up joins
- [x] Gain constraints, joins and multi-table transactions; give up built-in sharding and schema-free writes
- [ ] Nothing changes beyond the query language

Each database's strengths are the other's weaknesses. The choice should follow the invariants and access patterns, not fashion.

## Exam questions
- Survey answers with flexible questions: PostgreSQL JSONB or MongoDB? Defend it.
- When does embedding documents become a problem?
- What do you give up moving from MongoDB to PostgreSQL, and what do you gain?
