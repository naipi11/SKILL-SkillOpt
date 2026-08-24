"""Exception types for the portable Skill package workflow."""

from __future__ import annotations


class AgentSkillOptError(Exception):
    """Base exception for the portable package workflow."""


class SpecError(AgentSkillOptError):
    """Raised when a creation specification is malformed or unsafe."""


class PlanError(AgentSkillOptError):
    """Raised when a specification cannot be rendered into one file tree."""
