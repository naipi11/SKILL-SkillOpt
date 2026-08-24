"""Exception types for the portable Skill package workflow."""

from __future__ import annotations

from pathlib import Path


class AgentSkillOptError(Exception):
    """Base exception for the portable package workflow."""


class SpecError(AgentSkillOptError):
    """Raised when a creation specification is malformed or unsafe."""


class PlanError(AgentSkillOptError):
    """Raised when a specification cannot be rendered into one file tree."""


class ConfirmationError(AgentSkillOptError):
    """Raised when an apply request lacks its exact preview confirmation token."""


class WriteConflictError(AgentSkillOptError):
    """Raised when publication would replace an existing user target."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"输出目录已存在：{path}")


class PublicationError(AgentSkillOptError):
    """Raised when an atomic no-clobber publication cannot be completed."""


class StagingCleanupError(AgentSkillOptError):
    """Raised when a failed apply operation leaves its staging directory behind."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"暂存目录清理失败，残留路径：{path}")
