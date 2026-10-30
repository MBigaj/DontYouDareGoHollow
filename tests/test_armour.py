from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.application.blacksmith import Blacksmith, BlacksmithError
from hollow.application.fights import FightService
from hollow.application.lessons import LessonService
from hollow.domain.armory import (
    ARMOUR,
    BOSS_ARMOUR,
    DROP_CHANCE,
    EFFECTS,
    Effect,
    lesson_drop,
)
from hollow.domain.bosses import WARDEN
from hollow.domain.events import (
    ArmourBought,
    ArmourEquipped,
    ArmourRemoved,
    Event,
    FightAction,
    FightStarted,
    FightTurn,
    Material,
    Slot,
    StatLevelled,
)
from hollow.domain.progression import MIN_MISTAKE_COST, Stat
from tests.conftest import FakeClock
from tests.test_armory import earn, fell_the_warden, state
from tests.test_web_lessons import learn
from tests.test_world import CAL

# --- rules --------------------------------------------------------------------


def test_one_piece_per_slot_with_an_effect_each_and_one_for_sale() -> None:
    assert {a.slot for a in ARMOUR.values()} == set(Slot)
    assert {a.effect for a in ARMOUR.values()} == set(Effect) == set(EFFECTS)
    assert [a.id for a in ARMOUR.values() if a.price] == ["wanderer-hood"]
    assert all(ARMOUR[a].price == 0 for a in BOSS_ARMOUR.values())


def test_you_start_with_no_armour(store: SqlEventStore, clock: FakeClock) -> None:
    world = state(store, clock)
    assert world.armory.armour == set() and world.armory.worn == {}
    assert (world.max_hp, world.mistake_cost, world.estus) == (100, 35, 2)


def test_felled_bosses_drop_their_armour(store: SqlEventStore, clock: FakeClock) -> None:
    fell_the_warden(store, clock)
    arm = state(store, clock).armory
    assert arm.owns_armour("warden-pauldrons") and arm.worn == {}


def test_the_prospector_chance_is_added_and_capped() -> None:
    def drops(roll: float, bonus: float) -> bool:
        return lesson_drop(False, False, 10, 10, 0, 0, roll, bonus) is not None

    base = DROP_CHANCE[(False, True)]
    assert not drops(base + 0.1, 0.0)
    assert drops(base + 0.1, 0.15)
    assert lesson_drop(True, False, 10, 10, 0, 0, 0.99, 0.15) is not None  # 1.0, capped
    assert lesson_drop(False, True, 10, 10, 0, 0, 0.0, 0.15) is None  # practice never drops


# --- effects --------------------------------------------------------------------


def wear(store: SqlEventStore, clock: FakeClock, *ids: str) -> None:
    for armour_id in ids:
        clock.advance(seconds=1)
        store.append(ArmourBought(clock.now(), armour_id, 0))
        clock.advance(seconds=1)
        store.append(ArmourEquipped(clock.now(), armour_id))


def test_each_worn_piece_does_what_it_says(store: SqlEventStore, clock: FakeClock) -> None:
    wear(store, clock, *ARMOUR)
    world = state(store, clock)
    assert (world.max_hp, world.mistake_cost, world.estus) == (120, 30, 3)
    assert world.armory.drop_bonus == 0.15


def test_the_bulwark_never_goes_below_the_floor(store: SqlEventStore, clock: FakeClock) -> None:
    for _ in range(14):
        store.append(StatLevelled(clock.now(), Stat.ENDURANCE, 0))
    wear(store, clock, "warden-pauldrons")
    assert state(store, clock).mistake_cost == MIN_MISTAKE_COST


def test_owned_but_not_worn_does_nothing(store: SqlEventStore, clock: FakeClock) -> None:
    store.append(ArmourBought(clock.now(), "golem-gauntlets", 0))
    assert state(store, clock).estus == 2


