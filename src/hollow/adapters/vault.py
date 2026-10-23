"""Reads the Obsidian roadmap vault: how many words of your own each note holds.

Every note starts from the same template (Objective, What Is It?, How It Works…). Lines
that appear in many notes are template, so only the rest is counted as your writing.
"""

import re
from collections import Counter
from pathlib import Path

TEMPLATE_MIN_NOTES = 8
"""A line found in at least this many notes is template text."""
WORD = re.compile(r"[\w'\u2019-]+", re.UNICODE)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


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
            own = [
                line
                for line in texts[note]
                if line not in template
                and not line.startswith("# ")
                and line not in ("[ ]", "- [ ]")
            ]
            words[note] = sum(len(WORD.findall(line)) for line in own)
        return words
