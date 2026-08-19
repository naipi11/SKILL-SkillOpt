"""Public error types for Agent-SkillOpt."""


class ConfigurationError(ValueError):
    """Raised when a project configuration is malformed or unsafe."""


class ExecutionGateError(RuntimeError):
    """Raised when a live execution lacks an explicit safety prerequisite."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code
