"""Pure-stdlib, offline structural validation for portable Skill bundles."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

from agent_skillopt.errors import AgentSkillOptError

_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
_SEMANTIC_VERSION = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)
_SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_HOST_MANIFESTS = (
    Path(".codex-plugin/plugin.json"),
    Path(".claude-plugin/plugin.json"),
)
_MARKETPLACES = (
    Path(".agents/plugins/marketplace.json"),
    Path(".claude-plugin/marketplace.json"),
)
_REQUIRED_FILES = (
    Path("plugin.json"),
    *_HOST_MANIFESTS,
    *_MARKETPLACES,
    Path("README.md"),
    Path("tests/validate_bundle.py"),
)
_UNFINISHED_MARKERS = ("TODO", "TBD", "<skill-name>")
_ROOT_FIELDS = frozenset(
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
_AUTHOR_FIELDS = frozenset({"name", "email", "url"})
_OPTIONAL_METADATA_FIELDS = (
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
)
_REMOTE_LINK_SCHEMES = frozenset({"ftp", "ftps", "git", "http", "https", "ssh"})
_FORBIDDEN_ROOT_RUNTIME_SURFACES = {
    "openclaw.plugin.json": (
        "ROOT_NATIVE_OPENCLAW_FORBIDDEN",
        "native OpenClaw runtime manifest is prohibited in a portable v1 bundle",
    ),
    "plugin.yaml": (
        "ROOT_NATIVE_HERMES_FORBIDDEN",
        "native Hermes manifest is prohibited in a portable v1 bundle",
    ),
    ".mcp.json": (
        "ROOT_MCP_CONFIGURATION_FORBIDDEN",
        "root MCP configuration is prohibited in a portable v1 bundle",
    ),
    "mcp.json": (
        "ROOT_MCP_CONFIGURATION_FORBIDDEN",
        "root MCP configuration is prohibited in a portable v1 bundle",
    ),
    "hooks": (
        "ROOT_HOOK_SURFACE_FORBIDDEN",
        "root hook surface is prohibited in a portable v1 bundle",
    ),
    "hooks.json": (
        "ROOT_HOOK_SURFACE_FORBIDDEN",
        "root hook surface is prohibited in a portable v1 bundle",
    ),
}
_PERCENT_NORMALIZATION_LIMIT = 8
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class _LinkProbeResult(Enum):
    SAFE = "safe"
    LINK = "link"
    MISSING = "missing"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One deterministic, secret-free structural validation failure."""

    code: str
    path: Path
    message: str


class BundleValidationError(AgentSkillOptError):
    """Raised when one package has one or more structural validation failures."""

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__("bundle validation failed: " + ", ".join(issue.code for issue in issues))


def validate_bundle(root: Path) -> tuple[ValidationIssue, ...]:
    """Inspect a bundle without executing its content or using external services."""
    bundle_root = Path(root)
    issues: list[ValidationIssue] = []
    root_probe = _probe_link_or_reparse_point(bundle_root)
    if root_probe is _LinkProbeResult.LINK:
        return (
            _issue(
                "BUNDLE_ROOT_LINK_INVALID",
                bundle_root,
                "bundle root cannot be a link or reparse point",
            ),
        )
    if root_probe is _LinkProbeResult.ERROR:
        return (
            _issue(
                "BUNDLE_ROOT_PROBE_INVALID",
                bundle_root,
                "bundle root metadata cannot be inspected",
            ),
        )
    if root_probe is _LinkProbeResult.MISSING:
        return (_issue("BUNDLE_ROOT_INVALID", bundle_root, "bundle root must be a directory"),)
    if not bundle_root.is_dir():
        return (_issue("BUNDLE_ROOT_INVALID", bundle_root, "bundle root must be a directory"),)

    resolved_root = bundle_root.resolve()
    unsafe_paths = _validate_containment(bundle_root, resolved_root, issues)
    _validate_forbidden_root_runtime_surfaces(bundle_root, issues)
    required = _validate_required_files(bundle_root, unsafe_paths, issues)
    root_manifest = (
        _load_manifest(bundle_root / "plugin.json", issues)
        if required[Path("plugin.json")]
        else None
    )
    root_identity = _validate_root_manifest(bundle_root / "plugin.json", root_manifest, issues)

    host_manifests = {
        path: _load_manifest(bundle_root / path, issues) if required[path] else None
        for path in _HOST_MANIFESTS
    }
    marketplace_manifests = {
        path: _load_manifest(bundle_root / path, issues) if required[path] else None
        for path in _MARKETPLACES
    }
    for path, manifest in host_manifests.items():
        _validate_host_manifest(bundle_root / path, manifest, root_identity, issues)
    expected_name = root_identity["name"] if root_identity is not None else None
    for path, manifest in marketplace_manifests.items():
        _validate_marketplace(bundle_root / path, manifest, expected_name, issues)
    _validate_skill_tree(bundle_root, resolved_root, unsafe_paths, root_identity, issues)
    return tuple(issues)


