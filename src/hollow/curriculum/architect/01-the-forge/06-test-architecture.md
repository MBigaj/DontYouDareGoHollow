# Test Architecture

> **Why this matters for you:** Fast, trustworthy suites come from design: fakes at the ports, few mocks, the right test at each layer.

## You should be able to
- Test hexagonal code with fakes at the ports instead of mocks
- Balance unit, integration and end-to-end tests by cost and confidence
- Keep tests fast and non-flaky with real databases where it matters

## Lesson
Every test buys confidence at a price: run time, maintenance and flakiness. A good suite puts each kind of test where it is cheapest for the confidence it gives. A hexagonal design makes that placement obvious:

- **Domain:** pure functions and value objects. Plain unit tests, thousands of them, milliseconds each. This is where Hypothesis lives.
- **Application services:** test them through their ports with **in-memory fakes**, such as a list-backed event store or a fixed clock. The fake is a real, small implementation of the port, so the test checks *behaviour*: given these events, the service records that one.
- **Adapters:** test them against the real thing. SQL, constraints, transactions and migrations need a real PostgreSQL, run as a CI service container or with Testcontainers. A SQLite stand-in hides exactly the bugs you care about.
- **End to end:** a handful of tests through HTTP that prove the wiring.

**Mocks vs fakes.** A mock that asserts `repo.save.assert_called_once_with(...)` checks *how* the code talks to its collaborators. Rename a method, batch two saves, or move a call, and the test breaks, though nothing is wrong. Meanwhile the real repository might reject the data, and the mock never notices. Keep mocks for the edges you cannot run, like a payment provider's API, and assert on outcomes everywhere else.

**Between services: contract tests.** An end-to-end environment with ten services is slow and flaky. A contract test pins only what matters: the provider still accepts the requests, and returns the fields, that its consumers depend on. Consumer-driven contracts (Pact, or a shared schema checked in both CI pipelines) catch breaking changes before deploy.

**Message consumers.** To test a RabbitMQ consumer end to end in CI:
1. Run a real broker as a service container.
2. Publish a message.
3. Assert the side effect and that the message was acknowledged.
4. Publish the *same* message again and assert that nothing doubles. Brokers redeliver, so idempotency is part of the contract.

**Flakiness is a design smell.** The usual causes are the current time (inject a clock), randomness (seed it), ordering assumptions, shared state between tests, and the real network. Fix the cause. Retrying flaky tests teaches the team to ignore red builds.

## Quiz
### Why do heavily mocked tests break on refactors without catching real bugs?
- [x] They assert how the code calls its collaborators, not what it achieves
- [ ] Mocks are slower than real objects
- [ ] Mocks cannot be typed
- [ ] pytest runs mocked tests in a random order

Interaction assertions couple the test to the implementation. Outcome assertions survive refactors.

### What is the best test double for a repository port in application-service tests?
- [ ] A `MagicMock` with `assert_called_with` checks
- [x] An in-memory fake that implements the port
- [ ] The production adapter pointed at SQLite
- [ ] No double: always use the real database

A fake behaves like the real thing in miniature, so tests check behaviour and stay fast.

### Where is a real PostgreSQL in tests worth its cost?
- [ ] In domain unit tests
- [ ] Nowhere: SQLite behaves the same
- [x] In adapter tests: SQL, constraints, transactions and migrations
- [ ] Only in production smoke tests

The database adapter's job is the database. Test it against the real one.

### What does a contract test between two services check?
- [x] The provider still satisfies the requests and responses its consumers rely on
- [ ] Both services pass their own unit tests
- [ ] The two services run the same Python version
- [ ] A full user journey across every service

It replaces a slow shared environment with a fast check of the interface itself.

### A test fails now and then because it reads `datetime.now()`. What is the right fix?
- [ ] Retry the test up to three times
- [ ] Add a `sleep` before the assertion
- [x] Inject a clock and pass a fake one in the test
- [ ] Mark it `xfail`

Time is an input. Make it one.

### What does a solid end-to-end test of a RabbitMQ consumer in CI include?
- [ ] Mocking `pika` and asserting `basic_ack` was called
- [x] A real broker: publish, assert the effect and the ack, then redeliver the same message and assert nothing doubles
- [ ] Calling the consumer's handler function directly
- [ ] A test against the staging broker

Redelivery is normal broker behaviour, so idempotency belongs in the test.

## Exam questions
- Why do heavily mocked tests break on refactors without catching bugs?
- What belongs in a contract test between two services?
- How do you test a RabbitMQ consumer end to end in CI?
