"""Portable Skill naming rules."""

from __future__ import annotations

import re

from agent_skillopt.errors import SpecError

_SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def normalize_skill_name(value: str) -> str:
    """Validate and return an already-normalized portable Skill name."""
    if not isinstance(value, str) or not _SKILL_NAME_PATTERN.fullmatch(value):
        raise SpecError(
            "Skill 名称只能使用小写字母、数字和连字符 "
            "(lowercase letters, digits, and hyphens)。"
        )
    return value
