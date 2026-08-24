"""Run the portable bundle validator without importing the surrounding project."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
SEMVER = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
HOSTS = (Path(".codex-plugin/plugin.json"), Path(".claude-plugin/plugin.json"))
MARKETS = (Path(".agents/plugins/marketplace.json"), Path(".claude-plugin/marketplace.json"))
REQUIRED = (
    Path("plugin.json"),
    *HOSTS,
    *MARKETS,
    Path("README.md"),
    Path("tests/validate_bundle.py"),
)


def validate(root: Path) -> list[tuple[str, Path, str]]:
    root = Path(root)
    issues: list[tuple[str, Path, str]] = []
    if not root.is_dir():
        return [("BUNDLE_ROOT_INVALID", root, "bundle root must be a directory")]
    resolved_root = root.resolve()
    for directory, directories, filenames in os.walk(root, followlinks=False):
        for name in sorted([*directories, *filenames]):
            path = Path(directory) / name
            try:
                contained = path.resolve().is_relative_to(resolved_root)
            except OSError:
                contained = False
            if not contained:
                issues.append(
                    ("PATH_OUTSIDE_BUNDLE", path, "resolved path escapes the bundle root")
                )
    present = {relative: (root / relative).is_file() for relative in REQUIRED}
    for relative, exists in present.items():
        if not exists:
            issues.append(
                ("REQUIRED_FILE_MISSING", root / relative, "required bundle file is missing")
            )
    root_manifest = load(root / "plugin.json", issues) if present[Path("plugin.json")] else None
    identity = root_identity(root / "plugin.json", root_manifest, issues)
    if identity is None:
        return issues
    for relative in HOSTS:
        manifest = load(root / relative, issues) if present[relative] else None
        host(root / relative, manifest, identity, issues)
    for relative in MARKETS:
        manifest = load(root / relative, issues) if present[relative] else None
        marketplace(root / relative, manifest, identity["name"], issues)
    skill_tree(root, identity, issues)
    return issues


def load(path: Path, issues: list[tuple[str, Path, str]]) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        issues.append(("MANIFEST_JSON_INVALID", path, "manifest must be a UTF-8 JSON object"))
        return None
    if not isinstance(value, dict):
        issues.append(("MANIFEST_JSON_INVALID", path, "manifest must be a JSON object"))
        return None
    return value


def required_identity(
    path: Path, manifest: dict[str, object], issues: list[tuple[str, Path, str]]
) -> dict[str, str] | None:
    result: dict[str, str] = {}
    for field in ("name", "version", "description"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(("MANIFEST_METADATA_INVALID", path, f"{field} must be non-empty text"))
        else:
            result[field] = value
    if len(result) != 3:
        return None
    if not NAME.fullmatch(result["name"]):
        issues.append(("MANIFEST_NAME_INVALID", path, "name must be lowercase hyphenated text"))
    if not SEMVER.fullmatch(result["version"]):
        issues.append(("MANIFEST_VERSION_INVALID", path, "version must be semantic"))
    return result


def root_identity(
    path: Path, manifest: dict[str, object] | None, issues: list[tuple[str, Path, str]]
) -> dict[str, str] | None:
    if manifest is None:
        return None
    if manifest.get("$schema") != SCHEMA_URL:
        issues.append(("MANIFEST_SCHEMA_INVALID", path, "manifest schema URL is invalid"))
    return required_identity(path, manifest, issues)


def host(
    path: Path,
    manifest: dict[str, object] | None,
    identity: dict[str, str],
    issues: list[tuple[str, Path, str]],
) -> None:
    if manifest is None:
        return
    if required_identity(path, manifest, issues) is not None:
        for field, code in (
            ("name", "MANIFEST_NAME_MISMATCH"),
            ("version", "MANIFEST_VERSION_MISMATCH"),
            ("description", "MANIFEST_DESCRIPTION_MISMATCH"),
        ):
            if manifest.get(field) != identity[field]:
                issues.append((code, path, f"{field} differs from plugin.json"))
        for field in ("repository", "license"):
            if field in manifest and manifest[field] != identity.get(field):
                issues.append(
                    ("MANIFEST_METADATA_MISMATCH", path, f"{field} differs from plugin.json")
                )
    if manifest.get("skills") != ["./skills/"]:
        issues.append(("HOST_SKILLS_PATH_INVALID", path, "skills must be exactly ['./skills/']"))


def marketplace(
    path: Path,
    manifest: dict[str, object] | None,
    expected_name: str,
    issues: list[tuple[str, Path, str]],
) -> None:
    if manifest is None:
        return
    if manifest.get("name") != expected_name:
        issues.append(
            ("MARKETPLACE_NAME_MISMATCH", path, "marketplace name differs from plugin.json")
        )
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        issues.append(("MARKETPLACE_STRUCTURE_INVALID", path, "marketplace needs one plugin entry"))
    elif plugins[0].get("name") != expected_name or plugins[0].get("source") != "./":
        issues.append(
            ("MARKETPLACE_SOURCE_INVALID", path, "plugin must use matching name and './' source")
        )


def skill_tree(root: Path, identity: dict[str, str], issues: list[tuple[str, Path, str]]) -> None:
    skills = root / "skills"
    try:
        directories = [child for child in skills.iterdir() if child.is_dir()]
    except OSError:
        directories = []
    if len(directories) != 1:
        issues.append(
            ("SKILL_DIRECTORY_COUNT_INVALID", skills, "exactly one Skill directory is required")
        )
        return
    directory = directories[0]
    if directory.name != identity["name"]:
        issues.append(("SKILL_NAME_MISMATCH", directory, "Skill directory must match plugin name"))
    skill = directory / "SKILL.md"
    if not skill.is_file():
        issues.append(("SKILL_FILE_MISSING", skill, "SKILL.md is required"))
        return
    try:
        content = skill.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        issues.append(("SKILL_READ_INVALID", skill, "SKILL.md must be UTF-8 text"))
        return
    frontmatter = parse_frontmatter(content)
    if frontmatter is None:
        issues.append(
            ("SKILL_FRONTMATTER_INVALID", skill, "frontmatter must be strict name and description")
        )
    else:
        if frontmatter["name"] != identity["name"]:
            issues.append(
                ("SKILL_NAME_MISMATCH", skill, "frontmatter name differs from plugin name")
            )
        if frontmatter["description"] != identity["description"]:
            issues.append(
                (
                    "SKILL_DESCRIPTION_MISMATCH",
                    skill,
                    "frontmatter description differs from plugin.json",
                )
            )
    if any(marker in content for marker in ("TODO", "TBD", "<skill-name>")):
        issues.append(("SKILL_UNFINISHED_MARKER", skill, "unfinished scaffold marker found"))
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", content):
        target = target.strip().strip("<>").split("#", 1)[0].split("?", 1)[0]
        if target and "://" not in target and not target.startswith("mailto:"):
            if (
                ".." in PurePosixPath(target.replace("\\", "/")).parts
                or ".." in PureWindowsPath(target).parts
            ):
                issues.append(
                    ("SKILL_PATH_TRAVERSAL", skill, "Markdown resource link contains '..'")
                )


def parse_frontmatter(content: str) -> dict[str, str] | None:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    result: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        if key not in {"name", "description"} or key in result or not value.strip():
            return None
        result[key] = value.strip().strip('"')
    return result if set(result) == {"name", "description"} else None


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("usage: validate_bundle.py bundle-root", file=sys.stderr)
        return 2
    issues = validate(Path(arguments[0]))
    if issues:
        for code, path, message in issues:
            print(f"{code} {path}: {message}", file=sys.stderr)
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
