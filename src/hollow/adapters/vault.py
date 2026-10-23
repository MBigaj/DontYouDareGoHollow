"""Reads the Obsidian roadmap vault: how many words of your own each note holds.

Topic notes have a "## My notes" section: only what you write there counts. Lines that
appear in many notes (the template's guidance) are never counted. Notes without the section
fall back to counting every non-template line.
"""

import re
from collections import Counter
from pathlib import Path

TEMPLATE_MIN_NOTES = 8
"""A line found in at least this many notes is template text."""
WORD = re.compile(r"[\w'\u2019-]+", re.UNICODE)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


MY_NOTES = "## my notes"


def _my_notes(lines: list[str]) -> list[str]:
    """The lines of the "## My notes" section, or every line when there is none."""
    lowered = [line.lower() for line in lines]
    if MY_NOTES not in lowered:
        return lines
    start = lowered.index(MY_NOTES) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _boilerplate(line: str) -> bool:
    return line.startswith("# ") or line in ("[ ]", "- [ ]")


class Vault:
    def __init__(self, root: Path) -> None:
        self.root = root

    def available(self) -> bool:
        return self.root.is_dir()

    def own_words(self, notes: list[str]) -> dict[str, int]:
        """Words you wrote in each of `notes` (vault-relative paths); missing notes are skipped."""
        texts = {}
        counts: Counter[str] = Counter()
        for path in self.root.rglob("*.md"):
            if ".obsidian" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.relative_to(self.root).as_posix()
            lines = _lines(text)
            texts[rel] = lines
            counts.update(set(lines))
        template = {line for line, n in counts.items() if n >= TEMPLATE_MIN_NOTES}
        words = {}
        for note in notes:
            if note not in texts:
                continue
            lines = _my_notes(texts[note])
            own = [line for line in lines if line not in template and not _boilerplate(line)]
            words[note] = sum(len(WORD.findall(line)) for line in own)
        return words
