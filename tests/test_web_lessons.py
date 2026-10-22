import re

from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.domain.conjugation import te_form
from hollow.domain.vocabulary import LearnedWord, to_event
from tests.conftest import FakeClock
from tests.test_lessons import DECK_VERBS

HX = {"HX-Request": "true"}
KANA = dict(DECK_VERBS) | {"する": "する"}


def learn(store: SqlEventStore, clock: FakeClock) -> None:
    for n, (written, kana) in enumerate(DECK_VERBS):
        store.append(to_event(LearnedWord(n, written, kana, "meaning", "Verb"), clock.now()))


def hidden(page: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for name, value in re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', page):
        fields.setdefault(name, []).append(value)
    return fields


def play(client: TestClient, lesson: str, wrong: int = 0) -> str:
    page = client.get(f"/lessons/{lesson}").text
    fields = hidden(page)
    questions = fields["q"]
    for i, verb in enumerate(questions):
        right = te_form(verb, KANA[verb]).written
        answer = "ちがう" if i < wrong else right
        page = client.post(
            f"/lessons/{lesson}/answer", data={**fields, "answer": answer}, headers=HX
        ).text
        assert ("正解" in page) is (i >= wrong)
        fields = hidden(page)
        step = "finish" if i == len(questions) - 1 else "next"
        page = client.post(f"/lessons/{lesson}/{step}", data=fields, headers=HX).text
        fields = hidden(page)
    return str(page)


def test_lessons_page_lists_lessons_by_status(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    page = client.get("/lessons").text
    assert "Learn 2 more verbs of this kind in Anki to open it." in page
    learn(store, clock)
    page = client.get("/lessons").text
    assert "17 so far, plus する" in page
    assert 'href="/lessons/te-ru"' in page
    assert 'href="/lessons" aria-current="page"' in page


def test_a_full_lesson_clears_and_lights_the_bonfire(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    page = play(client, "te-ru", wrong=1)
    assert "4 / 5" in page
    assert "Lesson cleared" in page
    assert "+20 souls" in page
    assert "Comes back as a refresher on" in page
    assert "The bonfire is lit for today." in page
    assert "To review" in page

    bonfire = client.get("/").text
    assert "Lesson · る-verbs: 4/5" in bonfire
    assert "The bonfire is lit for today." in bonfire

    clock.advance(days=1)
    assert "1 refresher due today" in client.get("/").text
    assert 'class="badge">1<' in client.get("/lessons").text


def test_a_failed_run_still_pays(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    page = play(client, "te-shite", wrong=3)
    assert "2 / 5" in page
    assert "Not cleared yet" in page
    assert "+10 souls" in page


def test_feedback_explains_look_alike_verbs(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    fields = hidden(client.get("/lessons/te-tsu").text)
    fields["q"] = ["帰る"]
    page = client.post("/lessons/te-tsu/answer", data={**fields, "answer": "かえて"}, headers=HX)
    assert "帰る looks like a る-verb but is not" in page.text
    assert "You wrote" in page.text


def test_bad_runs_are_refused(client: TestClient, store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    page = client.get("/lessons/nope").text
    assert "There is no lesson called nope." in page
    fields = hidden(client.get("/lessons/te-ru").text)
    one = {"run": fields["run"], "q": fields["q"][:1]}
    assert (
        client.post("/lessons/te-ru/answer", data={**one, "q": ["書く"], "answer": "x"}).status_code
        == 422
    )
    assert client.post("/lessons/te-ru/finish", data=one).status_code == 422
    done = {**one, "a": ["たべて"]}
    assert client.post("/lessons/te-ru/next", data=done).status_code == 422
    assert client.post("/lessons/te-ru/answer", data={**done, "answer": "x"}).status_code == 422


def test_lessons_work_without_javascript(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    page = client.get("/lessons/te-ru").text
    assert "<!doctype html>" in page.lower()
    fields = hidden(page)
    answered = client.post("/lessons/te-ru/answer", data={**fields, "answer": "たべて"})
    assert "<!doctype html>" in answered.text.lower()


def test_kanji_show_their_reading_as_a_tooltip(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    listing = client.get("/lessons").text
    assert 'data-reading="たべる">食べる' in listing
    page = client.get("/lessons/te-ru").text
    assert 'class="ja" tabindex="0" data-reading=' in page
    assert "Hover or tap the word for its reading" in page
