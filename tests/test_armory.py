import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.application.blacksmith import Blacksmith, BlacksmithError
from hollow.application.fights import FightService
from hollow.application.lessons import LessonService
from hollow.domain.activities import ActivityKind, Track
from hollow.domain.armory import (
    MAX_DAMAGE,
    WEAPONS,
    dry_streak,
    lesson_drop,
    upgrade_cost,
)
from hollow.domain.bosses import WARDEN
from hollow.domain.events import (
    Event,
    FightAction,
    FightStarted,
    FightTurn,
    LessonCompleted,
    Material,
    MaterialDropped,
    StudyLogged,
    WeaponBought,
    WeaponEquipped,
    WeaponUpgraded,
)
from hollow.domain.lessons import Run
from hollow.domain.world import WorldState, replay
from tests.conftest import FakeClock
from tests.test_web_lessons import learn
from tests.test_world import CAL

HX = {"HX-Request": "true"}


def state(store: SqlEventStore, clock: FakeClock) -> WorldState:
    return replay(store.all(), CAL, CAL.day_of(clock.now()))


def earn(store: SqlEventStore, clock: FakeClock, souls: int) -> None:
    store.append(StudyLogged(clock.now(), ActivityKind.DEV_STUDY, souls // 2))


def give(store: SqlEventStore, clock: FakeClock, material: Material, count: int) -> None:
    store.append(MaterialDropped(clock.now(), material, count, "test"))


# --- rules --------------------------------------------------------------------


def test_damage_scales_by_level_with_half_value_ahead_of_pace_and_a_cap() -> None:
    katana = WEAPONS["rusted-katana"]
    assert [katana.damage(level, recommended=2) for level in (0, 1, 2, 4, 6, 10)] == [
        10, 11, 12, 13, 14, MAX_DAMAGE,
    ]  # fmt: skip
    assert MAX_DAMAGE == 16  # every boss still needs 60% of its hits
    assert WEAPONS["uchigatana"].damage(0, 2) == 11


@pytest.mark.parametrize(
    ("level", "cost"),
    [
        (1, (200, Material.SHARD, 1)),
        (3, (600, Material.SHARD, 3)),
        (4, (800, Material.LARGE_SHARD, 1)),
        (9, (1800, Material.CHUNK, 3)),
        (10, (2000, Material.SLAB, 1)),
    ],
)
def test_upgrade_costs_follow_the_titanite_tiers(
    level: int, cost: tuple[int, Material, int]
) -> None:
    assert upgrade_cost(level) == cost


@pytest.mark.parametrize(
    ("refresher", "practice", "correct", "step", "dry", "roll", "drop"),
    [
        (True, False, 10, 0, 0, 0.99, Material.SHARD),  # perfect due refresher: always
        (True, False, 10, 2, 0, 0.99, Material.LARGE_SHARD),  # from the 7-day interval
        (True, False, 9, 0, 0, 0.59, Material.SHARD),
        (True, False, 9, 0, 0, 0.61, None),
        (False, False, 10, -1, 0, 0.49, Material.SHARD),
        (False, False, 10, -1, 0, 0.51, None),
        (False, False, 9, -1, 0, 0.24, Material.SHARD),
        (False, False, 9, -1, 4, 0.99, Material.SHARD),  # bad-luck protection
        (False, False, 8, -1, 9, 0.0, None),  # below 90% never drops
        (False, True, 10, 0, 9, 0.0, None),  # practice never drops
    ],
)
def test_lesson_drops(
    refresher: bool,
    practice: bool,
    correct: int,
    step: int,
    dry: int,
    roll: float,
    drop: Material | None,
) -> None:
    assert lesson_drop(refresher, practice, correct, 10, step, dry, roll) is drop


def test_dry_streak_counts_good_runs_since_the_last_drop(
    store: SqlEventStore, clock: FakeClock
) -> None:
    for n, correct in enumerate([10, 10, 5, 10, 9]):
        clock.advance(days=2)
        store.append(LessonCompleted(clock.now(), f"lesson-{n}", correct, 10))
    outcomes = [o for p in state(store, clock).lessons.values() for o in p.history]
    first = min(outcomes, key=lambda o: o.at)
    assert dry_streak(outcomes, set()) == 4
    assert dry_streak(outcomes, {f"lesson:{first.event_id}"}) == 3


# --- replay -------------------------------------------------------------------


def test_you_start_with_a_plain_weapon_per_job(store: SqlEventStore, clock: FakeClock) -> None:
    arm = state(store, clock).armory
    assert arm.equipped == {Track.RONIN: "rusted-katana", Track.ARCHITECT: "pilgrim-shakujo"}
    assert arm.weapon(Track.RONIN)[1] == 0
    assert set(arm.materials.values()) == {0}


def test_the_old_hammers_are_read_as_shakujo(store: SqlEventStore, clock: FakeClock) -> None:
    """The Architect's hammers became staffs; events stored before keep the old ids."""
    store.append(WeaponBought(clock.now(), "smiths-hammer", 1500))
    clock.advance(seconds=1)
    store.append(WeaponEquipped(clock.now(), "smiths-hammer"))
    arm = state(store, clock).armory
    assert arm.equipped[Track.ARCHITECT] == "surveyor-shakujo"
    assert arm.owns("surveyor-shakujo") and arm.owns("pilgrim-shakujo")
    assert not arm.owns("smiths-hammer")


def test_prs_and_new_card_milestones_drop_titanite(store: SqlEventStore, clock: FakeClock) -> None:
    store.append(StudyLogged(clock.now(), ActivityKind.PULL_REQUEST, 2))
    store.append(StudyLogged(clock.now(), ActivityKind.ANKI_NEW_CARDS, 150))
    store.append(StudyLogged(clock.now(), ActivityKind.ANKI_NEW_CARDS, 60))
    mats = state(store, clock).armory.materials
    assert mats[Material.SLAB] == 1  # the very first PR
    assert mats[Material.CHUNK] == 1 + 2  # the second PR, then 100 and 200 new cards


def test_buying_and_reinforcing_spend_souls_and_titanite(
    store: SqlEventStore, clock: FakeClock
) -> None:
    earn(store, clock, 2000)
    give(store, clock, Material.SHARD, 2)
    for event in (
        WeaponBought(clock.now() + timedelta(seconds=1), "uchigatana", 1500),
        WeaponUpgraded(clock.now() + timedelta(seconds=2), "uchigatana", 1, 200, Material.SHARD, 1),
        WeaponEquipped(clock.now() + timedelta(seconds=3), "uchigatana"),
    ):
        store.append(event)
    world = state(store, clock)
    assert world.souls == 300
    assert world.armory.levels["uchigatana"] == 1
    assert world.armory.materials[Material.SHARD] == 1
    assert world.armory.weapon(Track.RONIN)[0].id == "uchigatana"


def test_events_for_weapons_you_do_not_own_are_ignored(
    store: SqlEventStore, clock: FakeClock
) -> None:
    store.append(WeaponUpgraded(clock.now(), "uchigatana", 5, 0, Material.SHARD, 1))
    store.append(WeaponEquipped(clock.now(), "warden-maul"))
    store.append(WeaponBought(clock.now(), "no-such-weapon", 0))
    arm = state(store, clock).armory
    assert not arm.owns("uchigatana") and not arm.owns("no-such-weapon")
    assert arm.equipped[Track.RONIN] == "rusted-katana"


def fell_the_warden(store: SqlEventStore, clock: FakeClock, damage: int = 10) -> None:
    clock.advance(seconds=1)
    started = FightStarted(clock.now(), WARDEN.id, 1, 100, 35, damage)
    store.append(started)
    while not state(store, clock).bosses[WARDEN.id].defeated:
        clock.advance(seconds=1)
        store.append(FightTurn(clock.now(), started.id, FightAction.ANSWER, True))


def test_the_warden_drops_its_maul_and_titanite(store: SqlEventStore, clock: FakeClock) -> None:
    fell_the_warden(store, clock)
    arm = state(store, clock).armory
    assert arm.owns("warden-maul")
    assert (arm.materials[Material.LARGE_SHARD], arm.materials[Material.CHUNK]) == (3, 1)
    assert [d.source for d in arm.drops] == ["boss:te-warden"] * 2


def test_a_stronger_weapon_takes_fewer_hits(store: SqlEventStore, clock: FakeClock) -> None:
    fell_the_warden(store, clock, damage=16)
    hits = state(store, clock).bosses[WARDEN.id].last
    assert hits is not None and hits.hits == 8 + 5  # 120 HP / 16, then 80 HP / 16


def test_soul_siphon_adds_15_percent_to_lesson_souls(
    store: SqlEventStore, clock: FakeClock
) -> None:
    fell_the_warden(store, clock)
    clock.advance(days=1)
    store.append(LessonCompleted(clock.now(), "te-ru", 10, 10))
    plain = state(store, clock).today_lessons[0].souls
    before = state(store, clock).souls
    store.append(WeaponEquipped(clock.now() - timedelta(minutes=1), "warden-maul"))
    assert state(store, clock).souls == before + (plain * 15 + 50) // 100


# --- services -----------------------------------------------------------------


def test_lessons_record_their_drop_once(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    service = LessonService(store, clock, CAL)
    run = service.start("te-ru")
    answers = [q.te_form.kana for q in run.questions]
    outcome, drop, _ = service.finish(run, answers, roll=0.1)
    assert (outcome.run, drop) == (Run.FIRST, Material.SHARD)
    _, again, world = service.finish(run, answers, roll=0.1)
    assert again is Material.SHARD
    assert world.armory.materials[Material.SHARD] == 1
    run = service.start("te-tsu")
    _, none, _ = service.finish(run, [q.te_form.kana for q in run.questions], roll=0.99)
    assert none is None


def test_fights_use_the_equipped_weapon(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    earn(store, clock, 3000)
    give(store, clock, Material.SHARD, 3)
    smith = Blacksmith(store, clock, CAL)
    smith.buy("uchigatana")
    smith.upgrade("uchigatana")
    smith.equip("uchigatana")
    view = FightService(store, clock, CAL).enter(WARDEN.id)
    assert view.attempt is not None and view.attempt.damage == 12


@pytest.mark.parametrize(
    ("action", "weapon", "message"),
    [
        ("buy", "rusted-katana", "already own"),
        ("buy", "warden-maul", "not for sale"),
        ("buy", "uchigatana", "1,500 more souls"),
        ("upgrade", "uchigatana", "do not own"),
        ("upgrade", "rusted-katana", "200 more souls"),
        ("equip", "warden-maul", "do not own"),
        ("equip", "excalibur", "never heard"),
    ],
)
def test_the_blacksmith_refuses_what_you_cannot_afford_or_own(
    store: SqlEventStore, clock: FakeClock, action: str, weapon: str, message: str
) -> None:
    with pytest.raises(BlacksmithError, match=message):
        getattr(Blacksmith(store, clock, CAL), action)(weapon)


def test_reinforcing_needs_titanite_and_stops_at_ten(
    store: SqlEventStore, clock: FakeClock
) -> None:
    earn(store, clock, 30000)
    smith = Blacksmith(store, clock, CAL)
    with pytest.raises(BlacksmithError, match="1 more Titanite Shard"):
        smith.upgrade("rusted-katana")
    store.append(WeaponUpgraded(clock.now(), "rusted-katana", 10, 0, Material.SLAB, 0))
    with pytest.raises(BlacksmithError, match="already at \\+10"):
        smith.upgrade("rusted-katana")


def test_new_events_round_trip_through_the_store(store: SqlEventStore, clock: FakeClock) -> None:
    events: list[Event] = [
        MaterialDropped(clock.now(), Material.CHUNK, 2, "boss:te-warden"),
        WeaponBought(clock.now() + timedelta(seconds=1), "uchigatana", 1500),
        WeaponUpgraded(clock.now() + timedelta(seconds=2), "uchigatana", 1, 200, Material.SHARD, 1),
        WeaponEquipped(clock.now() + timedelta(seconds=3), "uchigatana"),
        FightStarted(clock.now() + timedelta(seconds=4), WARDEN.id, 7, 110, 34, 12),
    ]
    for event in events:
        store.append(event)
    assert list(store.all()) == events
    with pytest.raises(ValueError, match="positive"):
        MaterialDropped(clock.now(), Material.CHUNK, 0, "x")


# --- pages --------------------------------------------------------------------


def test_blacksmith_page_buys_reinforces_and_equips(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    page = client.get("/blacksmith").text
    assert "Rusted Katana</strong> +0" in page and "Equipped" in page
    assert "Dropped by The て-form Warden." in page
    earn(store, clock, 2000)
    give(store, clock, Material.SHARD, 1)
    text = client.post("/blacksmith/buy", data={"weapon": "uchigatana"}, headers=HX).text
    assert "Bought the Uchigatana." in text
    text = client.post("/blacksmith/upgrade", data={"weapon": "uchigatana"}, headers=HX).text
    assert "The Uchigatana is now +1." in text
    text = client.post("/blacksmith/equip", data={"weapon": "uchigatana"}, headers=HX).text
    assert "The Uchigatana is in your hand." in text
    assert "1 × Titanite Shard" in text  # noqa: RUF001
    text = client.post("/blacksmith/upgrade", data={"weapon": "uchigatana"}, headers=HX).text
    assert "You need" in text
    character = client.get("/character").text
    assert (
        "Uchigatana +1" in character
        and "12 damage per hit against The て-form Warden." in character
    )


def test_blacksmith_without_javascript_and_bad_actions(client: TestClient) -> None:
    ok = client.post(
        "/blacksmith/equip", data={"weapon": "pilgrim-shakujo"}, follow_redirects=False
    )
    assert ok.headers["location"] == "/blacksmith"
    bad = client.post("/blacksmith/buy", data={"weapon": "warden-maul"}, follow_redirects=False)
    assert bad.status_code == 303
    assert client.post("/blacksmith/melt", data={"weapon": "x"}).status_code == 404


def test_drop_sources_are_described(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    for source in ("lesson:abc", "boss:te-warden", "boss:gone", "pull-request",
                   "milestone:100-new-cards", "gift"):  # fmt: skip
        clock.advance(seconds=1)
        store.append(MaterialDropped(clock.now(), Material.SHARD, 1, source))
    page = client.get("/blacksmith").text
    found = re.findall(r"Titanite Shard <span class=\"muted\">· ([^<]+)</span>", page)
    assert found == ["gift", "100 new cards", "a merged pull request", "a boss",
                     "The て-form Warden", "a lesson"]  # fmt: skip


def test_lesson_results_show_their_drop(
    client: TestClient, store: SqlEventStore, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_web_lessons import play

    monkeypatch.setattr("hollow.application.lessons.SystemRandom.random", lambda self: 0.0)
    learn(store, clock)
    assert "Titanite Shard dropped" in play(client, "te-ru")


def test_fight_gate_names_your_weapon(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    assert "Your Rusted Katana +0 deals 10 per hit here." in client.get("/boss/te-warden").text


def hero_weapon(page: str) -> str:
    """The weapon drawn in the hero's hand on a page."""
    match = re.search(r'class="hero-fig[^"]*" data-weapon="([\w-]+)"', page)
    assert match, "no hero on the page"
    held = str(match.group(1))
    assert f"sprites/held_{held}.png" in page
    return held


def test_the_hero_holds_the_weapon_of_the_road(client: TestClient, store: SqlEventStore,
                                               clock: FakeClock) -> None:  # fmt: skip
    assert hero_weapon(client.get("/").text) == "rusted-katana"
    assert hero_weapon(client.get("/map/firelink").text) == "rusted-katana"
    assert hero_weapon(client.get("/map/architect/forge").text) == "pilgrim-shakujo"
    assert hero_weapon(client.get("/boss/forge-boss").text) == "pilgrim-shakujo"
    client.cookies.set("hollow_road", "architect")
    assert hero_weapon(client.get("/").text) == "pilgrim-shakujo"
    assert hero_weapon(client.get("/character").text) == "pilgrim-shakujo"
    assert hero_weapon(client.get("/boss/te-warden").text) == "rusted-katana"
    store.append(WeaponBought(clock.now(), "surveyor-shakujo", 1500))
    clock.advance(seconds=1)
    store.append(WeaponEquipped(clock.now(), "surveyor-shakujo"))
    assert hero_weapon(client.get("/").text) == "surveyor-shakujo"
    assert "sprites/hero_hand.png" in client.get("/").text


def test_every_weapon_has_its_art() -> None:
    sprites = Path(__file__).parent.parent / "src/hollow/adapters/web/static/sprites"
    for weapon in WEAPONS.values():
        assert (sprites / weapon.sprite).is_file(), weapon.sprite
        assert (sprites / f"held_{weapon.id}.png").is_file(), weapon.id
