import json
from datetime import UTC, datetime
from typing import Any

import httpx

from hollow.adapters.anki_connect import AnkiConnect, WordFields, clean
from hollow.adapters.db.store import SqlEventStore
from hollow.application.anki_sync import AnkiSync
from hollow.domain.events import Event, WordLearned
from hollow.domain.vocabulary import LearnedWord, known_verbs, to_event
from tests.conftest import FakeClock
from tests.test_anki import CAL, FakeAnki

NOW = datetime(2026, 10, 23, 10, tzinfo=UTC)


def note(note_id: int, kanji: str, kana: str, english: str, pos: str) -> dict[str, Any]:
    values = {
        "Vocabulary-Kanji": kanji,
        "Vocabulary-Kana": kana,
        "Vocabulary-English": english,
        "Vocabulary-Pos": pos,
        "Expression": "<b>ignored</b>",
    }
    return {
        "noteId": note_id,
        "fields": {name: {"value": v, "order": i} for i, (name, v) in enumerate(values.items())},
    }


NOTES = {
    144: note(144, "食べる", "たべる", "eat", "Verb"),
    103: note(103, "上手", "じょうず", "skilled,&nbsp;good", "Adjectival Noun"),
    72: note(72, "<b>帰る</b>", "かえる", "return, go back", "Verb"),
}


def server(calls: list[dict[str, Any]]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        result: Any = None
        if body["action"] == "deckNames":
            result = ["Default", "Core 2000"]
        elif body["action"] == "findNotes":
            result = list(NOTES)
        elif body["action"] == "notesInfo":
            result = [NOTES[n] for n in body["params"]["notes"]]
        return httpx.Response(200, json={"result": result, "error": None})

    return httpx.MockTransport(handle)


def test_adapter_reads_learned_notes_once_each() -> None:
    calls: list[dict[str, Any]] = []
    anki = AnkiConnect(decks=("Core 2000",), transport=server(calls))

    words = anki.learned_words(skip=frozenset({144}))

    assert words == [
        LearnedWord(103, "上手", "じょうず", "skilled, good", "Adjectival Noun"),
        LearnedWord(72, "帰る", "かえる", "return, go back", "Verb"),
    ]
    find = next(c for c in calls if c["action"] == "findNotes")
    assert find["params"]["query"] == '("deck:Core 2000") -is:new'
    info = next(c for c in calls if c["action"] == "notesInfo")
    assert info["params"]["notes"] == [103, 72]


def test_adapter_skips_notes_without_the_word_field() -> None:
    anki = AnkiConnect(transport=server([]), fields=WordFields(written="Front", kana="Back"))
    assert anki.learned_words(skip=frozenset()) == []


def test_no_decks_means_no_query() -> None:
    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": [], "error": None})

    assert AnkiConnect(transport=httpx.MockTransport(empty)).learned_words(frozenset()) == []


def test_field_text_is_cleaned() -> None:
    assert clean("<b>帰る</b>") == "帰る"
    assert clean("一[ひと]つ") == "一つ"
    assert clean("skilled,&nbsp;good") == "skilled, good"


def test_sync_imports_each_word_once(store: SqlEventStore, clock: FakeClock) -> None:
    anki = FakeAnki(words=[LearnedWord(144, "食べる", "たべる", "eat", "Verb")])
    sync = AnkiSync(store, anki, clock, CAL)
    assert sync.run().words == 1
    assert sync.run().words == 0
    [event] = store.all()
    assert isinstance(event, WordLearned) and event.written == "食べる"


def test_known_verbs_are_verbs_and_verbal_nouns_plus_suru() -> None:
    words = [
        LearnedWord(1, "食べる", "たべる", "eat", "Verb"),
        LearnedWord(2, "上手", "じょうず", "skilled", "Adjectival Noun"),
        LearnedWord(3, "勉強", "べんきょう", "study", "Verbal Noun"),
        LearnedWord(4, "ある", "", "broken", "Verb"),
        LearnedWord(6, "もう", "もう", "already", "Adverb"),
        LearnedWord(5, "食べる", "たべる", "eat (again)", "Verb"),
    ]
    events: list[Event] = [to_event(w, NOW) for w in words]
    assert [v.written for v in known_verbs(events)] == ["食べる", "勉強する", "する"]


def test_words_round_trip_through_the_store(store: SqlEventStore) -> None:
    event = to_event(LearnedWord(7, "読む", "よむ", "read", "Verb"), NOW)
    store.append(event)
    assert store.all() == [event]


def test_words_reject_bad_input() -> None:
    import pytest

    with pytest.raises(ValueError, match="empty"):
        WordLearned(NOW, 1, " ", "", "", "Verb")
    with pytest.raises(ValueError, match="timezone"):
        WordLearned(datetime(2026, 10, 23), 1, "本", "ほん", "book", "Noun")
