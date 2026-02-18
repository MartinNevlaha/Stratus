"""Skill registry: discovery, conflict resolution, trigger matching."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from stratus.skills.models import (
    SkillManifest,
    SkillSource,
    SkillValidationError,
)

# Precedence order (lower number = higher precedence)
_SOURCE_PRECEDENCE: dict[str, int] = {
    SkillSource.LOCAL: 0,
    SkillSource.BUILTIN: 1,
    SkillSource.LEARNING: 2,
}


class SkillRegistry:
    _skills_dir: Path
    _agents_dir: Path | None
    _skills: dict[str, SkillManifest]

    def __init__(
        self,
        skills_dir: Path,
        agents_dir: Path | None = None,
    ) -> None:
        self._skills_dir = skills_dir
        self._agents_dir = agents_dir
        self._skills = {}

    def discover(self) -> list[SkillManifest]:
        """Discover all SKILL.md files in immediate subdirectories."""
        self._skills = {}
        if not self._skills_dir.is_dir():
            return []
        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            manifest = self._parse_skill(skill_file)
            if manifest is None:
                continue
            existing = self._skills.get(manifest.name)
            if existing is None:
                self._skills[manifest.name] = manifest
            else:
                self._skills[manifest.name] = self._resolve(existing, manifest)
        return list(self._skills.values())

    def get(self, name: str) -> SkillManifest | None:
        return self._skills.get(name)

    def filter_by_phase(self, phase: str) -> list[SkillManifest]:
        return [s for s in self._skills.values() if s.requires_phase == phase]

    def filter_by_tags(self, tags: list[str]) -> list[SkillManifest]:
        tag_set = set(tags)
        return [s for s in self._skills.values() if tag_set & set(s.tags)]

    def resolve_trigger(self, query: str) -> SkillManifest | None:
        for skill in self._skills.values():
            for pattern in skill.triggers:
                if re.search(pattern, query, re.IGNORECASE):
                    return skill
        return None

    def validate_all(self) -> list[SkillValidationError]:
        errors: list[SkillValidationError] = []
        if not self._agents_dir:
            return errors
        for skill in self._skills.values():
            agent_file = self._agents_dir / f"{skill.agent}.md"
            if not agent_file.exists():
                errors.append(
                    SkillValidationError(
                        skill_name=skill.name,
                        message=(f"Referenced agent '{skill.agent}' not found at {agent_file}"),
                    )
                )
        return errors

    def _parse_skill(self, path: Path) -> SkillManifest | None:
        """Parse SKILL.md with simple key: value frontmatter between --- markers."""
        text = path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(text.encode()).hexdigest()

        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            return None

        frontmatter: dict[str, str] = {}
        body_start = 1
        found_end = False
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                body_start = i + 1
                found_end = True
                break
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")

        if not found_end:
            return None

        name = frontmatter.get("name", "")
        description = frontmatter.get("description", "")
        agent = frontmatter.get("agent", "")
        if not all([name, description, agent]):
            return None

        body = "\n".join(lines[body_start:]).strip()

        return SkillManifest(
            name=name,
            description=description,
            agent=agent,
            context=frontmatter.get("context", "fork"),
            version=frontmatter.get("version") or None,
            requires=_parse_csv(frontmatter.get("requires", "")),
            triggers=_parse_csv(frontmatter.get("triggers", "")),
            priority=int(frontmatter.get("priority", "0")),
            tags=_parse_csv(frontmatter.get("tags", "")),
            requires_phase=frontmatter.get("requires_phase") or None,
            source=frontmatter.get("source", "local"),
            min_framework_version=frontmatter.get("min_framework_version") or None,
            body=body,
            path=str(path),
            content_hash=content_hash,
        )

    def _resolve(self, a: SkillManifest, b: SkillManifest) -> SkillManifest:
        """Resolve name conflict: higher source precedence wins, then priority, then first."""
        a_prec = _SOURCE_PRECEDENCE.get(a.source, 99)
        b_prec = _SOURCE_PRECEDENCE.get(b.source, 99)
        if a_prec != b_prec:
            return a if a_prec < b_prec else b
        if a.priority != b.priority:
            return a if a.priority > b.priority else b
        return a  # First discovered (alphabetical dir order) wins


def _parse_csv(value: str) -> list[str]:
    """Parse comma-separated string into list, filtering empty entries."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]
