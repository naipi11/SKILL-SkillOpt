"""Pure-stdlib rendering of portable Skill bundle previews."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath

from agent_skillopt.errors import PlanError
from agent_skillopt.models import BundlePlan, PlannedFile, ResourceSpec, SkillSpec

_RESOURCE_DIRECTORIES = {"reference": "references", "script": "scripts", "asset": "assets"}
_VALIDATOR_CONTENT = '''"""Offline validator entry point reserved for the generated bundle."""

from __future__ import annotations


def main() -> int:
    """Return success until full offline validation is added in a later task."""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_plan(spec: SkillSpec) -> BundlePlan:
    """Render a complete, deterministic package tree in memory and perform no writes."""
    files = [
        _planned_json("plugin.json", _root_manifest(spec), "portable root manifest"),
        _planned_json(
            ".codex-plugin/plugin.json", _host_manifest(spec), "Codex plugin manifest"
        ),
        _planned_json(
            ".agents/plugins/marketplace.json", _marketplace_manifest(spec), "Codex marketplace"
        ),
        _planned_json(
            ".claude-plugin/plugin.json", _host_manifest(spec), "Claude plugin manifest"
        ),
        _planned_json(
            ".claude-plugin/marketplace.json", _marketplace_manifest(spec), "Claude marketplace"
        ),
        PlannedFile(
            PurePosixPath("skills") / spec.name / "SKILL.md",
            _skill_content(spec),
            "canonical Skill instructions",
        ),
        PlannedFile(PurePosixPath("README.md"), _readme_content(spec), "package README"),
        PlannedFile(
            PurePosixPath("tests/validate_bundle.py"),
            _VALIDATOR_CONTENT,
            "offline bundle validator",
        ),
    ]
    files.extend(_resource_file(resource) for resource in spec.resources)
    ordered_files = tuple(sorted(files, key=lambda file: file.relative_path.as_posix()))
    _assert_no_duplicate_paths(ordered_files)
    return BundlePlan(
        output_directory=spec.output_directory,
        files=ordered_files,
        confirmation_token=_confirmation_token(spec),
    )


def render_preview(plan: BundlePlan) -> dict[str, object]:
    """Return JSON-serializable, content-free plan information for a preview response."""
    return {
        "output_directory": str(plan.output_directory),
        "confirmation_token": plan.confirmation_token,
        "files": [
            {"path": file.relative_path.as_posix(), "purpose": file.purpose} for file in plan.files
        ],
    }


def _planned_json(path: str, content: dict[str, object], purpose: str) -> PlannedFile:
    return PlannedFile(
        relative_path=PurePosixPath(path),
        content=json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        purpose=purpose,
    )


def _root_manifest(spec: SkillSpec) -> dict[str, object]:
    return {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "description": spec.description,
        "name": spec.name,
        "version": spec.version,
    }


def _host_manifest(spec: SkillSpec) -> dict[str, object]:
    return {
        "description": spec.description,
        "name": spec.name,
        "skills": ["./skills/"],
        "version": spec.version,
    }


def _marketplace_manifest(spec: SkillSpec) -> dict[str, object]:
    return {
        "name": spec.name,
        "plugins": [{"name": spec.name, "source": "./"}],
    }


def _skill_content(spec: SkillSpec) -> str:
    lines = [
        "---",
        f"name: {spec.name}",
        f"description: {json.dumps(spec.description)}",
        "---",
        "",
        spec.body,
    ]
    if spec.resources:
        lines.extend(["", "## Resources", ""])
        for resource in spec.resources:
            directory = _RESOURCE_DIRECTORIES[resource.kind]
            lines.append(f"- [{resource.filename}]({directory}/{resource.filename})")
    return "\n".join(lines) + "\n"


def _readme_content(spec: SkillSpec) -> str:
    return f"# {spec.name}\n\n{spec.description}\n"


def _resource_file(resource: ResourceSpec) -> PlannedFile:
    directory = _RESOURCE_DIRECTORIES[resource.kind]
    return PlannedFile(
        relative_path=PurePosixPath(directory) / resource.filename,
        content=resource.content,
        purpose=f"{resource.kind} resource",
    )


def _assert_no_duplicate_paths(files: tuple[PlannedFile, ...]) -> None:
    paths = [file.relative_path.as_posix() for file in files]
    if len(paths) != len(set(paths)):
        raise PlanError("生成的文件路径重复。")


def _confirmation_token(spec: SkillSpec) -> str:
    payload = {
        "output_directory": str(spec.output_directory),
        "spec": {
            "body": spec.body,
            "description": spec.description,
            "name": spec.name,
            "resources": [
                {"content": resource.content, "filename": resource.filename, "kind": resource.kind}
                for resource in spec.resources
            ],
            "version": spec.version,
        },
    }
    canonical_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]
