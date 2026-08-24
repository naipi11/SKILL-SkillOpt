"""Run the portable bundle validator without importing the surrounding project."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

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
ROOT_FIELDS = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
AUTHOR_FIELDS = frozenset({"name", "email", "url"})
OPTIONAL_METADATA_FIELDS = (
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
)
REMOTE_LINK_SCHEMES = frozenset({"ftp", "ftps", "git", "http", "https", "ssh"})
PERCENT_NORMALIZATION_LIMIT = 8
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
UNFINISHED = ("TODO", "TBD", "<skill-name>")


def validate(root: Path) -> list[tuple[str, Path, str]]:
    root = Path(root)
    issues: list[tuple[str, Path, str]] = []
    if not root.is_dir():
        return [("BUNDLE_ROOT_INVALID", root, "bundle root must be a directory")]
    resolved_root = root.resolve()
    unsafe = validate_containment(root, resolved_root, issues)
    present = validate_required(root, resolved_root, unsafe, issues)
    root_manifest = load(root / "plugin.json", issues) if present[Path("plugin.json")] else None
    identity = root_identity(root / "plugin.json", root_manifest, issues)
    for relative in HOSTS:
        manifest = load(root / relative, issues) if present[relative] else None
        host(root / relative, manifest, identity, issues)
    expected_name = identity["name"] if identity is not None else None
    for relative in MARKETS:
        manifest = load(root / relative, issues) if present[relative] else None
        marketplace(root / relative, manifest, expected_name, issues)
    skill_tree(root, resolved_root, unsafe, identity, issues)
    return issues


def validate_containment(
    root: Path, resolved_root: Path, issues: list[tuple[str, Path, str]]
) -> set[Path]:
    unsafe: set[Path] = set()
    for directory, directories, filenames in os.walk(root, followlinks=False):
        directories.sort()
        filenames.sort()
        for name in [*directories, *filenames]:
            path = Path(directory) / name
            if is_link_or_reparse_point(path):
                unsafe.add(path)
                if name in directories:
                    directories.remove(name)
                issues.append(
                    (
                        "PATH_OUTSIDE_BUNDLE",
                        path,
                        "links and reparse points are not accepted in a portable bundle",
                    )
                )
                continue
            if not contained(path, resolved_root):
                unsafe.add(path)
                issues.append(
                    ("PATH_OUTSIDE_BUNDLE", path, "resolved path escapes the bundle root")
                )
    return unsafe


def validate_required(
    root: Path,
    resolved_root: Path,
    unsafe: set[Path],
    issues: list[tuple[str, Path, str]],
) -> dict[Path, bool]:
    present: dict[Path, bool] = {}
    for relative in REQUIRED:
        path = root / relative
        exists = (
            exact_regular_file(root, relative)
            and path not in unsafe
            and contained(path, resolved_root)
        )
        present[relative] = exists
        if not exists:
            issues.append(("REQUIRED_FILE_MISSING", path, "required bundle file is missing"))
    return present


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


def root_identity(
    path: Path, manifest: dict[str, object] | None, issues: list[tuple[str, Path, str]]
) -> dict[str, object] | None:
    if manifest is None:
        return None
    validate_root_fields(path, manifest, issues)
    if manifest.get("$schema") != SCHEMA_URL:
        issues.append(("MANIFEST_SCHEMA_INVALID", path, "manifest schema URL is invalid"))
    identity = required_identity(path, manifest, issues)
    if identity is not None:
        for field in OPTIONAL_METADATA_FIELDS:
            if field in manifest:
                identity[field] = manifest[field]
    return identity


def validate_root_fields(
    path: Path, manifest: dict[str, object], issues: list[tuple[str, Path, str]]
) -> None:
    for field in sorted(set(manifest) - ROOT_FIELDS):
        issues.append(
            ("ROOT_MANIFEST_UNKNOWN_FIELD", path, f"{field} is not an Agent Plugins v1 field")
        )
    for field in ("homepage", "repository", "license"):
        if field in manifest and not isinstance(manifest[field], str):
            issues.append(("ROOT_MANIFEST_OPTIONAL_TYPE_INVALID", path, f"{field} must be text"))
    if "keywords" in manifest and (
        not isinstance(manifest["keywords"], list)
        or not all(isinstance(keyword, str) for keyword in manifest["keywords"])
    ):
        issues.append(
            ("ROOT_MANIFEST_OPTIONAL_TYPE_INVALID", path, "keywords must be a list of text")
        )
    if "author" in manifest:
        author = manifest["author"]
        if not isinstance(author, dict) or any(
            field not in AUTHOR_FIELDS or not isinstance(value, str)
            for field, value in author.items()
        ):
            issues.append(
                ("ROOT_MANIFEST_OPTIONAL_TYPE_INVALID", path, "author must be a text-only object")
            )
    if "extensions" in manifest and (
        not isinstance(manifest["extensions"], dict)
        or not all(isinstance(value, dict) for value in manifest["extensions"].values())
    ):
        issues.append(
            ("ROOT_MANIFEST_OPTIONAL_TYPE_INVALID", path, "extensions must be an object of objects")
        )


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


def host(
    path: Path,
    manifest: dict[str, object] | None,
    identity: dict[str, object] | None,
    issues: list[tuple[str, Path, str]],
) -> None:
    if manifest is None:
        return
    required = required_identity(path, manifest, issues)
    if identity is not None:
        if required is not None:
            compare_required_identity(path, manifest, identity, issues)
        compare_optional_metadata(path, manifest, identity, issues)
    if manifest.get("skills") != ["./skills/"]:
        issues.append(("HOST_SKILLS_PATH_INVALID", path, "skills must be exactly ['./skills/']"))


def compare_required_identity(
    path: Path,
    manifest: dict[str, object],
    identity: dict[str, object],
    issues: list[tuple[str, Path, str]],
) -> None:
    for field, code in (
        ("name", "MANIFEST_NAME_MISMATCH"),
        ("version", "MANIFEST_VERSION_MISMATCH"),
        ("description", "MANIFEST_DESCRIPTION_MISMATCH"),
    ):
        if manifest.get(field) != identity[field]:
            issues.append((code, path, f"{field} differs from plugin.json"))


def compare_optional_metadata(
    path: Path,
    manifest: dict[str, object],
    identity: dict[str, object],
    issues: list[tuple[str, Path, str]],
) -> None:
    for field in OPTIONAL_METADATA_FIELDS:
        if field in manifest and not json_values_equal(manifest[field], identity.get(field)):
            issues.append(("MANIFEST_METADATA_MISMATCH", path, f"{field} differs from plugin.json"))


def marketplace(
    path: Path,
    manifest: dict[str, object] | None,
    expected_name: str | None,
    issues: list[tuple[str, Path, str]],
) -> None:
    if manifest is None:
        return
    if expected_name is not None and manifest.get("name") != expected_name:
        issues.append(
            ("MARKETPLACE_NAME_MISMATCH", path, "marketplace name differs from plugin.json")
        )
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        issues.append(("MARKETPLACE_STRUCTURE_INVALID", path, "marketplace needs one plugin entry"))
        return
    plugin = plugins[0]
    if plugin.get("source") != "./" or (
        expected_name is not None and plugin.get("name") != expected_name
    ):
        issues.append(
            ("MARKETPLACE_SOURCE_INVALID", path, "plugin must use matching name and './' source")
        )


def skill_tree(
    root: Path,
    resolved_root: Path,
    unsafe: set[Path],
    identity: dict[str, object] | None,
    issues: list[tuple[str, Path, str]],
) -> None:
    skills = root / "skills"
    if is_link_or_reparse_point(skills):
        issues.append(
            (
                "SKILL_DIRECTORY_COUNT_INVALID",
                skills,
                "canonical skills directory cannot be a link or reparse point",
            )
        )
        return
    if skills in unsafe:
        return
    if not contained(skills, resolved_root):
        return
    if not exact_regular_directory(root, Path("skills")):
        issues.append(
            (
                "SKILL_DIRECTORY_COUNT_INVALID",
                skills,
                "exactly one canonical skills directory is required",
            )
        )
        return
    try:
        children = sorted(skills.iterdir(), key=lambda child: child.name)
    except OSError:
        children = []
    directories = [
        child
        for child in children
        if not is_link_or_reparse_point(child)
        and child.is_dir()
        and child not in unsafe
        and contained(child, resolved_root)
    ]
    if len(directories) != 1:
        issues.append(
            ("SKILL_DIRECTORY_COUNT_INVALID", skills, "exactly one Skill directory is required")
        )
        return
    directory = directories[0]
    if identity is not None and directory.name != identity["name"]:
        issues.append(("SKILL_NAME_MISMATCH", directory, "Skill directory must match plugin name"))
    skill = directory / "SKILL.md"
    if skill in unsafe:
        return
    if is_link_or_reparse_point(skill):
        issues.append(("SKILL_FILE_MISSING", skill, "SKILL.md cannot be a link or reparse point"))
        return
    if not contained(skill, resolved_root):
        return
    if not exact_regular_file(directory, Path("SKILL.md")):
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
        return
    expected_skill_name = identity["name"] if identity is not None else directory.name
    if frontmatter["name"] != expected_skill_name:
        issues.append(("SKILL_NAME_MISMATCH", skill, "frontmatter name differs from plugin.json"))
    if identity is not None and frontmatter["description"] != identity["description"]:
        issues.append(
            (
                "SKILL_DESCRIPTION_MISMATCH",
                skill,
                "frontmatter description differs from plugin.json",
            )
        )
    if any(marker in content for marker in UNFINISHED):
        issues.append(("SKILL_UNFINISHED_MARKER", skill, "unfinished scaffold marker found"))
    for target in markdown_targets(content):
        if contains_parent_reference(target):
            issues.append(("SKILL_PATH_TRAVERSAL", skill, "Markdown resource link contains '..'"))


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
        if key not in {"name", "description"} or key in result:
            return None
        scalar = parse_scalar(value)
        if scalar is None:
            return None
        result[key] = scalar
    return result if set(result) == {"name", "description"} else None


def parse_scalar(value: str) -> str | None:
    if not value.startswith(" ") or value != value.rstrip() or "\t" in value:
        return None
    scalar = value[1:]
    if not scalar:
        return None
    if scalar.startswith('"'):
        try:
            decoded = json.loads(scalar)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, str) and decoded else None
    if scalar.startswith("'"):
        if not scalar.endswith("'") or len(scalar) < 2:
            return None
        inner = scalar[1:-1]
        if "'" in inner.replace("''", ""):
            return None
        return inner.replace("''", "'") or None
    if scalar[0] in "[{|>&*!#" or " #" in scalar or ": " in scalar:
        return None
    return scalar


def markdown_targets(content: str) -> tuple[str, ...]:
    inline = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", content)
    references = re.findall(r"(?m)^\s*\[[^\]]+\]:\s*(\S+)", content)
    return tuple([*inline, *references])


def contains_parent_reference(target: str) -> bool:
    target = target.strip().strip("<>").split("#", 1)[0].split("?", 1)[0]
    if not target:
        return False
    decoded = normalize_percent_escapes(target)
    if decoded is None:
        return True
    scheme = urlsplit(decoded).scheme.lower()
    if scheme in REMOTE_LINK_SCHEMES or scheme == "mailto":
        return False
    if scheme:
        return True
    posix_path = PurePosixPath(decoded.replace("\\", "/"))
    windows_path = PureWindowsPath(decoded)
    return (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    )


def exact_regular_file(root: Path, relative: Path) -> bool:
    current = root
    for index, component in enumerate(relative.parts):
        try:
            child = next(child for child in current.iterdir() if child.name == component)
        except (OSError, StopIteration):
            return False
        if is_link_or_reparse_point(child):
            return False
        if index == len(relative.parts) - 1:
            return child.is_file()
        if not child.is_dir():
            return False
        current = child
    return False


def exact_regular_directory(root: Path, relative: Path) -> bool:
    current = root
    for index, component in enumerate(relative.parts):
        try:
            child = next(child for child in current.iterdir() if child.name == component)
        except (OSError, StopIteration):
            return False
        if is_link_or_reparse_point(child):
            return False
        if index == len(relative.parts) - 1:
            return child.is_dir()
        if not child.is_dir():
            return False
        current = child
    return False


def contained(path: Path, resolved_root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(resolved_root)
    except OSError:
        return False


def is_link_or_reparse_point(path: Path) -> bool:
    """Reject link indirection without resolving or following the directory entry."""
    try:
        if path.is_symlink():
            return True
    except OSError:
        return False
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            if is_junction():
                return True
        except OSError:
            pass
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def json_values_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            json_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            json_values_equal(left_item, right_item) for left_item, right_item in zip(left, right)
        )
    return left == right


def normalize_percent_escapes(target: str) -> str | None:
    normalized = target
    for _ in range(PERCENT_NORMALIZATION_LIMIT):
        decoded = unquote(normalized)
        if decoded == normalized:
            return normalized
        normalized = decoded
    return normalized if unquote(normalized) == normalized else None


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
