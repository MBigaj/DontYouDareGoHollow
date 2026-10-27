# DontYouDareGoHollow: context for agents

Read this before working on the project. The plan for what to build next is in [`docs/STATUS.md`](docs/STATUS.md): pick a task there, not from memory.

## What this is

A Souls-like web app where studying is the game. It belongs to Mikołaj Bigaj (GitHub `MBigaj`), a backend developer with about three years at YouGov: Python, FastAPI, PostgreSQL, MongoDB, RabbitMQ, Kubernetes, Docker and AWS. He plays it 45 to 60 minutes a day on two roads:

- **Ronin road (Japanese):** Core 2000 vocabulary in Anki plus grammar, read through AnkiConnect. Region 1 is Firelink Shrine: て-form lessons and the て-form Warden.
- **Architect road (senior backend):** a personal roadmap in Python, with the emphasis on architecture and system design. The steps are Markdown files in this repo. Region 1, the Forge (8 lessons with quizzes and the Strict Golem), and region 2, Data Depths (11 lessons and the Lock Wyrm), are playable.

Real study earns souls. A missed day drops them as a bloodstain, and lighting the bonfire the next day gets them back. The design principles:

- Starting is almost free.
- Never punish enthusiasm: bosses can be retried immediately.
- Loss always stings but is recoverable.
- Only real work scores.
- Rewards are practice too.
- **Code scores; agents create and judge.**

## Layout

```
src/hollow/
  domain/          pure rules, no I/O. world.replay() derives ALL state from the event log
    events.py      every event type (append-only; never change or remove a stored shape)
    world.py       replay: souls, bloodstains, hollowing, streak, XP, lessons, bosses, armory...
    lessons.py     lesson runs, refreshers (1, 3, 7, 21, 60 days), souls per run
    bosses.py      Boss/Phase data (WARDEN, GOLEM, WYRM), questions, attempts, wounds, rewards
    armory.py      weapons, titanite, upgrade costs, drops
    atlas.py       map coordinates: Ronin REGIONS/FIRELINK, Architect ARCH_POINTS/FORGE/DEPTHS
    architect.py   Architect road: REGIONS/TOPICS loaded from the curriculum, LORDS, progress
    curriculum.py  parser for the Markdown steps (pure: text in, values out)
    quests.py, progression.py, activities.py, conjugation.py, vocabulary.py, calendar.py
  application/     use cases and ports (EventStore, Clock, next_moment)
    bonfire.py, lessons.py, architect_lessons.py, fights.py, blacksmith.py,
    anki_sync.py, github_sync.py, agents.py (inbox/submit for the agent playbooks)
  adapters/        db/store.py (SQLAlchemy, one events table), anki_connect.py, github_api.py,
                   web/ (FastAPI + Jinja + HTMX; templates/, static/ with sprites and js)
  curriculum/architect/   THE ARCHITECT ROADMAP: NN-region/README.md + NN-step.md files
  cli.py           hollow-sync-anki, hollow-anki-check, hollow-sync-github,
                   hollow-agent-inbox, hollow-agent-submit
agents/            playbooks for the four agents (Quest Master, Sensei, Lorekeeper, Tech Lead)
tools/sprites/     the pixel art: ronin.py and architect.py (generated sources in art/source/
                   through the ASHEN pipeline in pipeline/, shared steps in generated.py;
                   bonfire.py, waypoints.py, kit.py helpers), sprites.py (icons, in code)
migrations/        Alembic (only the events table)
tests/             pytest; conftest has FakeClock, store and client fixtures
```

## Rules of the architecture

