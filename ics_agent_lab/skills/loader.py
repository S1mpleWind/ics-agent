from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path


class SkillLoader:
    """Load skills from SKILL.md files under a directory."""

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self.reload()

    def reload(self) -> None:
        self._skills: dict[str, Skill] = {}

        if not self.skills_dir.exists():
            return

        # Discover every SKILL.md under skills/<name>/SKILL.md and keep the
        # parsed frontmatter plus the full file body.
        for skill_path in sorted(self.skills_dir.glob("*/SKILL.md")):
            try:
                skill = self._load_skill(skill_path)
            except Exception:
                continue
            self._skills[skill.name] = skill

    def descriptions(self) -> str:
        if not getattr(self, "_skills", None):
            return "(no skills available)"

        lines = [f"- {skill.name}: {skill.description}" for skill in self._skills.values()]
        return "\n".join(lines)

    def content(self, name: str) -> str:
        skill = getattr(self, "_skills", {}).get(name)
        if skill is None:
            raise KeyError(f"Unknown skill: {name}")
        return skill.body

    def _load_skill(self, path: Path) -> Skill:
        body = path.read_text(encoding="utf-8")
        name, description = self._parse_frontmatter(body, path)
        return Skill(name=name, description=description, body=body, path=path)

    def _parse_frontmatter(self, body: str, path: Path) -> tuple[str, str]:
        lines = body.splitlines()
        if len(lines) < 3 or lines[0].strip() != "---":
            raise ValueError(f"Missing front matter in {path}")

        end_index = None
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                end_index = index
                break

        if end_index is None:
            raise ValueError(f"Unterminated front matter in {path}")

        frontmatter = "\n".join(lines[1:end_index])
        name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
        description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
        if name_match is None or description_match is None:
            raise ValueError(f"Front matter must contain name and description in {path}")

        return name_match.group(1).strip(), description_match.group(1).strip()
