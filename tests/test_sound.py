import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.web.app import sounds
from hollow.domain.conjugation import te_form
from tests.conftest import FakeClock
from tests.test_bosses import fields
from tests.test_web_lessons import KANA, hidden, learn, play

HX = {"HX-Request": "true"}
WEB = Path(__file__).parent.parent / "src/hollow/adapters/web"


def cues(page: str) -> list[str]:
    return re.findall(r'data-sfx="([^"]*)"', page)


def known(name: str) -> bool:
    """A sound exists by its name or as _<n> variants (strike_1, strike_2...)."""
    files = sounds()
    return name in files or any(re.fullmatch(rf"{name}_\d+", f) for f in files)


def test_every_cue_the_game_can_send_has_its_sound() -> None:
    sources = [WEB / "app.py", WEB / "static/js/map.js", *WEB.glob("templates/**/*.html")]
    text = "\n".join(p.read_text(encoding="utf-8") for p in sources)
    used = set()
    for cue in re.findall(r'sfx="([^"{]+)"', text):  # sfx="souls bonfire" in app.py
        used.update(cue.split())
    for words in re.findall(r'"(?:start|hit|miss|estus|phase|won|died)": "([^"]+)"', text):
        used.update(words.split())  # the fight's beat-to-sound table
    used.update(re.findall(r"'(right|wrong)'", text))
    used.update(re.findall(r'hollowSound\("(\w+)"\)', text))
    used.update(re.findall(r'data-sfx="(\w+)\{\{', text))  # data-sfx="souls{{ ' drop' ... }}"
    used.update(re.findall(r"\{\{ ' (\w+)' if", text))
    assert {"bonfire", "souls", "drop", "strike", "felled", "died", "step", "right"} <= used
    assert [name for name in sorted(used) if not known(name)] == []


def test_the_page_lists_its_sounds_and_a_hidden_toggle(client: TestClient) -> None:
    page = client.get("/").text
    found = re.search(r'<script type="application/json" id="sounds">(.*?)</script>', page, re.S)
    assert found
    listed = json.loads(found[1])
    assert listed == sounds() and "felled" in listed
    assert all(url.startswith("/static/sounds/") and "?v=" in url for url in listed.values())
    assert re.search(r"<button[^>]*data-sound-toggle[^>]*hidden>", page)


def test_actions_name_their_sounds(client: TestClient) -> None:
    assert cues(client.post("/light", headers=HX).text) == ["bonfire"]
    first = client.post("/log", data={"kind": "dev_study", "quantity": "10"}, headers=HX).text
    assert cues(first) == ["souls"]  # /light already lit today
    page = client.post("/blacksmith/equip", data={"weapon": "rusted-katana"}, headers=HX).text
    assert cues(page) == ["equip"]


def test_logging_that_lights_the_bonfire_sounds_it(client: TestClient) -> None:
    page = client.post("/log", data={"kind": "dev_study", "quantity": "10"}, headers=HX).text
    assert cues(page) == ["souls bonfire"]
    page = client.post("/log", data={"kind": "dev_study", "quantity": "10"}, headers=HX).text
    assert cues(page) == ["souls"]


def test_lessons_sound_each_answer_and_the_result(
    client: TestClient, store: SqlEventStore, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("hollow.application.lessons.SystemRandom.random", lambda self: 0.0)
    learn(store, clock)
    form = hidden(client.get("/lessons/te-ru").text)
    verb = form["q"][0]
    for answer, cue in ((te_form(verb, KANA[verb]).written, "right"), ("ちがう", "wrong")):
        page = client.post("/lessons/te-ru/answer", data={**form, "answer": answer}, headers=HX)
        assert cues(page.text) == [cue]
    assert cues(play(client, "te-ru")) == ["souls drop"]  # the roll is pinned to drop


def test_fights_sound_each_beat(client: TestClient, store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    assert "data-sfx" not in client.get("/boss/te-warden").text  # the gate is quiet
    page = client.post("/boss/te-warden/enter", headers=HX).text
    assert cues(page) == ["fog"]
    page = client.post(
        "/boss/te-warden/answer", data={**fields(page), "answer": "x"}, headers=HX
    ).text
    assert cues(page) == ["hurt"]
    page = client.post(
        "/boss/te-warden/estus", data={"attempt": fields(page)["attempt"]}, headers=HX
    ).text
    assert cues(page) == ["estus"]