def test_a_fight_starts_with_what_you_wear(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    wear(store, clock, "golem-gauntlets", "wanderer-hood")
    view = FightService(store, clock, CAL).enter(WARDEN.id)
    attempt = view.attempt
    assert attempt is not None
    assert (attempt.estus, attempt.flasks, attempt.max_hp) == (3, 3, 120)


def test_taking_armour_off_later_never_rewrites_a_fight(
    store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    wear(store, clock, "golem-gauntlets")
    started = FightService(store, clock, CAL).enter(WARDEN.id).attempt
    assert started is not None
    clock.advance(seconds=1)
    store.append(ArmourRemoved(clock.now(), Slot.ARMS))
    for action, correct in ((FightAction.ANSWER, False), (FightAction.ESTUS, False)):
        clock.advance(seconds=1)
        store.append(FightTurn(clock.now(), started.id, action, correct))
    current = state(store, clock).bosses[WARDEN.id].current
    assert current is not None and (current.estus, current.flasks) == (2, 3)


def test_old_fights_keep_two_flasks(store: SqlEventStore, clock: FakeClock) -> None:
    store.append(FightStarted(clock.now(), WARDEN.id, 1, 100, 35, 10))
    current = state(store, clock).bosses[WARDEN.id].current
    assert current is not None and (current.estus, current.flasks) == (2, 2)


def test_greaves_make_lessons_drop_more(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    service = LessonService(store, clock, CAL)
    run = service.start("te-ru")
    roll = DROP_CHANCE[(False, True)] + 0.05
    _, drop, _ = service.finish(run, [q.te_form.kana for q in run.questions], roll=roll)
    assert drop is None
    wear(store, clock, "wyrm-greaves")
    run = service.start("te-tsu")
    _, drop, _ = service.finish(run, [q.te_form.kana for q in run.questions], roll=roll)
    assert drop is Material.SHARD


# --- the blacksmith -------------------------------------------------------------


def test_buy_wear_swap_and_take_off(store: SqlEventStore, clock: FakeClock) -> None:
    earn(store, clock, 2500)
    smith = Blacksmith(store, clock, CAL)
    world = smith.buy_armour("wanderer-hood")
    assert world.souls == 500 and world.armory.owns_armour("wanderer-hood")
    world = smith.wear("wanderer-hood")
    assert world.armory.worn == {Slot.HEAD: "wanderer-hood"}
    world = smith.take_off(Slot.HEAD)
    assert world.armory.worn == {}


def test_events_for_armour_you_do_not_own_are_ignored(
    store: SqlEventStore, clock: FakeClock
) -> None:
    store.append(ArmourEquipped(clock.now(), "warden-pauldrons"))
    store.append(ArmourBought(clock.now(), "no-such-armour", 0))
    arm = state(store, clock).armory
    assert arm.worn == {} and arm.armour == set()


def test_a_boss_drop_can_be_worn(store: SqlEventStore, clock: FakeClock) -> None:
    fell_the_warden(store, clock)
    clock.advance(seconds=1)
    Blacksmith(store, clock, CAL).wear("warden-pauldrons")
    assert state(store, clock).armory.worn == {Slot.CHEST: "warden-pauldrons"}


@pytest.mark.parametrize(
    ("action", "arg", "message"),
    [
        ("buy_armour", "wanderer-hood", "2,000 more souls"),
        ("buy_armour", "warden-pauldrons", "not for sale"),
        ("buy_armour", "plate-of-havel", "never heard"),
        ("wear", "golem-gauntlets", "do not own"),
        ("take_off", Slot.LEGS, "Nothing is worn on your legs"),
    ],
)
def test_the_blacksmith_refuses_armour_it_cannot_sell_or_fit(
    store: SqlEventStore, clock: FakeClock, action: str, arg: object, message: str
) -> None:
    with pytest.raises(BlacksmithError, match=message):
        getattr(Blacksmith(store, clock, CAL), action)(arg)


def test_buying_twice_and_wearing_twice_are_refused(store: SqlEventStore, clock: FakeClock) -> None:
    earn(store, clock, 5000)
    smith = Blacksmith(store, clock, CAL)
    smith.buy_armour("wanderer-hood")
    with pytest.raises(BlacksmithError, match="already own"):
        smith.buy_armour("wanderer-hood")
    smith.wear("wanderer-hood")
    with pytest.raises(BlacksmithError, match="already wearing"):
        smith.wear("wanderer-hood")


def test_armour_events_round_trip_through_the_store(store: SqlEventStore, clock: FakeClock) -> None:
    events: list[Event] = [
        ArmourBought(clock.now(), "wanderer-hood", 2000),
        ArmourEquipped(clock.now() + timedelta(seconds=1), "wanderer-hood"),
        ArmourRemoved(clock.now() + timedelta(seconds=2), Slot.HEAD),
        FightStarted(clock.now() + timedelta(seconds=3), WARDEN.id, 7, 120, 30, 12, 3),
    ]
    for event in events:
        store.append(event)
    assert list(store.all()) == events


# --- pages --------------------------------------------------------------------

HX = {"HX-Request": "true"}


def test_the_blacksmith_has_sections(client: TestClient) -> None:
    page = client.get("/blacksmith").text
    for anchor in ("weapons", "armour", "rings", "finds"):
        assert f'href="#{anchor}"' in page and f'id="{anchor}"' in page
    assert "Wanderer&#39;s Iron Hood" in page and "Buy · 2,000 souls" in page
    assert "Dropped by The て-form Warden." in page and "Dropped by The Lock Wyrm." in page
    assert "+1 Estus flask in every boss fight" in page


def test_blacksmith_page_buys_wears_and_takes_off_armour(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    earn(store, clock, 2500)
    text = client.post("/blacksmith/armour/buy", data={"armour": "wanderer-hood"}, headers=HX).text
    assert "Bought the Wanderer&#39;s Iron Hood." in text and 'data-sfx="coins"' in text
    text = client.post("/blacksmith/armour/wear", data={"armour": "wanderer-hood"}, headers=HX).text
    assert "You put on the Wanderer&#39;s Iron Hood." in text and "Worn" in text
    character = client.get("/character").text
    assert "+20 max HP in boss fights." in character and "<td>120</td>" in character
    text = client.post("/blacksmith/armour/take-off", data={"slot": "head"}, headers=HX).text
    assert "You took off the Wanderer&#39;s Iron Hood." in text
    text = client.post("/blacksmith/armour/take-off", data={"slot": "head"}, headers=HX).text
    assert "Nothing is worn" in text


def test_armour_without_javascript_and_bad_actions(client: TestClient) -> None:
    bad = client.post(
        "/blacksmith/armour/wear", data={"armour": "wyrm-greaves"}, follow_redirects=False
    )
    assert (bad.status_code, bad.headers["location"]) == (303, "/blacksmith#armour")
    nowhere = client.post("/blacksmith/armour/take-off", data={"slot": "tail"}, headers=HX)
    assert "Nothing is worn" in nowhere.text
    assert client.post("/blacksmith/armour/melt", data={"armour": "x"}).status_code == 404


def test_the_character_page_counts_flasks_from_armour(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    assert "2 × 50 HP" in client.get("/character").text  # noqa: RUF001
    wear(store, clock, "golem-gauntlets")
    page = client.get("/character").text
    assert "3 × 50 HP" in page and "Golem&#39;s Riveted Gauntlets" in page  # noqa: RUF001
