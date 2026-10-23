"""The Architect road's steps, parsed from the Markdown files in hollow/curriculum.

A region is a folder with a README.md (front matter, then its description) and one file per
step. A step file has, in order: `# Title`, a `> **Why this matters for you:**` line, then
`## You should be able to`, `## Lesson`, `## Quiz` and `## Exam questions` sections. Quiz
questions are `### Prompt` headings, options as `- [ ]` lines (the right one `- [x]`), then an
explanation. Parsing is pure: it takes text and returns values, and raises on a broken file.
"""

import re
from dataclasses import dataclass

MIN_QUIZ = 4
"""Quiz questions a step needs before it can be played."""
WHY = "> **Why this matters for you:**"


class CurriculumError(ValueError):
    """A step or region file that does not follow the format."""


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    """`<topic id>#<n>`, stable while the file keeps its order."""
    prompt: str
    options: tuple[str, ...]
    answer: int
    """Index of the right option, as written in the file."""
    explanation: str


@dataclass(frozen=True)
class Topic:
    id: str
    number: int
    title: str
    region: str
    why: str
    abilities: tuple[str, ...]
    lesson: str
    """Markdown; empty while the lesson is unwritten."""
    quiz: tuple[QuizQuestion, ...]
    exam: tuple[str, ...]
    path: str
    """Repo path of the step file, for linking."""

    @property
    def playable(self) -> bool:
        return bool(self.lesson) and len(self.quiz) >= MIN_QUIZ


@dataclass(frozen=True)
class SkillRegion:
    id: str
    number: int
    name: str
    blurb: str
    covers: str
    start: str
    """Where you start in this region."""
    boss: str
    boss_blurb: str
    build: str
    topics: tuple[Topic, ...]

    @property
    def written(self) -> bool:
        """Every step has its lesson and quiz, so the region can be played."""
        return all(t.playable for t in self.topics)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _sections(lines: list[str], level: str) -> dict[str, list[str]]:
    """Lines under each heading of `level` ("## "), keyed by the heading text."""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in lines:
        if line.startswith(level):
            current = out.setdefault(line[len(level) :].strip(), [])
        elif current is not None:
            current.append(line)
    return out


def _items(lines: list[str]) -> tuple[str, ...]:
    return tuple(line[2:].strip() for line in lines if line.startswith("- "))


def _quiz(topic_id: str, lines: list[str], where: str) -> tuple[QuizQuestion, ...]:
    questions = []
    for n, (prompt, body) in enumerate(_sections(lines, "### ").items(), 1):
        options: list[str] = []
        answer = -1
        rest: list[str] = []
        for line in body:
            mark = re.match(r"- \[( |x)\] (.+)", line)
            if mark and not rest:
                if mark.group(1) == "x":
                    if answer >= 0:
                        raise CurriculumError(f"{where}: two right answers in quiz {n}.")
                    answer = len(options)
                options.append(mark.group(2).strip())
            elif line.strip() or rest:
                rest.append(line)
        if len(options) < 2 or answer < 0:
            raise CurriculumError(f"{where}: quiz {n} needs options with one marked [x].")
        explanation = " ".join(line.strip() for line in rest if line.strip())
        questions.append(
            QuizQuestion(f"{topic_id}#{n}", prompt, tuple(options), answer, explanation)
        )
    return tuple(questions)


def parse_topic(text: str, region: str, number: int, path: str) -> Topic:
    lines = text.splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), "")
    if not title:
        raise CurriculumError(f"{path}: no '# Title' line.")
    why = next((line[len(WHY) :].strip() for line in lines if line.startswith(WHY)), "")
    topic_id = slug(title)
    parts = _sections(lines, "## ")
    lesson = "\n".join(parts.get("Lesson", [])).strip()
    return Topic(
        topic_id,
        number,
        title,
        region,
        why,
        _items(parts.get("You should be able to", [])),
        lesson,
        _quiz(topic_id, parts.get("Quiz", []), path),
        _items(parts.get("Exam questions", [])),
        path,
    )


REGION_KEYS = ("id", "name", "covers", "start", "boss", "boss_blurb", "build")


def parse_region(readme: str, number: int, topics: tuple[Topic, ...], path: str) -> SkillRegion:
    match = re.match(r"---\n(.*?)\n---\n(.*)", readme, re.S)
    if not match:
        raise CurriculumError(f"{path}: needs front matter between --- lines.")
    meta = dict(line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line)
    missing = [k for k in REGION_KEYS if not meta.get(k)]
    if missing:
        raise CurriculumError(f"{path}: missing {', '.join(missing)}.")
    body = [line for line in match.group(2).splitlines() if not line.startswith("# ")]
    paragraphs = "\n".join(body).strip().split("\n\n")
    return SkillRegion(
        meta["id"],
        number,
        meta["name"],
        paragraphs[0].strip(),
        meta["covers"],
        meta["start"],
        meta["boss"],
        meta["boss_blurb"],
        meta["build"],
        tuple(t for t in topics if t.region == meta["id"]),
    )
