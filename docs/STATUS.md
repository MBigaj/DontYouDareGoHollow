# Status: what is done and what is next

The project's board. To pick up work:

1. Choose one task from **Up next**, or from the **Backlog** if Mikołaj asks for it. Prefer the top of Up next.
2. Create the next numbered branch. The last used number is in **Done**.
3. In that branch, move the task to **In progress** with your branch name and keep its entry current with every commit (done, next, decisions, open questions), so another agent can pick it up mid-branch. When it is finished, move it to **Done** with a one-line summary and update Up next and the Backlog. The full rule is in `CLAUDE.md` under Conventions.
4. Keep tasks small enough for one branch. If a task turns out bigger, split it here and do the first part.

The full design is the plan document, "DontYouDareGoHollow: A Souls-like Study Game", in Mikołaj's claude.ai docs. This board is the short version, kept true to the code.

## In progress

Template for an entry:

```
### <branch>
- Done: ...
- Next: ...
- Decisions: ...
- Open: ...
```

## Done

| # | Branch | What it delivered |
| --- | --- | --- |
| 1 | `1-phase-0-kindling` | Bonfire, manual study logging, souls ledger as an event log, bloodstains, hollowing, pixel UI, Docker and Postgres setup |
| 2 | `2-anki-sync` | Souls from Anki through AnkiConnect (reviews and new cards, each imported once), `hollow-sync-anki`, `hollow-anki-check` |
| 3 | `3-github-sync` | Merged PRs with passing CI in `MBigaj/hollow-trials` pay 100 souls |
| 4 | `4-levelling` | Stats (Vigor, Endurance, Faith, Intelligence), levelling with souls, Effigies (2 a week), Ronin and Architect jobs, character page, background sync on page load |
| 5 | `5-lessons` | て-form lessons built from the verbs learned in Anki, refreshers at 1, 3, 7, 21 and 60 days, hiragana tooltips on kanji |
| 6 | `6-world-map` | Walkable world map and Firelink Shrine map, new knight sprite, the knight teleports between points |
| 7 | `7-te-warden` | Boss engine (phases, HP, Estus, wounds, resting at the fog gate, first-try bonus) and the て-form Warden, phases 1 and 2 |
| 8 | `8-blacksmith` | Weapons for both jobs, titanite drops (lessons, bosses, PRs, cards), upgrades, the Warden's Maul with Soul Siphon |
| 9 | `9-agent-playbooks` | Playbooks for the Quest Master, Sensei, Lorekeeper and Tech Lead (`agents/`) |
| 10 | `10-agent-handoff` | `hollow-agent-inbox` and `hollow-agent-submit`, daily quests and roulette checked by code, lore texts, Journal page |
| 11 | `11-architect-track` | Architect road on the map: the 82-step roadmap as Markdown in the repo, the Forge playable (8 lessons with quizzes), the Strict Golem, a road picker with distinct art, Tech Lead exams and placement trials |
| 12 | `12-agent-context` | This board and `CLAUDE.md`, the context file for agents |
| 13 | `13-character-stats-overlap` | Character page: the knight and stats stay in their panel (the arena's `.hero` rules are scoped to `.arena`), stat values no longer overflow on narrow screens |
| 14 | `14-data-depths-lessons` | Data Depths written: lessons and 6-question quizzes for all 11 steps (MVCC to connection pooling); a written region now also needs its map before it opens; lesson tables scroll on phones |
| 15 | `15-data-depths-map` | Data Depths playable: its flooded-vault map, the Lock Wyrm (three quiz phases, +3) with his arena and the Lock Wyrm's Chain; weapon damage measured against the next Architect boss standing; map labels open inward at the edges; boss sprites shrink on phones |
| 16 | `16-ronin-art` | Ronin road redrawn from generated art through the ASHEN pipeline: the knight, the て-form Warden (one sprite, maul in hand), the Firelink map and arena, the world map (region points moved onto its landmarks), rune-stone waypoints, a new bonfire (flame spiralling up the blade, firelight, an unlit state) and a shrine stage on the home page, cold until the day is lit |
| 17 | `17-map-landmarks` | On the Ronin maps the painted landmarks are the places: hovering a region (or Firelink's bonfire and fog gate) outlines it in gold, clicking walks the knight there, fogged regions sit under a grey veil; stones get a pixel outline on hover (cyan on the Architect road); works without JavaScript |
| 18 | `18-architect-art` | Architect road redrawn from generated art at night: its world map (eight landmarks as places, the Distributed Abyss looming in the sky), the Forge hall and the flooded Data Depths archive (lesson points moved onto the painted floor and causeways), the Strict Golem, the Lock Wyrm and both arenas; iron obelisk waypoints and the chain icon at 2x; shared pipeline steps in `generated.py` |
| 19 | `19-hollow-ronin` | A new hero: a hollow ronin (kasa hat, one ember eye, ragged indigo haori, bandaged hands), generated empty-handed in a weapon-agnostic stance with his grip point recorded for the weapons to come; mirrored to face the bosses |
| 20 | `20-equipment` | The hero carries what you equip: every weapon cut from one generated sheet (`weapons.py`) into a 72 px icon and a layer gripped in his fist, stacked on the home stage, the character page, the maps (the road you walk) and in fights (the boss's road); the Architect's hammers became the Pilgrim's and Surveyor's Shakujō (old ids read as the staffs) |
| 21 | `21-item-art` | The last code-drawn art replaced: the item icons (estus, ember, lens, sign, ring, tome, soul) and a sprite per titanite grade cut from one generated sheet (`items.py`), a generated anvil for the blacksmith and a crescent hit slash; icons shown at their file size (48 px, the souls counter's soul at 28) |
| 22 | `22-sound` | Sound effects: Kenney CC0 recordings layered with synthesis (`tools/sounds/sounds.py`) for the bonfire, souls, drops, fights (fog, strikes, blows, estus, phase, felled, death), the anvil, coins, equipping, levelling up, map footsteps and soft lesson ticks; cues sent by the server as `data-sfx`, played on HTMX swaps only; a ♪ mute toggle in the header |
| 23 | `23-hero-armour` | Armour with real effects, one piece per slot drawn on the hero: Wanderer's Iron Hood (bought, +20 HP), Warden's Bronze Pauldrons (mistakes -5 HP), Golem's Riveted Gauntlets (+1 Estus), Wyrm-scale Greaves (+15 points lesson titanite); the blacksmith split into Weapons, Armour, Rings and items, Recent finds; the Architect road's cyan eye and scarf; `armour.py` cuts a generated sheet into icons and paints each piece onto the hero's own silhouette; the status rule for agents in `CLAUDE.md` |
| 24 | `24-warden-phase-3` | The Warden's third phase: he speaks four lines built from your verbs, you answer each in a Japanese sentence in the fight, and the Sensei judges the transcript in the next agent round (3 good of 4 fell him; fewer is a death and the retry starts at his question); attempts record their phase count; the verdict shows on the fog gate |
| 25 | `25-plain-forms` | Undead Village, part 1 of 3: the conjugation engine learns the plain forms (〜ている, 〜た, 〜ない, 〜なかった, with ある → ない); six Undead Village lessons on them, a mixed one cycling the forms; the region sealed until the Warden falls (lessons, quests, inbox); `/lessons` grouped by region, listing only lessons you can play (the rest counted in one line), with hints per form; the rule to work directly in Mikołaj's repo in `CLAUDE.md` |
| 26 | `26-undead-village-map` | Undead Village, part 2 of 3: its generated map (a dead village climbing to the gargoyle's gatehouse at dusk), a stone per plain-form lesson up the street, the bonfire and gate as landmarks; `/map/<region>` for any Ronin region in `RONIN_REGION_MAPS`, opened by `REGION_GATES`; `ronin.py OUT <region>` builds one map. Branched from 25 (not merged when it began) |
| 27 | `27-plain-form-gargoyle` | Undead Village, part 3 of 3: the Plain-Form Gargoyle at the village gatehouse, waiting for 3 cleared village lessons; plain-form phases (〜た/〜ない, then 〜なかった/〜ている, timed) and a conversation in plain forms judged by the Sensei with its own rubric; drops the Gargoyle's Tail Halberd (Soul Siphon) and the Gargoyle Helm (right answers in boss fights pay 2 more souls, recorded on `FightStarted`); his sprite, arena and gear generated in Figma; `weapons.py` reads more than one sheet. Branched from 26 (25 and 26 not merged when it began) |
| 28 | `28-rune-stones` | New Ronin waypoints (Mikołaj, 1 Nov: the old ones looked poor): a grave stone painted from a generated `tombstone.jpg` (light, cracks, moss) with a recessed panel, rim light, grass and a crisp kana drawn in code; て on Firelink, た on Undead Village (`waypoint_ta*.png`, swapped in by the CSS); `ronin.py OUT waypoints`. Branched from 27 |

## Up next

In a sensible order. Each one fits a branch.

1. **Lore for the Architect road.** `lore_targets()` in `application/agents.py` only knows the Ronin regions. Add the Architect regions, so the Lorekeeper can write region and boss lore for them.
2. **Deploy.** Put the Docker image on one small host (DigitalOcean was the plan) with PostgreSQL and `HOLLOW_PASSWORD`. Anki sync keeps running from his PC with `hollow-sync-anki` on a schedule, which needs the API to accept pushed reviews or a remote database URL. That design decision is Mikołaj's: ask first.

## Backlog

Grouped by area. Ask Mikołaj before starting anything marked *(decide)*.

### Architect road
- Regions 3 to 8 (API Citadel, Async Ruins, Watchtower, Iron Keep, Undercroft, Distributed Abyss): lessons, maps and bosses. The bosses are already named in each region's README.
- **Lords of Design fights:** a design fight with the Tech Lead in three phases (design; the rules change, for example 10x traffic or multi-region; failure injection), scored on a fixed rubric. A win also needs a diagram and an ADR. Needs an `AgentResult` shape, a page per Lord and rewards. Lords open when their regions' bosses fall (already in `domain/architect.py`).
- **Build gate:** CI-checked coding challenges in `hollow-trials`, where a green run awards souls and titanite. The Forge's build is "a fully tested and typed souls ledger" (mypy --strict, 90% coverage, a Hypothesis property test).
- **Echoes:** his three YouGov projects (AI chat API layer, RPC to API migration, Lambda to ECS) as retrospective ADRs, then challenged by the Tech Lead.
- **Weekly Trade-off Duels:** 20-minute ADRs (PostgreSQL vs MongoDB, Kafka vs RabbitMQ, microservices vs modular monolith, REST vs gRPC, sync vs async).
- **Portfolio export:** each felled Lord becomes a case study for mbigaj.github.io (problem, diagram, ADR, 10x section).

### Armour
- **More pieces per slot** as bosses arrive: each new boss (the Architect regions 3 to 8, Ronin regions 3 to 6) can drop one, with its own effect, as the Gargoyle Helm did. Positioning is already saved per slot (`FITS` in `tools/sprites/armour.py`): a new piece needs its painting, an `ARMOUR` entry and a `LOOKS` entry (icon cell and painter), as `CLAUDE.md` under Armour art lists.
- **Armour lore:** `lore_targets()` in `application/agents.py` asks for `weapon:` and `material:` lore only. Add `armour:<id>` so the Lorekeeper writes for the pieces, and show it at the blacksmith like weapon lore.

### Ronin road
- **A waiting verdict on the bonfire:** while the Warden waits for the Sensei, or once a verdict comes in, the home page could say so (today it shows only on the fog gate and in the inbox).
- **More conversation phases:** the engine is generic (`Kind.CONVERSATION`, `Phase.prompts`), and the Plain-Form Gargoyle ends the same way (`Kind.PLAIN` lines, `Phase.rubric`); later Ronin bosses can follow with lines for their own grammar in `spoken()`.
- Regions 3 to 6 (Kanji Catacombs, Sen's Fortress, Anor Keigo, the Kiln) with their grammar and bosses; the Kiln lines up with JLPT N4.
- **Furigana fading:** readings fade as the Ronin levels up.
- **Free conversation with the Sensei:** practice only, nothing saved.

### Systems from the plan
- **Items:** Ember (restores all hollowing), Furigana lens, Phantom sign (one hint from the Sensei or Tech Lead in a fight, losing the no-help bonus), Tomes, Rings. Their sprites exist; there is no inventory yet. Rings are worn but never drawn on the hero (Mikołaj, 30 Oct); the blacksmith's "Rings and items" section is waiting for them, and Intelligence 10 already promises a second ring slot. Faith and Intelligence perks are described in `domain/progression.py` but mostly not wired.
- **Weapon infusions** at +5 and **weapon arts** at +10; more boss weapon skills.
- **Skill decay and Revenants:** untouched regions dim on the map, and beaten bosses return for short rematches.
- **Invasions:** surprise 3-minute quizzes on older material, opt in.
- **Covenants:** a weekly focus worth 1.5x souls. **Weekly raid:** one bigger challenge, reset every Monday.
- **Kindled challenge and NG+:** harder versions of beaten bosses and regions.
- **Ground messages** from the Lorekeeper (short hints on the map), alongside the player's own messages.

### Architecture practice on the app itself (each is a build boss)
- Move Anki and GitHub sync onto a queue with an outbox, so they survive crashes (Async Ruins).
- Use CQRS for stats reads, and later extract one service with the strangler fig, with an ADR on whether it was worth it.
- Observability: OpenTelemetry tracing, SLOs and burn-rate alerts, and a postmortem of a deliberate outage (Watchtower).
- Infrastructure as code: deploy with Terraform (Iron Keep).

### Art and platform
- **The Gargoyle's gear at full size:** `gargoyle_gear.jpg` is the 256 px preview upscaled 6x (the Figma MCP's daily limit). Pull node 3:4 of "ASHEN source art - armour" at full size, then rerun `weapons.py OUT gargoyle-halberd` and `armour.py` (restore the unchanged sprites with `git checkout`).
- **Ambience:** quiet loops under the pages: crackle at the lit bonfire, wind on the maps, a low drone in boss arenas, the flooded archive dripping. Off by default or its own toggle, so it never fights study.
- **Art redesign:** replace the procedural placeholder sprites through the ASHEN pixel pipeline. Keep file names and sizes.
- **PWA or native app** *(decide)*: still an open question in the plan.