def assert_valid_bundle(root: Path) -> None:
    """Raise one aggregate exception if ``root`` violates the bundle contract."""
    issues = validate_bundle(root)
    if issues:
        raise BundleValidationError(issues)


def _issue(code: str, path: Path, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message)


def _validate_containment(
    root: Path, resolved_root: Path, issues: list[ValidationIssue]
) -> dict[Path, _LinkProbeResult | None]:
    unsafe_paths: dict[Path, _LinkProbeResult | None] = {}
    for directory, directories, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        directories.sort()
        filenames.sort()
        for name in [*directories, *filenames]:
            candidate = current / name
            probe = _probe_link_or_reparse_point(candidate)
            if probe in {_LinkProbeResult.LINK, _LinkProbeResult.ERROR}:
                if name in directories:
                    directories.remove(name)
                _record_link_probe_rejection(candidate, probe, unsafe_paths, issues)
                continue
            if probe is _LinkProbeResult.MISSING:
                continue
            if not _is_contained(candidate, resolved_root):
                _record_outside_path(candidate, unsafe_paths, issues)
    return unsafe_paths


def _validate_forbidden_root_runtime_surfaces(root: Path, issues: list[ValidationIssue]) -> None:
    """Reject approved root-only native runtime surfaces without restricting Skill resources."""
    try:
        entries = sorted(root.iterdir(), key=lambda entry: (entry.name.casefold(), entry.name))
    except OSError:
        return
    for entry in entries:
        surface = _FORBIDDEN_ROOT_RUNTIME_SURFACES.get(entry.name.casefold())
        if surface is not None:
            code, message = surface
            issues.append(_issue(code, entry, message))


def _validate_required_files(
    root: Path, unsafe_paths: dict[Path, _LinkProbeResult | None], issues: list[ValidationIssue]
) -> dict[Path, bool]:
    found: dict[Path, bool] = {}
    for relative_path in _REQUIRED_FILES:
        path = root / relative_path
        is_file = (
            _has_exact_regular_file(root, relative_path, unsafe_paths, issues)
            and path not in unsafe_paths
            and _is_contained(path, root.resolve())
        )
        found[relative_path] = is_file
        if not is_file:
            issues.append(_issue("REQUIRED_FILE_MISSING", path, "required bundle file is missing"))
    return found


def _load_manifest(path: Path, issues: list[ValidationIssue]) -> dict[str, object] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        issues.append(_issue("MANIFEST_JSON_INVALID", path, "manifest must be a UTF-8 JSON object"))
        return None
    if not isinstance(document, dict):
        issues.append(_issue("MANIFEST_JSON_INVALID", path, "manifest must be a JSON object"))
        return None
    return document


