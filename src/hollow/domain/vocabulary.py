"""Words you have learned in Anki, and the verbs among them that drills use."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from hollow.domain.conjugation import NotAVerb, Verb, classify
from hollow.domain.events import Event, WordLearned

WORDS_NAMESPACE = UUID("d2b7a1e4-5c3f-4e9a-8b16-0a7c9e3f5d21")
SURU = Verb("する", "する", "do")
"""Always drillable: する is grammar, not vocabulary."""


@dataclass(frozen=True)
class LearnedWord:
    note_id: int
    written: str
    kana: str
    meaning: str
    part_of_speech: str


def to_event(word: LearnedWord, at: datetime) -> WordLearned:
    return WordLearned(
        occurred_at=at,
        note_id=word.note_id,
        written=word.written,
        kana=word.kana,
        meaning=word.meaning,
        part_of_speech=word.part_of_speech,
        id=uuid5(WORDS_NAMESPACE, str(word.note_id)),
    )


def known_verbs(events: Iterable[Event]) -> list[Verb]:
    """Verbs from your learned words, plus する, in the order you learned them.

    "Verbal Noun" entries (勉強) become する verbs (勉強する).
    """
    verbs: dict[str, Verb] = {}
    for event in events:
        if not isinstance(event, WordLearned):
            continue
        pos = set(re.findall(r"[a-z]+", event.part_of_speech.lower()))
        written, kana = event.written, event.kana
        if {"verbal", "noun"} <= pos:
            written, kana = written + "する", kana + "する"
        elif "verb" not in pos:  # whole words, so "Adverb" is not a verb
            continue
        try:
            classify(written, kana)
        except NotAVerb:
            continue
        verbs.setdefault(written, Verb(written, kana, event.meaning))
    verbs.setdefault(SURU.written, SURU)
    return list(verbs.values())
