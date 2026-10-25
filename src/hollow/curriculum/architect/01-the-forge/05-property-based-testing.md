# Property-Based Testing

> **Why this matters for you:** Example tests only check the cases you thought of; Hypothesis finds the ones you did not.

## You should be able to
- Write Hypothesis properties for pure logic (round trips, invariants, oracles)
- Use stateful testing for something like a ledger or a cache
- Know when property tests are not worth it

## Lesson
An example test says *for this input, expect this output*. A property test says *for every input of this shape, this must hold*. It then lets Hypothesis generate hundreds of inputs from *strategies*:

```python
from hypothesis import given, strategies as st


@given(st.lists(st.integers()))
def test_sort(xs: list[int]) -> None:
    out = sorted(xs)
    assert all(a <= b for a, b in zip(out, out[1:]))  # ordered
    assert Counter(out) == Counter(xs)  # same items
```

When a property fails, Hypothesis **shrinks** the input: it keeps simplifying the failing case until it finds the smallest one that still fails. A list of 40 random integers becomes `[0, -1]`. It also saves failing examples in a local database and replays them on the next run.

**Properties worth writing.**
- *Round trip:* `parse(serialize(x)) == x`. This catches encoders, mappers and anything with a pair of functions.
- *Invariants:* what must always be true. A balance is never negative; the output is a permutation of the input.
- *Oracle or model:* compare your clever implementation with a slow, obvious one.
- *Idempotence:* `f(f(x)) == f(x)` for normalisers and upserts.

**Stateful testing.** For objects driven by a sequence of operations, such as a souls ledger, a cache or a queue, a `RuleBasedStateMachine` generates random *sequences* of calls. After every step it checks the real object against a simple model, such as a dict or a running total. This finds the bugs that need three specific operations in a specific order, which nobody writes example tests for.

**Pinning a failure.** Hypothesis is random. When it finds a bug in CI, add the shrunk input as `@example(...)` on the test (or as a normal regression test), so it is checked on every run forever.

**When not to bother.** Thin glue code, such as a handler that calls a service, has no interesting property. A "property" that just re-implements the code under test proves nothing. Properties shine on pure logic with rich input spaces: parsers, money, scheduling, game rules like refresher intervals.

## Quiz
### What does shrinking do when a property fails?
- [ ] Runs fewer examples to save time
- [x] Simplifies the failing input to the smallest case that still fails
- [ ] Shrinks the size of the generated data for every run
- [ ] Removes flaky examples from the database

A minimal counterexample usually points straight at the bug.

### Which is the best property for a souls ledger?
- [ ] After `add(10)`, the balance is 10
- [ ] Running any operations does not raise
- [x] For any sequence of valid operations, the balance equals gains minus spends and never drops below zero
- [ ] The balance equals what the ledger's own `balance()` method returns

The first is an example test, the second is very weak, and the last is a tautology.

### Which of these is a round-trip property?
- [ ] `len(sorted(xs)) == len(xs)`
- [x] `parse(serialize(x)) == x`
- [ ] `f(f(x)) == f(x)`
- [ ] `fast(x) == slow(x)`

The others are an invariant, idempotence and an oracle, in that order.

### What is stateful testing best at?
- [x] Objects driven by sequences of operations, checked against a simple model after every step
- [ ] Pure functions with one argument
- [ ] Testing HTML templates
- [ ] Load testing an API

It finds bugs that need a particular order of operations.

### Where are property tests usually a waste?
- [ ] Parsers and serialisers
- [ ] Money and rounding logic
- [x] Thin glue code, where the property would just restate the implementation
- [ ] Scheduling rules like refresher intervals

There is no independent truth to check in glue code.

### Hypothesis finds a failure in CI. How do you keep that case tested forever?
- [ ] Increase `max_examples` so it shows up again
- [x] Add the shrunk input as an `@example(...)` or a regression test
- [ ] Set `derandomize=True`
- [ ] Nothing: Hypothesis's local database is enough

The example database lives on one machine and is usually not in CI. An explicit example travels with the code.

## Exam questions
- What property would you test for a souls ledger?
- How does shrinking help when a property fails?
- Where do property tests beat example tests, and where are they a waste?