def _validate_root_manifest(
    path: Path, manifest: dict[str, object] | None, issues: list[ValidationIssue]
) -> dict[str, object] | None:
    if manifest is None:
        return None
    _validate_root_fields(path, manifest, issues)
    if manifest.get("$schema") != _SCHEMA_URL:
        issues.append(_issue("MANIFEST_SCHEMA_INVALID", path, "manifest schema URL is invalid"))
    identity = _required_identity(path, manifest, issues)
    if identity is not None:
        for field in _OPTIONAL_METADATA_FIELDS:
            if field in manifest:
                identity[field] = manifest[field]
    return identity


def _validate_root_fields(
    path: Path, manifest: dict[str, object], issues: list[ValidationIssue]
) -> None:
    for field in sorted(set(manifest) - _ROOT_FIELDS):
        issues.append(
            _issue("ROOT_MANIFEST_UNKNOWN_FIELD", path, f"{field} is not an Agent Plugins v1 field")
        )
    for field in ("homepage", "repository", "license"):
        if field in manifest and not isinstance(manifest[field], str):
            issues.append(
                _issue("ROOT_MANIFEST_OPTIONAL_TYPE_INVALID", path, f"{field} must be text")
            )
    if "keywords" in manifest and (
        not isinstance(manifest["keywords"], list)
        or not all(isinstance(keyword, str) for keyword in manifest["keywords"])
    ):
        issues.append(
            _issue("ROOT_MANIFEST_OPTIONAL_TYPE_INVALID", path, "keywords must be a list of text")
        )
    if "author" in manifest:
        author = manifest["author"]
        if not isinstance(author, dict) or any(
            field not in _AUTHOR_FIELDS or not isinstance(value, str)
            for field, value in author.items()
        ):
            issues.append(
                _issue(
                    "ROOT_MANIFEST_OPTIONAL_TYPE_INVALID", path, "author must be a text-only object"
                )
            )
    if "extensions" in manifest and (
        not isinstance(manifest["extensions"], dict)
        or not all(isinstance(value, dict) for value in manifest["extensions"].values())
    ):
        issues.append(
            _issue(
                "ROOT_MANIFEST_OPTIONAL_TYPE_INVALID",
                path,
                "extensions must be an object of objects",
            )
        )