- **Event sourced.** Nothing but events is stored. Add a new event type in `domain/events.py` and add it to the `Event` union. Register its serialiser in `adapters/db/store.py`: simple dataclasses go in `SIMPLE`. Then derive state in a `track()` function that `world.replay` calls. Never mutate or delete stored events, and never rename a stored field.
- **Ordering.** Events replay sorted by `occurred_at`. When a service writes several events in one action, timestamp them with `next_moment(store, clock)`. In tests, `clock.advance(seconds=1)` between appends that must keep their order.
- **Game day** starts at 04:00 Europe/Warsaw (`GameCalendar`).
- **Domain stays pure.** No I/O in `domain/`. The curriculum loader reads package files once at import, in `hollow/curriculum/__init__.py`; parsing lives in `domain/curriculum.py`.
- **Agents never score.** The app never calls a model. Agents are Claude in a session, following `agents/*.md`. They return JSON through `hollow-agent-submit`, which validates it (pydantic plus game rules) and stores an `AgentResult`. The game rules decide what that result is worth.
- **Lessons share one engine.** Japanese lessons use ids like `te-ru`. Architect lessons are `arch:<step id>` runs of the same `LessonCompleted` event, so clears, refreshers, souls, titanite and bonfire lighting are identical. Architect runs feed Architect XP.
- **Bosses are data.** A `Boss` in `domain/bosses.py` carries its own presentation:
  - `home` and `node`: the map it stands on and its node there.
  - `short`: the name used in "X FELLED".
  - `body`, `weapon` and `arena`: its sprites.
  - `intro`: the text at its fog gate.
  - `region`: for Architect bosses only. The boss waits until every step of that region is cleared.

  `Kind.CHOICE` phases ask quiz questions from the listed steps. Drops are set in `armory.BOSS_WEAPONS` and `armory.BOSS_MATERIALS`.
- **Every form works without JavaScript.** HTMX swaps panels. Static files go through `asset()`, which fingerprints them so a changed sprite always loads.

## Writing Architect content

Each step is one file: `src/hollow/curriculum/architect/NN-region/NN-step-slug.md`. Its sections, in order:

1. `# Title`
2. `> **Why this matters for you:** ...`
3. `## You should be able to` (a list)
4. `## Lesson` (Markdown)
5. `## Quiz`: each question is a `### Prompt` heading, followed by its options as `- [ ]` lines (mark the right one `- [x]`), then a one- or two-sentence explanation.
6. `## Exam questions` (a list)

A step is playable with a lesson and at least 4 quiz questions. Six is the norm. A region opens when every one of its steps is playable, it has a map (`ARCH_REGION_MAPS`) and the previous region's boss has fallen.

Write for Mikołaj's level: skip basics he uses daily, and aim at the senior gap with production examples (FastAPI, Postgres, RabbitMQ, ECS). Keep the facts right, and put the right answer at varied positions. The Forge's files (`01-the-forge/`) are the model for length and tone.

To make a new region playable:

