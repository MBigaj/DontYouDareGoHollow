"""The Architect road, written as Markdown in architect/: one folder per region, one file per
step. Loaded once at import; see architect/README.md for the format."""

from pathlib import Path

from hollow.domain.curriculum import CurriculumError, SkillRegion, parse_region, parse_topic

ROOT = Path(__file__).parent / "architect"


def load(root: Path = ROOT) -> tuple[SkillRegion, ...]:
    regions = []
    folders = sorted(p for p in root.iterdir() if p.is_dir() and p.name[:2].isdigit())
    for number, folder in enumerate(folders, 1):
        readme = folder / "README.md"
        if not readme.is_file():
            raise CurriculumError(f"{folder.name} has no README.md.")
        text = readme.read_text(encoding="utf-8")
        region_id = next(
            (line[4:].strip() for line in text.splitlines() if line.startswith("id: ")), ""
        )
        steps = sorted(p for p in folder.glob("*.md") if p.name[:2].isdigit())
        topics = tuple(
            parse_topic(
                step.read_text(encoding="utf-8"),
                region_id,
                n,
                f"src/hollow/curriculum/architect/{folder.name}/{step.name}",
            )
            for n, step in enumerate(steps, 1)
        )
        regions.append(parse_region(text, number, topics, f"{folder.name}/README.md"))
    return tuple(regions)
