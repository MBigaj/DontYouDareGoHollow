"""AnkiConnect client: https://foosoft.net/projects/anki-connect/ (add-on code 2055492159)."""

from datetime import datetime
from typing import Any

import httpx

from hollow.application.anki_sync import AnkiUnavailable
from hollow.domain.anki import AnkiReview

API_VERSION = 6


class AnkiConnect:
    def __init__(
        self,
        url: str = "http://127.0.0.1:8765",
        decks: tuple[str, ...] = (),
        timeout: float = 3.0,
        connect_timeout: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self._decks = decks
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
