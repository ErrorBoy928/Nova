"""
ai/skills_manager.py

Antigravity-inspired Skills and Customizations System for Nova AI.
Discovers, parses, matches, and injects modular skills defined in SKILL.md files.
Each skill contains YAML frontmatter and detailed instructional guidelines.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

# Frontmatter regex: captures key-value pairs between --- and ---
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


from utils.app_paths import project_root


class SkillsManager:
    """Manages discovery, loading, and runtime matching of Antigravity skills."""

    def __init__(self, root_dir: Path | str | None = None):
        if root_dir is None:
            self.root_dir = project_root() / "skills"
        else:
            self.root_dir = Path(root_dir)

        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._skills_cache: dict[str, dict] = {}
        self.reload_skills()

    def reload_skills(self) -> dict[str, dict]:
        """Scans the skills directory and reloads all valid SKILL.md files."""
        self._skills_cache.clear()

        if not self.root_dir.exists():
            return self._skills_cache

        for item in self.root_dir.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.md"
                if skill_file.is_file():
                    skill_data = self._parse_skill_file(skill_file)
                    if skill_data:
                        self._skills_cache[skill_data["name"]] = skill_data

        log.info(f"Loaded {len(self._skills_cache)} Antigravity skills from {self.root_dir}")
        return self._skills_cache

    def _parse_skill_file(self, path: Path) -> dict | None:
        """Parses a SKILL.md file with YAML frontmatter."""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            log.warning(f"Failed to read skill file {path}: {e}")
            return None

        match = FRONTMATTER_RE.match(content.strip())
        frontmatter_dict = {}
        instructions = content.strip()

        if match:
            fm_text = match.group(1)
            instructions = match.group(2).strip()
            for line in fm_text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter_dict[key.strip().lower()] = val.strip()

        name = frontmatter_dict.get("name") or path.parent.name
        description = frontmatter_dict.get("description", "Custom Antigravity skill.")
        slash_command = frontmatter_dict.get("slash_command", "")
        keywords_str = frontmatter_dict.get("keywords", "")
        keywords = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]

        return {
            "name": name,
            "description": description,
            "slash_command": slash_command,
            "keywords": keywords,
            "path": str(path),
            "directory": str(path.parent),
            "instructions": instructions,
        }

    def list_skills(self) -> list[dict]:
        """Returns all registered skills as a list."""
        return list(self._skills_cache.values())

    def get_skill(self, name: str) -> dict | None:
        """Retrieves a skill by name or slug."""
        name_clean = name.strip().lower()
        if name_clean in self._skills_cache:
            return self._skills_cache[name_clean]
        for skill in self._skills_cache.values():
            if skill["name"].lower() == name_clean:
                return skill
        return None

    def match_skills(self, query: str, limit: int = 2) -> list[dict]:
        """Finds skills matching keywords in the query or matching a slash command."""
        query_lower = query.lower().strip()
        matched: list[tuple[int, dict]] = []

        for skill in self._skills_cache.values():
            score = 0
            if skill["slash_command"] and query_lower.startswith(skill["slash_command"].lower()):
                score += 100

            if skill["name"].lower() in query_lower:
                score += 20

            for kw in skill["keywords"]:
                if kw in query_lower:
                    score += 5

            if score > 0:
                matched.append((score, skill))

        matched.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in matched[:limit]]

    def format_skills_injection(self, skills: list[dict]) -> str:
        """Formats matched skills for injection into LLM system prompt."""
        if not skills:
            return ""

        sections = ["\n[Active Antigravity Skills: Applied Directives]"]
        for skill in skills:
            sections.append(
                f"### Skill: {skill['name']}\n"
                f"Description: {skill['description']}\n"
                f"Instructions:\n{skill['instructions']}\n"
            )
        return "\n".join(sections)

    def create_or_update_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        slash_command: str = "",
        keywords: list[str] | None = None,
    ) -> dict:
        """Creates or updates a skill on disk and reloads cache."""
        slug = re.sub(r"[^\w\-]", "-", name.lower()).strip("-")
        skill_dir = self.root_dir / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        kw_str = ", ".join(keywords) if keywords else ""
        content = (
            f"---\n"
            f"name: {slug}\n"
            f"description: {description}\n"
            f"slash_command: {slash_command}\n"
            f"keywords: {kw_str}\n"
            f"---\n\n"
            f"{instructions}\n"
        )
        skill_file.write_text(content, encoding="utf-8")
        self.reload_skills()
        return self._skills_cache.get(slug, {})


# Global singleton instance
skills_manager = SkillsManager()
