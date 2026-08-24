"""Immutable creation-specification and in-memory bundle-plan models."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from agent_skillopt.errors import SpecError
from agent_skillopt.naming import normalize_skill_name

_SEMANTIC_VERSION_PATTERN = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)
_TOP_LEVEL_KEYS = {"name", "description", "body", "output_directory", "version", "resources"}
_RESOURCE_KEYS = {"kind", "filename", "content"}
_RESOURCE_KINDS = {"reference", "script", "asset"}


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """One text resource included with the portable Skill."""

    kind: Literal["reference", "script", "asset"]
    filename: str
    content: str


@dataclass(frozen=True, slots=True)
class SkillSpec:
    """Strict, user-provided data needed to render one portable Skill package."""

    name: str
    description: str
    body: str
    output_directory: Path
    version: str = "0.1.0"
    resources: tuple[ResourceSpec, ...] = ()

    @classmethod
    def from_json(cls, text: str) -> SkillSpec:
        """Parse a single strict JSON creation specification without writing to disk."""
        if not isinstance(text, str):
            raise SpecError("规格必须是 JSON 文本。")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise SpecError("规格必须是一个有效的 JSON 对象。") from error
        if not isinstance(data, dict):
            raise SpecError("规格必须是一个 JSON 对象。")

        unknown_keys = set(data).difference(_TOP_LEVEL_KEYS)
        if unknown_keys:
            raise SpecError("规格包含不支持的字段。")
        required_keys = {"name", "description", "body", "output_directory"}
        if not required_keys.issubset(data):
            raise SpecError("规格缺少必填字段。")

        name = normalize_skill_name(data["name"])
        description = _required_text(data["description"], "description")
        body = _required_text(data["body"], "body")
        if body.startswith("---"):
            raise SpecError("body 不能以 YAML frontmatter 开头。")

        output_value = _required_text(data["output_directory"], "output_directory")
        output_directory = Path(output_value).expanduser().absolute()
        version = data.get("version", "0.1.0")
        if not isinstance(version, str) or not _SEMANTIC_VERSION_PATTERN.fullmatch(version):
            raise SpecError("version 必须是有效的语义化版本。")

        resources = _parse_resources(data.get("resources", []))
        return cls(
            name=name,
            description=description,
            body=body,
            output_directory=output_directory,
            version=version,
            resources=resources,
        )


@dataclass(frozen=True, slots=True)
class PlannedFile:
    """One not-yet-written file in a package plan."""

    relative_path: PurePosixPath
    content: str
    purpose: str


@dataclass(frozen=True, slots=True)
class BundlePlan:
    """A deterministic, write-free rendering of a portable Skill package."""

    output_directory: Path
    files: tuple[PlannedFile, ...]
    confirmation_token: str


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{field} 必须是非空文本。")
    return value


def _parse_resources(value: object) -> tuple[ResourceSpec, ...]:
    if not isinstance(value, list):
        raise SpecError("resources 必须是数组。")

    resources: list[ResourceSpec] = []
    for resource in value:
        if not isinstance(resource, dict) or set(resource) != _RESOURCE_KEYS:
            raise SpecError("每个 resource 必须包含 kind、filename 和 content。")
        kind = resource["kind"]
        filename = resource["filename"]
        content = resource["content"]
        if not isinstance(kind, str) or kind not in _RESOURCE_KINDS:
            raise SpecError("resource kind 必须是 reference、script 或 asset。")
        if not isinstance(filename, str) or not _is_safe_resource_filename(filename):
            raise SpecError("resource filename 不能是绝对路径或包含路径遍历。")
        if not isinstance(content, str) or not content:
            raise SpecError("resource content 必须是非空文本。")
        resources.append(ResourceSpec(kind=kind, filename=filename, content=content))

    return tuple(
        sorted(resources, key=lambda resource: (resource.kind, resource.filename, resource.content))
    )


def _is_safe_resource_filename(value: str) -> bool:
    if "\\" in value or not value or value.startswith("/"):
        return False
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute():
        return False
    return posix_path != PurePosixPath(".") and ".." not in posix_path.parts