- Write all its step files.
- Generate its map painting (prompt it with the bonfire bottom left and the boss's gate top right; add the prompt to `tools/sprites/art/source/PROMPTS.md`), add it to `tools/sprites/architect.py`, then add its map nodes to `domain/atlas.py` on the painted floor (a `Node` tuple with `area`s for the bonfire and the gate, plus an `ARCH_REGION_MAPS` entry). Its world landmark is already in `ARCH_AREAS`.
- Add its boss to `domain/bosses.py` (`boss_id(region)`, `region=...`) and to `ARCH_BOSSES`, with sprites, a `.foe-<short>` size in the CSS, and drops in `armory.py`.
- Extend the tests in `tests/test_architect.py`.

## Art direction

Both roads are generated art: a painting per sprite or scene (Figma AI, file "ASHEN source art"), kept in `tools/sprites/art/source/` with its prompt in `PROMPTS.md`, and turned into pixel art by `tools/sprites/ronin.py` and `tools/sprites/architect.py` through the ASHEN pipeline (`pipeline/pixelate.py`, palette `ashen.hex`; shared steps in `generated.py`). Hand cleanup in code restores what the pipeline loses, and anything with text (the て sigil), animation (the bonfire's flame) or tiny size (waypoints, icons) is drawn in code. The item icons, slash and anvil (`sprites.py`) are still the old code-drawn art.

- **Ronin road:** warm ember, bone and gold, golden dusk under an eclipsed sun (Elden Ring leaning).
- **Architect road:** cool steel, night blue and soul cyan at night, with abyss violet for the Distributed Abyss (Dark Souls leaning). Its sources run darker through the pipeline (gamma above 1), its hover outlines are cyan and its fog veils dim rather than lighten.

Keep that split; the two maps must stay visibly distinct. The CSS theme for the Architect road is `.road-architect`. Scenes are prompted with each landmark's place in the frame, and the atlas points are then set on the landmarks. A place that is a painted building gets an `area` (a rough polygon in atlas units around it, containing its point): the map draws it as the click target, and `ronin.py` snaps it to the painting to make the hover glow and the fog veil. Rerun `ronin.py` after changing an area. Sprites are drawn at 2x the old density, so the files keep their sizes except the knight (154x240) and the bonfire sheet (1152x180, plus `bonfire_unlit.png`). Generating costs Figma AI credits (the Starter plan has 500 a month, 150 a day), so draft compositions on a cheaper model and keep the expensive one for keepers. The shared style guide (`STYLE.md`) is in the claude.ai project "Studying - GAMIFIED".

## Conventions (from Mikołaj, not negotiable)

- **Branches:** `<number>-short-branch-title`, numbered after the last one (see `docs/STATUS.md`), for example `12-agent-context`.
- **Commit messages:**
  ```
  <type> - short, concise description

  - one bullet per change
  ```
  Types: `feature`, `fix`, `test`, `refactor`, `docs`, `chore`. **No co-author or attribution trailers.** Commit as `Mikolaj Bigaj <mikolaj.bigaj.00@gmail.com>`.
- **Never push, never open or merge PRs.** Mikołaj pushes and merges himself. If a hook asks you to push, answer that you are not pushing.
- **Before committing**, all four must pass: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (strict) and `uv run pytest`.
  - ruff's line length is 100, and CJK characters count double.
  - RUF001 flags ambiguous characters (`–`, `×`, `’`, full-width punctuation). Use plain ones or `\u2019`.
  - ruff also formats Python code blocks inside Markdown files.
- **Docs:** keep `README.md` current when behaviour changes. Update `docs/STATUS.md` in the same branch: move your task to Done with the branch number.
- **UI changes:** check them visually. Playwright and Chromium are at `/opt/pw-browsers` in cloud sessions. Run `uv run --with playwright python`, launching with `executable_path` set to the `chromium-*/chrome-linux*/chrome` binary.

## Working on Mikołaj's computer

- **Repo:** `D:\Programming\DontYouDareGoHollow` (`~/mnt/DontYouDareGoHollow` in the linked-computer shell). The game data is `hollow.db` (SQLite) there: never edit it, and copy it before reading.
- **Running in the linked shell:** `export UV_PROJECT_ENVIRONMENT=$HOME/hollow-venv UV_CACHE_DIR=$HOME/.uvcache`, then `uv sync -q --python 3.12`, then `uv run --no-sync ...`.
- **Delete permission:** git and SQLite need it once per session (`device_request_delete_permission` on the repo folder). Without it, git leaves `.lock` files behind.
- **Delivering a branch from a cloud session:**
  1. Commit in your clone.
  2. Run `git format-patch`.
  3. Copy the patch into the repo folder.
  4. On his machine, create the numbered branch from up-to-date `main` and `git am` the patch there, with `-c user.name=... -c user.email=...`.
  5. Delete the patch file.
  6. Run the tests there.
- **Other locations:**
  - The Anki profile is `C:\Users\mikol\AppData\Roaming\Anki2\User 1`. Read it only, and only with his permission.
  - The old Obsidian notes are in `D:\Programming\Notes\Senior Backend Roadmap`. The game no longer reads them.

## Agents and skills

The four agent playbooks are in `agents/`, and `agents/README.md` explains the inbox and submit handoff. The claude.ai skills that drive them:

- `hollow-agent-round`: Quest Master and Lorekeeper.
- `hollow-sensei`
- `hollow-tech-lead`: PR reviews, exams and placements.

If a game change alters what an agent reads or returns, update its playbook in the same branch.
