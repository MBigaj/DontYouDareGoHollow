"""Imports how much you have written in each roadmap note, for the Learn gate."""

from typing import Protocol

from hollow.application.ports import Clock, EventStore, next_moment
from hollow.domain.architect import LEARN_WORDS, TOPICS
from hollow.domain.events import NoteWritten

STEP = 20
"""Record a note again only when it grew by this many words (or crossed the Learn mark)."""


class NoteSource(Protocol):
    def available(self) -> bool: ...

    def own_words(self, notes: list[str]) -> dict[str, int]: ...


class VaultSync:
    def __init__(self, store: EventStore, source: NoteSource, clock: Clock) -> None:
        self._store = store
        self._source = source
        self._clock = clock

    def run(self) -> int:
        """Records notes that changed enough. Returns how many were recorded."""
        if not self._source.available():
            return 0
        known: dict[str, int] = {}
        for event in self._store.all():
            if isinstance(event, NoteWritten):
                known[event.topic_id] = event.words
        by_note = {t.note: t.id for t in TOPICS.values() if t.note}
        counts = self._source.own_words(list(by_note))
        recorded = 0
        for note, words in counts.items():
            topic_id = by_note[note]
            before = known.get(topic_id, 0)
            crossed = before < LEARN_WORDS <= words
            if abs(words - before) >= STEP or crossed:
                self._store.append(
                    NoteWritten(next_moment(self._store, self._clock), topic_id, words)
                )
                recorded += 1
        return recorded