def _required_identity(
    path: Path, manifest: dict[str, object], issues: list[ValidationIssue]
) -> dict[str, str] | None:
    values: dict[str, str] = {}
    for field in ("name", "version", "description"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(
                _issue("MANIFEST_METADATA_INVALID", path, f"{field} must be non-empty text")
            )
            continue
        values[field] = value
    if set(values) != {"name", "version", "description"}:
        return None
    if not _SKILL_NAME.fullmatch(values["name"]):
        issues.append(
            _issue("MANIFEST_NAME_INVALID", path, "name must be lowercase hyphenated text")
        )
    if not _SEMANTIC_VERSION.fullmatch(values["version"]):
        issues.append(_issue("MANIFEST_VERSION_INVALID", path, "version must be semantic"))
    return values


def _validate_host_manifest(
    path: Path,
    manifest: dict[str, object] | None,
    root_identity: dict[str, object] | None,
    issues: list[ValidationIssue],
) -> None:
    if manifest is None:
        return
    identity = _required_identity(path, manifest, issues)
    if root_identity is not None:
        if identity is not None:
            _compare_required_identity(path, manifest, root_identity, issues)
        _compare_optional_metadata(path, manifest, root_identity, issues)
    if manifest.get("skills") != ["./skills/"]:
        issues.append(
            _issue("HOST_SKILLS_PATH_INVALID", path, "skills must be exactly ['./skills/']")
        )


def _compare_required_identity(
    path: Path,
    manifest: dict[str, object],
    root_identity: dict[str, object],
    issues: list[ValidationIssue],
) -> None:
    for field, code in (
        ("name", "MANIFEST_NAME_MISMATCH"),
        ("version", "MANIFEST_VERSION_MISMATCH"),
        ("description", "MANIFEST_DESCRIPTION_MISMATCH"),
    ):
        if manifest.get(field) != root_identity[field]:
            issues.append(_issue(code, path, f"{field} differs from plugin.json"))


def _compare_optional_metadata(
    path: Path,
    manifest: dict[str, object],
    root_identity: dict[str, object],
    issues: list[ValidationIssue],
) -> None:
    for field in _OPTIONAL_METADATA_FIELDS:
        if field in manifest and not _json_values_equal(manifest[field], root_identity.get(field)):
            issues.append(
                _issue("MANIFEST_METADATA_MISMATCH", path, f"{field} differs from plugin.json")
            )


def _validate_marketplace(
    path: Path,
    manifest: dict[str, object] | None,
    expected_name: str | None,
    issues: list[ValidationIssue],
) -> None:
    if manifest is None:
        return
    if expected_name is not None and manifest.get("name") != expected_name:
        issues.append(
            _issue("MARKETPLACE_NAME_MISMATCH", path, "marketplace name differs from plugin.json")
        )
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        issues.append(
            _issue("MARKETPLACE_STRUCTURE_INVALID", path, "marketplace needs one plugin entry")
        )
        return
    plugin = plugins[0]
    if plugin.get("source") != "./" or (
        expected_name is not None and plugin.get("name") != expected_name
    ):
        issues.append(
            _issue(
                "MARKETPLACE_SOURCE_INVALID", path, "plugin must use matching name and './' source"
            )
        )


def _validate_skill_tree(
    root: Path,
    resolved_root: Path,
    unsafe_paths: dict[Path, _LinkProbeResult | None],
    identity: dict[str, object] | None,
    issues: list[ValidationIssue],
) -> None:
    skills_directory = root / "skills"
    if skills_directory in unsafe_paths:
        if unsafe_paths[skills_directory] is _LinkProbeResult.LINK:
            issues.append(
                _issue(
                    "SKILL_DIRECTORY_COUNT_INVALID",
                    skills_directory,
                    "canonical skills directory cannot be a link or reparse point",
                )
            )
        return
    probe = _probe_link_or_reparse_point(skills_directory)
    if probe in {_LinkProbeResult.LINK, _LinkProbeResult.ERROR}:
        _record_link_probe_rejection(skills_directory, probe, unsafe_paths, issues)
        if probe is _LinkProbeResult.ERROR:
            return
        issues.append(
            _issue(
                "SKILL_DIRECTORY_COUNT_INVALID",
                skills_directory,
                "canonical skills directory cannot be a link or reparse point",
            )
        )
        return
    if not _is_contained(skills_directory, resolved_root):
        return
    if not _has_exact_regular_directory(root, Path("skills"), unsafe_paths, issues):
        issues.append(
            _issue(
                "SKILL_DIRECTORY_COUNT_INVALID",
                skills_directory,
                "exactly one canonical skills directory is required",
            )
        )
        return
    try:
        children = sorted(skills_directory.iterdir(), key=lambda child: child.name)
    except OSError:
        children = []
    skill_directories: list[Path] = []
    for child in children:
        if child in unsafe_paths:
            continue
        child_probe = _probe_link_or_reparse_point(child)
        if child_probe in {_LinkProbeResult.LINK, _LinkProbeResult.ERROR}:
            _record_link_probe_rejection(child, child_probe, unsafe_paths, issues)
            continue
        if child_probe is _LinkProbeResult.MISSING:
            continue
        if child.is_dir() and _is_contained(child, resolved_root):
            skill_directories.append(child)
    if len(skill_directories) != 1:
        issues.append(
            _issue(
                "SKILL_DIRECTORY_COUNT_INVALID",
                skills_directory,
                "exactly one Skill directory is required",
            )
        )
        return
    skill_directory = skill_directories[0]
    if identity is not None and skill_directory.name != identity["name"]:
        issues.append(
            _issue("SKILL_NAME_MISMATCH", skill_directory, "Skill directory must match plugin name")
        )
    skill_file = skill_directory / "SKILL.md"
    if skill_file in unsafe_paths:
        return
    skill_probe = _probe_link_or_reparse_point(skill_file)
    if skill_probe in {_LinkProbeResult.LINK, _LinkProbeResult.ERROR}:
        _record_link_probe_rejection(skill_file, skill_probe, unsafe_paths, issues)
        if skill_probe is _LinkProbeResult.LINK:
            issues.append(
                _issue(
                    "SKILL_FILE_MISSING",
                    skill_file,
                    "SKILL.md cannot be a link or reparse point",
                )
            )
        return
    if not _is_contained(skill_file, resolved_root):
        return
    if not _has_exact_regular_file(skill_directory, Path("SKILL.md"), unsafe_paths, issues):
        issues.append(_issue("SKILL_FILE_MISSING", skill_file, "SKILL.md is required"))
        return
    _validate_skill_file(skill_file, identity, issues)


def _validate_skill_file(
    path: Path, identity: dict[str, object] | None, issues: list[ValidationIssue]
) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        issues.append(_issue("SKILL_READ_INVALID", path, "SKILL.md must be UTF-8 text"))
        return
    frontmatter = _parse_frontmatter(content)
    if frontmatter is None:
        issues.append(
            _issue(
                "SKILL_FRONTMATTER_INVALID", path, "frontmatter must be strict name and description"
            )
        )
        return
    expected_name = identity["name"] if identity is not None else path.parent.name
    if frontmatter["name"] != expected_name:
        issues.append(
            _issue("SKILL_NAME_MISMATCH", path, "frontmatter name differs from plugin name")
        )
    if identity is not None and frontmatter["description"] != identity["description"]:
        issues.append(
            _issue(
                "SKILL_DESCRIPTION_MISMATCH",
                path,
                "frontmatter description differs from plugin.json",
            )
        )
    if any(marker in content for marker in _UNFINISHED_MARKERS):
        issues.append(_issue("SKILL_UNFINISHED_MARKER", path, "unfinished scaffold marker found"))
    for target in _markdown_targets(content):
        if _contains_parent_reference(target):
            issues.append(
                _issue("SKILL_PATH_TRAVERSAL", path, "Markdown resource link contains '..'")
            )


def _parse_frontmatter(content: str) -> dict[str, str] | None:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        if key not in {"name", "description"} or key in fields:
            return None
        scalar = _parse_frontmatter_scalar(value)
        if scalar is None:
            return None
        fields[key] = scalar
    return fields if set(fields) == {"name", "description"} else None


def _parse_frontmatter_scalar(value: str) -> str | None:
    """Accept only the one-line scalar subset emitted by portable bundles."""
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


def _markdown_targets(content: str) -> tuple[str, ...]:
    inline = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", content)
    references = re.findall(r"(?m)^\s*\[[^\]]+\]:\s*(\S+)", content)
    return tuple([*inline, *references])


def _has_exact_regular_file(
    root: Path,
    relative_path: Path,
    unsafe_paths: dict[Path, _LinkProbeResult | None],
    issues: list[ValidationIssue],
) -> bool:
    current = root
    for index, component in enumerate(relative_path.parts):
        try:
            child = next(child for child in current.iterdir() if child.name == component)
        except (OSError, StopIteration):
            return False
        if child in unsafe_paths:
            return False
        probe = _probe_link_or_reparse_point(child)
        if probe in {_LinkProbeResult.LINK, _LinkProbeResult.ERROR}:
            _record_link_probe_rejection(child, probe, unsafe_paths, issues)
            return False
        if probe is _LinkProbeResult.MISSING:
            return False
        if index == len(relative_path.parts) - 1:
            return child.is_file()
        if not child.is_dir():
            return False
        current = child
    return False


def _has_exact_regular_directory(
    root: Path,
    relative_path: Path,
    unsafe_paths: dict[Path, _LinkProbeResult | None],
    issues: list[ValidationIssue],
) -> bool:
    current = root
    for index, component in enumerate(relative_path.parts):
        try:
            child = next(child for child in current.iterdir() if child.name == component)
        except (OSError, StopIteration):
            return False
        if child in unsafe_paths:
            return False
        probe = _probe_link_or_reparse_point(child)
        if probe in {_LinkProbeResult.LINK, _LinkProbeResult.ERROR}:
            _record_link_probe_rejection(child, probe, unsafe_paths, issues)
            return False
        if probe is _LinkProbeResult.MISSING:
            return False
        if index == len(relative_path.parts) - 1:
            return child.is_dir()
        if not child.is_dir():
            return False
        current = child
    return False


def _is_contained(path: Path, resolved_root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(resolved_root)
    except OSError:
        return False


def _record_link_probe_rejection(
    path: Path,
    probe: _LinkProbeResult,
    unsafe_paths: dict[Path, _LinkProbeResult | None],
    issues: list[ValidationIssue],
) -> None:
    """Record one exact-path rejection without leaking filesystem error details."""
    if path in unsafe_paths:
        return
    unsafe_paths[path] = probe
    if probe is _LinkProbeResult.ERROR:
        issues.append(
            _issue(
                "PATH_LINK_PROBE_INVALID",
                path,
                "link or reparse-point metadata cannot be inspected",
            )
        )
        return
    issues.append(
        _issue(
            "PATH_OUTSIDE_BUNDLE",
            path,
            "links and reparse points are not accepted in a portable bundle",
        )
    )


def _record_outside_path(
    path: Path,
    unsafe_paths: dict[Path, _LinkProbeResult | None],
    issues: list[ValidationIssue],
) -> None:
    if path in unsafe_paths:
        return
    unsafe_paths[path] = None
    issues.append(_issue("PATH_OUTSIDE_BUNDLE", path, "resolved path escapes the bundle root"))


def _probe_link_or_reparse_point(path: Path) -> _LinkProbeResult:
    """Inspect one entry without resolving it and report an indeterminate probe explicitly."""
    try:
        if path.is_symlink():
            return _LinkProbeResult.LINK
    except FileNotFoundError:
        return _LinkProbeResult.MISSING
    except OSError:
        return _LinkProbeResult.ERROR
    try:
        is_junction = getattr(path, "is_junction", None)
    except FileNotFoundError:
        return _LinkProbeResult.MISSING
    except OSError:
        return _LinkProbeResult.ERROR
    if callable(is_junction):
        try:
            if is_junction():
                return _LinkProbeResult.LINK
        except FileNotFoundError:
            return _LinkProbeResult.MISSING
        except OSError:
            return _LinkProbeResult.ERROR
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return _LinkProbeResult.MISSING
    except OSError:
        return _LinkProbeResult.ERROR
    return (
        _LinkProbeResult.LINK
        if attributes & _FILE_ATTRIBUTE_REPARSE_POINT
        else _LinkProbeResult.SAFE
    )


def _json_values_equal(left: object, right: object) -> bool:
    """Compare JSON values recursively without Python's bool/int coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _json_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_values_equal(left_item, right_item) for left_item, right_item in zip(left, right)
        )
    return left == right


def _normalize_percent_escapes(target: str) -> str | None:
    """Decode nested percent escapes up to a fixed, fail-closed transformation cap."""
    normalized = target
    for _ in range(_PERCENT_NORMALIZATION_LIMIT):
        decoded = unquote(normalized)
        if decoded == normalized:
            return normalized
        normalized = decoded
    return normalized if unquote(normalized) == normalized else None


def _contains_parent_reference(target: str) -> bool:
    target = target.strip().strip("<>").split("#", 1)[0].split("?", 1)[0]
    if not target:
        return False
    decoded = _normalize_percent_escapes(target)
    if decoded is None:
        return True
    scheme = urlsplit(decoded).scheme.lower()
    if scheme in _REMOTE_LINK_SCHEMES or scheme == "mailto":
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
