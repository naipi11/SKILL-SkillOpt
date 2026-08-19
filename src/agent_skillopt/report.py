"""Evidence-first parsing for locally produced experiment artifacts."""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Metric:
    """One directly reported, validated experiment metric."""

    split: str
    score: float
    samples: int
    cost_usd: float | None


@dataclass(frozen=True, slots=True)
class ReportWarning:
    """A limitation in the evidence available for a report."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    """The manifest, accepted metrics, and evidence limitations for one run."""

    manifest: Mapping[str, Any]
    metrics: list[Metric]
    warnings: list[ReportWarning]
    raw_upstream_summary: Mapping[str, Any] | None = None


def build_report(run_directory: Path) -> ExperimentReport:
    """Read local evidence without inventing metrics when it is absent or incomplete."""
    manifest_path = run_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest.json 顶层必须是对象。")

    metrics_path = run_directory / "metrics.json"
    if not metrics_path.exists():
        return ExperimentReport(
            manifest=manifest,
            metrics=[],
            warnings=[
                ReportWarning(
                    code="METRICS_UNAVAILABLE",
                    message="未找到 metrics.json；报告不会推断或伪造实验指标。",
                )
            ],
        )

    try:
        metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ExperimentReport(
            manifest=manifest,
            metrics=[],
            warnings=[
                ReportWarning(
                    code="METRICS_INVALID_JSON",
                    message="metrics.json 不是有效 JSON；报告不会猜测指标。",
                )
            ],
        )
    if not isinstance(metrics_payload, Mapping):
        return ExperimentReport(
            manifest=manifest,
            metrics=[],
            warnings=[
                ReportWarning(
                    code="METRICS_SCHEMA_INVALID",
                    message="metrics.json 顶层必须是对象；报告不会猜测指标。",
                )
            ],
        )

    metrics: list[Metric] = []
    warnings: list[ReportWarning] = []
    raw_summary: Mapping[str, Any] | None = None
    for split, raw_metric in metrics_payload.items():
        if split == "upstream_summary":
            if isinstance(raw_metric, Mapping):
                raw_summary = _sanitize_mapping(raw_metric)
            continue
        if not isinstance(raw_metric, Mapping):
            warnings.append(
                ReportWarning(
                    code="METRIC_SCHEMA_INVALID",
                    message=f"{split} 指标必须是对象，已忽略。",
                )
            )
            continue

        score = raw_metric.get("score")
        if not _is_finite_number(score):
            warnings.append(
                ReportWarning(
                    code="METRIC_SCORE_INVALID",
                    message=f"{split} 指标的 score 必须是有限数值，已忽略。",
                )
            )
            continue

        samples = raw_metric.get("samples")
        if not _is_positive_integer(samples):
            code = "HOLDOUT_SAMPLES_REQUIRED" if split == "holdout" else "METRIC_SAMPLES_INVALID"
            warnings.append(
                ReportWarning(
                    code=code,
                    message=f"{split} 指标的 samples 必须是正整数，已忽略。",
                )
            )
            continue

        cost_usd = raw_metric.get("cost_usd")
        if cost_usd is not None and (not _is_finite_number(cost_usd) or cost_usd < 0):
            warnings.append(
                ReportWarning(
                    code="METRIC_COST_INVALID",
                    message=f"{split} 指标的 cost_usd 必须是非负数或 null，已忽略。",
                )
            )
            continue

        metrics.append(
            Metric(
                split=str(split),
                score=float(score),
                samples=samples,
                cost_usd=None if cost_usd is None else float(cost_usd),
            )
        )

    return ExperimentReport(
        manifest=manifest,
        metrics=metrics,
        warnings=warnings,
        raw_upstream_summary=raw_summary,
    )


def write_report(report: ExperimentReport, output_directory: Path) -> tuple[Path, Path]:
    """Atomically write a machine-readable and Chinese-first human-readable report."""
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "report.json"
    markdown_path = output_directory / "report.md"
    _atomic_write_json(json_path, _report_payload(report))
    _atomic_write_text(markdown_path, _render_markdown(report))
    return json_path, markdown_path


def _report_payload(report: ExperimentReport) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest": _sanitize_mapping(report.manifest),
        "metrics": [
            {
                "split": metric.split,
                "score": metric.score,
                "samples": metric.samples,
                "cost_usd": metric.cost_usd,
            }
            for metric in report.metrics
        ],
        "warnings": [
            {"code": warning.code, "message": warning.message} for warning in report.warnings
        ],
        "raw_upstream_summary": (
            None
            if report.raw_upstream_summary is None
            else _sanitize_mapping(report.raw_upstream_summary)
        ),
    }


def _render_markdown(report: ExperimentReport) -> str:
    status = report.manifest.get("status", "unknown")
    lines = [
        "# Agent-SkillOpt experiment report",
        "",
        "## Run status / 运行状态",
        "",
        f"- Status / 状态：`{_escape_markdown_cell(str(status))}`",
        "",
        "## Evidence warnings / 证据警告",
        "",
    ]
    if report.warnings:
        lines.extend(f"- `{warning.code}`：{warning.message}" for warning in report.warnings)
    else:
        lines.append("- 无；以下指标均为输入文件中明确报告的证据。")

    lines.extend(["", "## Reported metrics / 已报告指标", ""])
    if report.metrics:
        lines.extend(
            [
                "| Split / 切分 | Score / 分数 | Samples / 样本数 | Cost USD / 成本 |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for metric in report.metrics:
            cost = "not reported / 未报告" if metric.cost_usd is None else str(metric.cost_usd)
            lines.append(
                "| "
                f"{_escape_markdown_cell(metric.split)} | {metric.score} | "
                f"{metric.samples} | {cost} |"
            )
    else:
        lines.append("未找到可接受的指标；本报告不会推断分数、样本数或成本。")

    if report.raw_upstream_summary is not None:
        lines.extend(
            [
                "",
                "## Raw upstream summary / 原始上游摘要（已过滤敏感字段）",
                "",
                "```json",
                json.dumps(
                    _sanitize_mapping(report.raw_upstream_summary),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "```",
            ]
        )

    return "\n".join(lines) + "\n"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _atomic_write_text(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sanitize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if _is_sensitive_key(str(key)):
            continue
        sanitized[str(key)] = _sanitize_value(item)
    return sanitized


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return any(
        marker in normalized
        for marker in ("key", "token", "secret", "password", "authorization", "credential")
    )
