# mypy --strict in Practice

> **Why this matters for you:** You write type hints every day; strict mode is where they start catching real bugs and documenting intent.

## You should be able to
- Use Protocols, generics, TypedDict, overloads and ParamSpec where they pay off
- Explain variance, and why `list[Child]` is not a `list[Parent]`
- Introduce strict mode into an untyped codebase without stopping delivery

## Lesson
Plain mypy is lenient: an unannotated function is simply not checked, and `Any` leaks quietly from untyped libraries. `--strict` turns on the flags that close those holes: every function must be annotated, generics need their parameters (`list[int]`, not `list`), returning `Any` from a typed function is reported, unused `# type: ignore` comments are flagged, and re-exports must be explicit. The result is that a green check actually means something.

**Structural vs nominal.** An ABC is nominal: a class satisfies it only by inheriting from it. A `Protocol` is structural: anything with the right methods satisfies it, including classes from libraries you cannot edit. Ports in a hexagonal design are a natural fit for Protocols, because the adapters never need to import the domain's base classes. Reach for an ABC when you want shared implementation or to force subclasses to register.

**Variance.** `list` is mutable, so it is *invariant*: if a function accepts `list[Animal]`, it may append a `Cat`, which would corrupt your `list[Dog]`. `Sequence` is read-only, so it is *covariant*: a `Sequence[Dog]` is a fine `Sequence[Animal]`. Callable arguments are *contravariant*: a function that handles any `Animal` can stand in where a `Dog` handler is expected. Rule of thumb: accept the most abstract read-only type you need (`Sequence`, `Mapping`, `Iterable`), return concrete ones.

**The right tool for the shape.**
- `TypedDict` types a dict with known keys, such as a JSON payload, without converting it into a class.
- `@overload` describes functions whose return type depends on the arguments.
- `ParamSpec` lets a decorator keep the wrapped function's exact signature:

```python
P = ParamSpec("P")
R = TypeVar("R")


def logged(fn: Callable[P, R]) -> Callable[P, R]:
    def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(*args, **kwargs)

    return inner
```

**Rolling it out.** Fixing a 50k-line service in one pull request never ships. Turn `strict = true` on globally, add per-module overrides that relax the legacy packages, and make CI fail on any new error. Then ratchet: remove one override at a time, starting with the modules you touch most. New code is strict from day one.

**Escape hatches cost trust.** `cast()` and `# type: ignore` are claims the checker cannot verify. Use the narrow form, `# type: ignore[arg-type]`, with a comment saying why, and keep `warn_unused_ignores` on, so the ignore disappears when it stops being needed. Annotating something as `Any` is the most expensive option, because it silently switches checking off everywhere that value flows.

## Quiz
### Why does mypy reject passing a `list[Dog]` where a `list[Animal]` is expected?
- [x] `list` is mutable and so invariant: the callee could append a `Cat` to your list of dogs
- [ ] mypy does not support subclasses inside generic types
- [ ] `Dog` would have to inherit from `list` explicitly
- [ ] It is only an error with `--strict`; plain mypy accepts it

Mutability is the reason. A read-only `Sequence[Animal]` parameter would accept `list[Dog]`, because nothing can be written into it.

### When is a `Protocol` the better choice than an ABC?
- [ ] When the base class should share implementation with its subclasses
- [x] When classes you do not control should satisfy the interface without inheriting from it
- [ ] When you need `isinstance` to check full method signatures at runtime
- [ ] When you want subclasses to be forced to register themselves

Protocols are structural. `@runtime_checkable` only checks that the methods exist, not their signatures.

### How do you type a decorator so the wrapped function keeps its exact signature?
- [ ] `Callable[..., Any]` for both the argument and the return value
- [ ] An `@overload` for every function it decorates
- [x] A `ParamSpec` for the parameters and a `TypeVar` for the return type
- [ ] A `TypedDict` describing `*args` and `**kwargs`

`Callable[P, R]` in and `Callable[P, R]` out carries the parameters and the return type through unchanged.

### What is the realistic way to bring `--strict` to a 50k-line untyped service?
- [ ] One large pull request that fixes every error before turning it on
- [ ] Run strict mode locally only, never in CI
- [x] Strict globally, per-module overrides for legacy code, CI blocks new errors, then remove overrides one by one
- [ ] Add a bare `# type: ignore` to every failing line and clean them up later

The ratchet keeps delivery moving and guarantees things only get better. Bare ignores hide the real errors and also every future error on those lines.

### Which escape hatch costs the least when mypy is wrong about a line?
- [ ] Annotating the value as `Any`
- [ ] A bare `# type: ignore`
- [ ] `cast(Any, value)`
- [x] `# type: ignore[arg-type]` with a short reason, and `warn_unused_ignores` on

The narrow ignore silences one error code on one line, and tells you when it is no longer needed. `Any` switches checking off wherever the value travels.

### What does `TypedDict` fit best?
- [x] A JSON payload with known keys that you pass around as a dict
- [ ] A mutable object with behaviour and methods
- [ ] A fixed set of named constants
- [ ] A tuple whose positions have different types

`TypedDict` types the dict itself, with no conversion step. Methods belong on a dataclass, and constants belong in an `Enum`.

## Exam questions
- When do you reach for a Protocol instead of an ABC?
- Why is `list` invariant but `Sequence` covariant?
- How would you roll `mypy --strict` out across a 50k-line service?
- What do `cast()` and `type: ignore` cost you, and when are they acceptable?
