"""AnkiConnect client: https://foosoft.net/projects/anki-connect/ (add-on code 2055492159)."""

import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from hollow.application.anki_sync import AnkiUnavailable
from hollow.config import Settings
from hollow.domain.anki import AnkiReview
from hollow.domain.vocabulary import LearnedWord

API_VERSION = 6
BATCH = 200
TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class WordFields:
    """Which note fields hold a word. The defaults fit the Core 2000 (Optimized) deck."""

    written: str = "Vocabulary-Kanji"
    kana: str = "Vocabulary-Kana"
    meaning: str = "Vocabulary-English"
    part_of_speech: str = "Vocabulary-Pos"


def clean(value: str) -> str:
    """Field text without HTML tags, entities or furigana brackets."""
    text = html.unescape(TAG.sub("", value)).replace("\xa0", " ")
    return re.sub(r"\[[^\]]*\]", "", text).strip()


def connect(settings: Settings) -> "AnkiConnect":
    """The AnkiConnect client the settings describe."""
    fields = WordFields(
        settings.anki_word_field,
        settings.anki_kana_field,
        settings.anki_meaning_field,
        settings.anki_pos_field,
    )
    return AnkiConnect(settings.anki_url, settings.anki_deck_names(), fields=fields)


class AnkiConnect:
    def __init__(
        self,
        url: str = "http://127.0.0.1:8765",
        decks: tuple[str, ...] = (),
        timeout: float = 3.0,
        connect_timeout: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        fields: WordFields | None = None,
    ) -> None:
        self._url = url
        self._decks = decks
        self._fields = fields or WordFields()
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=connect_timeout), transport=transport
        )

    def reviews_since(self, after: datetime) -> list[AnkiReview]:
        start_id = int(after.timestamp() * 1000)
        reviews: list[AnkiReview] = []
        for deck in self.decks():
            rows = self._call("cardReviews", deck=deck, startID=start_id)
            # (reviewTime, cardID, usn, buttonPressed, newInterval, previousInterval,
            #  newFactor, reviewDuration, reviewType)
            reviews.extend(
                AnkiReview(
                    review_id=int(row[0]),
                    card_id=int(row[1]),
                    review_type=int(row[8]),
                    last_interval=int(row[5]),
                )
                for row in rows
            )
        return reviews

    def learned_words(self, skip: frozenset[int]) -> list[LearnedWord]:
        """Notes with at least one card that is no longer new, read once each."""
        decks = " OR ".join(f'"deck:{name}"' for name in self.decks())
        if not decks:
            return []
        note_ids: list[int] = self._call("findNotes", query=f"({decks}) -is:new")
        new = [note_id for note_id in note_ids if note_id not in skip]
        words: list[LearnedWord] = []
        f = self._fields
        for start in range(0, len(new), BATCH):
            for note in self._call("notesInfo", notes=new[start : start + BATCH]):
                fields = {name: clean(field["value"]) for name, field in note["fields"].items()}
                written = fields.get(f.written) or fields.get(f.kana, "")
                if not written:
                    continue
                words.append(
                    LearnedWord(
                        note_id=int(note["noteId"]),
                        written=written,
                        kana=fields.get(f.kana, written),
                        meaning=fields.get(f.meaning, ""),
                        part_of_speech=fields.get(f.part_of_speech, ""),
                    )
                )
        return words

    def decks(self) -> tuple[str, ...]:
        """Every deck a sync reads: all of them, or the configured ones with their subdecks.

        AnkiConnect's cardReviews only matches cards sitting directly in the named deck, not
        in its subdecks, so each deck is queried on its own. A card lives in exactly one deck,
        so nothing is counted twice. Only names that exist are returned: AnkiConnect creates a
        deck when asked about a name it does not know.
        """
        names: list[str] = self._call("deckNames")
        if not self._decks:
            return tuple(names)
        return tuple(
            name
            for name in names
            if any(name == wanted or name.startswith(f"{wanted}::") for wanted in self._decks)
        )

    def missing_decks(self) -> tuple[str, ...]:
        """Configured deck names that do not exist in Anki (usually a typo)."""
        names: list[str] = self._call("deckNames")
        return tuple(wanted for wanted in self._decks if wanted not in names)

    def version(self) -> int:
        return int(self._call("version"))

    def _call(self, action: str, **params: Any) -> Any:
        body: dict[str, Any] = {"action": action, "version": API_VERSION}
        if params:
            body["params"] = params
        try:
            response = self._client.post(self._url, json=body)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise AnkiUnavailable(f"Could not reach AnkiConnect at {self._url}") from error
        if not isinstance(payload, dict) or "result" not in payload:
            raise AnkiUnavailable("AnkiConnect returned an unexpected response")
        if payload.get("error"):
            raise AnkiUnavailable(f"AnkiConnect error: {payload['error']}")
        return payload["result"]
