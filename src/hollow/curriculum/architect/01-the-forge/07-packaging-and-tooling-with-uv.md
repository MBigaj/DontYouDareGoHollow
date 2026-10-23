# Packaging and Tooling with uv

> **Why this matters for you:** Reproducible builds and clean dependency management are part of owning a service.

## You should be able to
- Explain lockfiles, dependency resolution and reproducible builds
- Structure a multi-package repo (workspaces)
- Build small, cacheable Docker images for Python

## Lesson
`pyproject.toml` declares what you *need*: ranges such as `fastapi>=0.115`. The resolver turns those ranges into one concrete set of versions, transitive dependencies included. `uv.lock` records that set, with hashes, for every platform. Whoever installs from the lock gets exactly the same packages, whether that is your laptop, CI or the Docker image.

**Services lock, libraries do not pin.** A service is the end of the line, and you want every deploy to be byte-for-byte what you tested, so you lock it. A library is installed *into* someone else's environment. Tight pins there would clash with other libraries, so a library declares honest ranges and lets the application's resolver decide.

**The flags that matter in CI.**
- `uv sync --locked` fails if `uv.lock` no longer matches `pyproject.toml`. That catches someone who edited dependencies without re-locking.
- `uv sync --frozen` installs from the lock without checking it at all. It is fast, and fine in a Docker layer once CI has verified the lock.
- `uv lock --upgrade-package httpx` moves one package and leaves the rest alone.

**Workspaces.** Several packages in one repo, for example `api`, `worker` and a shared `domain`, can be members of a uv workspace. They resolve together into a single lockfile, so they can never disagree on versions, and they depend on each other by path.

**Docker images that cache.** Docker reuses a layer until something it depends on changes. Dependencies change rarely and source code changes constantly, so copy the lockfile before the source:

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev
```

For a small image, build in a builder stage, then copy only the virtualenv and the app into a slim runtime stage, and run as a non-root user. A `.dockerignore` keeps `.venv`, `.git` and caches out of the build context.

**A vulnerable transitive dependency.** First find who pulls it in: `uv tree --invert --package urllib3`. The clean fix is to upgrade that parent. If the parent has not released a fix, add a constraint (`[tool.uv] constraint-dependencies = ["urllib3>=2.2.2"]`) or an override, re-lock, and run the tests. Put `pip-audit` (or a similar scanner) in CI, so the next one finds you.

## Quiz
### Why does a service commit a lockfile while a library keeps honest version ranges?
- [x] A service needs reproducible deploys, while tight pins in a library would clash with its users' other dependencies
- [ ] Libraries cannot have lockfiles
- [ ] Lockfiles make installs slower for libraries
- [ ] PyPI rejects pinned dependencies

Locks are for the end of the line, and ranges are for things others install.

### CI should fail when someone changed `pyproject.toml` but forgot to update `uv.lock`. Which command does that?
- [ ] `uv sync --frozen`
- [x] `uv sync --locked`
- [ ] `uv lock --upgrade`
- [ ] `uv sync --no-cache`

`--frozen` trusts the lock without checking it. `--locked` asserts it is up to date.

### Which Dockerfile order caches dependency installs best?
- [ ] Copy everything, then run `uv sync`
- [x] Copy `pyproject.toml` and `uv.lock`, install dependencies, then copy the source
- [ ] Install dependencies in the final `CMD`
- [ ] Copy the source, install, then copy the lockfile

Source changes then only rebuild the last layers.

### A transitive dependency has a CVE. What is the right first move?
- [ ] Pin it directly in your dependencies and forget about it
- [ ] Wait for the next major release of your framework
- [x] Find the parent with `uv tree --invert`, upgrade it, or constrain the transitive version and re-lock
- [ ] Delete it from the virtualenv in the Dockerfile

Fix it at the source if you can, and constrain only when you must, with tests to back it.

### What does a uv workspace give a repo with several Python packages?
- [ ] A separate lockfile per package
- [x] One resolution and one lockfile shared by every member
- [ ] Automatic publishing to PyPI
- [ ] Docker images for each package

Shared resolution means the packages can never drift apart on versions.

### How do you get a small runtime image for a Python service?
- [x] Build in a builder stage, then copy only the virtualenv and app into a slim runtime stage
- [ ] Use the full `python` image so nothing is missing
- [ ] Install build tools in the runtime image
- [ ] Squash every layer into one

The compilers and caches stay behind in the builder.

## Exam questions
- Why does a lockfile matter for a service but not for a library?
- How do you make a Python Docker build cache well?
- How would you handle a vulnerable transitive dependency?
