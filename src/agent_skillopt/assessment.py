"""Offline quality and safety assessment for portable Skill bundles."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agent_skillopt.errors import SpecError
from agent_skillopt.installation import _read_stable_file
from agent_skillopt.models import TestCaseSpec
from agent_skillopt.naming import normalize_skill_name
from agent_skillopt.validation import ValidationIssue, validate_bundle

_CASE_KEYS = {"name", "prompt", "required_contains", "forbidden_contains"}
_SECTION_RULES = {
    "WHEN_TO_USE": re.compile(
        r"^##\s+(?:when to use|triggers?|何时使用|使用场景|触发条件)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    "PROCEDURE": re.compile(
        r"^##\s+(?:procedure|steps?|workflow|步骤|流程|操作步骤)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    "OUTPUT": re.compile(
        r"^##\s+(?:output|output format|输出|输出格式)\b", re.IGNORECASE | re.MULTILINE
    ),
    "SAFETY": re.compile(
        r"^##\s+(?:safety|safety boundaries|constraints?|boundaries|安全|安全边界|约束|边界)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
}
_SECURITY_RULES = (
    (
        "SECRET_LIKE_VALUE",
        "high",
        re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
        "secret-like value found in Skill content",
    ),
    (
        "INSTRUCTION_OVERRIDE",
        "high",
        re.compile(
            r"\b(?:ignore\s+(?:all\s+|any\s+|previous\s+)?instructions|"
            r"bypass\s+(?:the\s+|user\s+)?confirmation)\b",
            re.IGNORECASE,
        ),
        "instruction override or confirmation bypass language found",
    ),
    (
        "DESTRUCTIVE_OPERATION",
        "high",
        re.compile(
            r"(?:rm\s+-rf|remove-item\b.*-recurse|format\s+[a-z]:|drop\s+table)",
            re.IGNORECASE,
        ),
        "destructive operation pattern found",
    ),
    (
        "SHELL_EXECUTION",
        "medium",
        re.compile(
            r"(?:subprocess\.(?:run|popen|call)|os\.system|shell\s*=\s*true|child_process)",
            re.IGNORECASE,
        ),
        "shell or subprocess execution pattern found",
    ),
    (
        "NETWORK_ACCESS",
        "medium",
        re.compile(
            r"(?:\bcurl\b|\bwget\b|invoke-webrequest|requests\.(?:get|post)|"
            r"urllib\.request|fetch\s*\()",
            re.IGNORECASE,
        ),
        "network access pattern found",
    ),
    (
        "ENVIRONMENT_SECRET_ACCESS",
        "medium",
        re.compile(r"(?:os\.environ|process\.env|getenvironmentvariable)", re.IGNORECASE),
        "environment or secret lookup pattern found",
    ),
)
_MAX_SECURITY_SCAN_BYTES = 2 * 1024 * 1024


def review_bundle(root: Path) -> dict[str, Any]:
    """Return a deterministic, secret-free static quality and safety report."""
    bundle_root = Path(root)
    validation_issues = validate_bundle(bundle_root)
    if validation_issues:
        findings = [_validation_finding(bundle_root, issue) for issue in validation_issues]
        return {
            "executed": False,
            "findings": findings,
            "network_accessed": False,
            "quality_score": 0,
            "security": {"findings": [], "score": 0, "status": "blocked"},
            "status": "blocked",
        }

    skill_path = _skill_path(bundle_root)
    skill_content = skill_path.read_text(encoding="utf-8")
    description = _manifest_description(bundle_root)
    cases, case_findings = _load_cases(bundle_root)
    quality_score, quality_findings = _quality_assessment(
        skill_content, description, cases, case_findings
    )
    security_findings = _security_assessment(bundle_root)
    security_score = max(
        0,
        100
        - 60 * sum(finding["severity"] == "high" for finding in security_findings)
        - 20 * sum(finding["severity"] == "medium" for finding in security_findings),
    )
    security_status = _security_status(security_findings)
    findings = quality_findings + security_findings
    if security_status == "blocked":
        status = "blocked"
    elif findings:
        status = "review"
    else:
        status = "pass"
    return {
        "executed": False,
        "findings": findings,
        "network_accessed": False,
        "quality_score": quality_score,
        "security": {
            "findings": security_findings,
            "score": security_score,
            "status": security_status,
        },
        "status": status,
    }


def evaluate_bundle(root: Path, responses_path: Path) -> dict[str, Any]:
    """Score supplied response text against packaged cases without running a Skill."""
    review = review_bundle(root)
    if review["status"] == "blocked":
        return {
            **review,
            "evaluation": {"cases": [], "failed": 0, "passed": 0, "score": 0},
        }

    cases, case_findings = _load_cases(Path(root))
    if case_findings:
        return {
            **review,
            "evaluation": {"cases": [], "failed": 0, "passed": 0, "score": 0},
            "findings": review["findings"],
            "status": "blocked",
        }
    responses = _load_responses(Path(responses_path))
    results: list[dict[str, Any]] = []
    for case in cases:
        response = responses.get(case.name)
        if response is None:
            results.append(
                {
                    "failed_required": list(case.required_contains),
                    "forbidden_found": [],
                    "name": case.name,
                    "passed": False,
                    "score": 0,
                    "status": "missing",
                }
            )
            continue
        folded_response = response.casefold()
        matched_required = [
            phrase for phrase in case.required_contains if phrase.casefold() in folded_response
        ]
        found_forbidden = [
            phrase for phrase in case.forbidden_contains if phrase.casefold() in folded_response
        ]
        required_score = (
            100
            if not case.required_contains
            else round(100 * len(matched_required) / len(case.required_contains))
        )
        forbidden_score = 0 if found_forbidden else 100
        score = round(required_score * 0.7 + forbidden_score * 0.3)
        results.append(
            {
                "failed_required": [
                    phrase for phrase in case.required_contains if phrase not in matched_required
                ],
                "forbidden_found": found_forbidden,
                "name": case.name,
                "passed": (
                    not found_forbidden
                    and len(matched_required) == len(case.required_contains)
                ),
                "score": score,
                "status": "evaluated",
            }
        )

    passed = sum(result["passed"] for result in results)
    failed = len(results) - passed
    score = round(sum(result["score"] for result in results) / len(results)) if results else 0
    return {
        **review,
        "evaluation": {"cases": results, "failed": failed, "passed": passed, "score": score},
    }


def _validation_finding(root: Path, issue: ValidationIssue) -> dict[str, Any]:
    return {
        "code": "BUNDLE_INVALID",
        "message": issue.message,
        "path": _relative_path(root, issue.path),
        "rule": issue.code,
        "severity": "high",
    }


def _skill_path(root: Path) -> Path:
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    return root / "skills" / manifest["name"] / "SKILL.md"


def _manifest_description(root: Path) -> str:
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    return manifest["description"]


def _load_cases(root: Path) -> tuple[tuple[TestCaseSpec, ...], list[dict[str, Any]]]:
    cases_directory = root / "tests" / "cases"
    if not cases_directory.is_dir():
        return (), [
            {
                "code": "TEST_CASES_MISSING",
                "message": "no offline evaluation cases are packaged",
                "path": "tests/cases",
                "severity": "medium",
            }
        ]

    cases: list[TestCaseSpec] = []
    findings: list[dict[str, Any]] = []
    names: set[str] = set()
    for path in sorted(cases_directory.glob("*.json"), key=lambda item: item.name):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or set(data) != _CASE_KEYS:
                raise ValueError("invalid case fields")
            name = data["name"]
            prompt = data["prompt"]
            required = data["required_contains"]
            forbidden = data["forbidden_contains"]
            normalized_name = normalize_skill_name(name)
            if (
                not isinstance(prompt, str)
                or not prompt.strip()
                or not isinstance(required, list)
                or not isinstance(forbidden, list)
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in [*required, *forbidden]
                )
                or normalized_name != path.stem
                or normalized_name in names
            ):
                raise ValueError("invalid case values")
            names.add(normalized_name)
            cases.append(
                TestCaseSpec(
                    name=normalized_name,
                    prompt=prompt,
                    required_contains=tuple(required),
                    forbidden_contains=tuple(forbidden),
                )
            )
        except (OSError, UnicodeError, ValueError, SpecError, json.JSONDecodeError):
            findings.append(
                {
                    "code": "TEST_CASE_INVALID",
                    "message": "offline evaluation case is malformed",
                    "path": _relative_path(root, path),
                    "severity": "high",
                }
            )
    if not cases and not findings:
        findings.append(
            {
                "code": "TEST_CASES_MISSING",
                "message": "no offline evaluation cases are packaged",
                "path": "tests/cases",
                "severity": "medium",
            }
        )
    return tuple(cases), findings


def _quality_assessment(
    skill_content: str,
    description: str,
    cases: tuple[TestCaseSpec, ...],
    case_findings: list[dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    body = _frontmatter_body(skill_content)
    score = 20
    findings: list[dict[str, Any]] = []
    if len(description.strip()) >= 20:
        score += 10
    else:
        findings.append(_quality_finding("QUALITY_SHORT_DESCRIPTION", "description is too short"))
    if len(body.strip()) >= 80:
        score += 10
    else:
        findings.append(_quality_finding("QUALITY_SHORT_BODY", "Skill body is too short"))
    for rule_name, pattern in _SECTION_RULES.items():
        if pattern.search(body):
            score += 10
        else:
            findings.append(
                _quality_finding(
                    f"QUALITY_MISSING_{rule_name}",
                    f"recommended {rule_name.lower()} section is missing",
                )
            )
    if cases:
        score += 10
    else:
        findings.append(
            _quality_finding("QUALITY_NO_TEST_CASES", "no evaluation cases are available")
        )
    if any(case.required_contains or case.forbidden_contains for case in cases):
        score += 10
    else:
        findings.append(
            _quality_finding(
                "QUALITY_NO_ASSERTIONS",
                "evaluation cases contain no required or forbidden assertions",
            )
        )
    findings.extend(case_findings)
    return score, findings


def _security_assessment(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, content in _text_files(root):
        for line_number, line in enumerate(content.splitlines(), start=1):
            for code, severity, pattern, message in _SECURITY_RULES:
                if pattern.search(line):
                    findings.append(
                        {
                            "code": code,
                            "line": line_number,
                            "message": message,
                            "path": _relative_path(root, path),
                            "severity": severity,
                        }
                    )
    return findings


def _text_files(root: Path):
    for current, directories, filenames in os.walk(root, followlinks=False):
        directories.sort()
        for filename in sorted(filenames):
            path = Path(current) / filename
            try:
                if path.lstat().st_size > _MAX_SECURITY_SCAN_BYTES:
                    continue
                raw_content, _ = _read_stable_file(path)
                content = raw_content.decode("utf-8")
            except (OSError, SpecError, UnicodeError):
                continue
            yield path, content


def _frontmatter_body(content: str) -> str:
    parts = content.split("---", 2)
    return parts[2] if len(parts) == 3 else content


def _quality_finding(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "path": "skills", "severity": "low"}


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _security_status(findings: list[dict[str, Any]]) -> str:
    if any(finding["severity"] == "high" for finding in findings):
        return "blocked"
    if findings:
        return "review"
    return "pass"


def _load_responses(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    responses = data.get("responses") if isinstance(data, dict) else None
    if not isinstance(responses, dict) or any(
        not isinstance(name, str) or not isinstance(response, str)
        for name, response in responses.items()
    ):
        raise ValueError("responses must be an object mapping case names to strings")
    return responses
