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
        url: str = "http://localhost:8765",
        decks: tuple[str, ...] = (),
        timeout: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self._decks = decks
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def reviews_since(self, after: datetime) -> list[AnkiReview]:
        start_id = int(after.timestamp() * 1000)
        reviews: list[AnkiReview] = []
        for deck in self._decks or self._top_level_decks():
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

    def version(self) -> int:
        return int(self._call("version"))

    def _top_level_decks(self) -> list[str]:
        """Child decks are included in their parent's reviews, so only query the roots."""
        names: list[str] = self._call("deckNames")
        return [name for name in names if "::" not in name]

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
