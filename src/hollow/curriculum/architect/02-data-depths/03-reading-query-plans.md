# Reading Query Plans

> **Why this matters for you:** EXPLAIN ANALYZE is the difference between 'add an index' folklore and knowing.

## You should be able to
- Read EXPLAIN ANALYZE: scan types, joins, estimates vs actuals, buffers
- Explain why the planner chose a plan, and how statistics mislead it
- Fix a slow query and prove it with numbers

## Exam questions
- Seq scan on a table with an index: list three reasons it can be the right choice.
- Estimated rows 10, actual 1,000,000. What went wrong and how do you fix it?
- Nested loop vs hash join vs merge join: when does each win?
