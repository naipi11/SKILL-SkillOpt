"""Behavioral tests for evidence-first experiment reporting."""

from __future__ import annotations

import json
from pathlib import Path

from agent_skillopt.cli import main
from agent_skillopt.report import Metric, build_report, write_report


def write_manifest(run_directory: Path) -> None:
    """Create the smallest redacted run artifact a report can consume."""
    (run_directory / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "succeeded",
                "provider": {"base_url_host": "api.example.test", "model": "test-model"},
                "run": {"seed": 42},
            }
        ),
        encoding="utf-8",
    )


def test_report_warns_when_metrics_are_absent(tmp_path: Path) -> None:
    """Removing the metrics artifact must not fabricate an experiment result."""
    write_manifest(tmp_path)

    report = build_report(tmp_path)

    assert "METRICS_UNAVAILABLE" in {warning.code for warning in report.warnings}
    assert report.metrics == []


def test_report_rejects_holdout_metric_without_samples(tmp_path: Path) -> None:
    """Dropping sample validation must not admit a statistically opaque holdout score."""
    write_manifest(tmp_path)
    (tmp_path / "metrics.json").write_text(
        '{"holdout": {"score": 0.8}}',
        encoding="utf-8",
    )

    report = build_report(tmp_path)

    assert "HOLDOUT_SAMPLES_REQUIRED" in {warning.code for warning in report.warnings}
    assert report.metrics == []


def test_report_keeps_only_explicit_valid_metrics_and_sanitized_upstream_summary(
    tmp_path: Path,
) -> None:
    """Weak validation must not turn malformed values or credential fields into evidence."""
    write_manifest(tmp_path)
    (tmp_path / "metrics.json").write_text(
        json.dumps(
            {
                "baseline": {"score": 0.62, "samples": 100, "cost_usd": None},
                "candidate": {"score": 0.68, "samples": 100, "cost_usd": 1.25},
                "holdout": {"score": 0.65, "samples": 120, "cost_usd": None},
                "upstream_summary": {
                    "source": "synthetic-example",
                    "api_key": "remove-me",
                    "nested": {"token": "remove-me-too", "completed": True},
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)

    assert report.metrics == [
        Metric(split="baseline", score=0.62, samples=100, cost_usd=None),
        Metric(split="candidate", score=0.68, samples=100, cost_usd=1.25),
        Metric(split="holdout", score=0.65, samples=120, cost_usd=None),
    ]
    assert report.warnings == []
    assert report.raw_upstream_summary == {
        "source": "synthetic-example",
        "nested": {"completed": True},
    }


def test_report_warns_instead_of_crashing_for_invalid_metrics_json(tmp_path: Path) -> None:
    """A corrupted metrics artifact must remain visible as missing evidence, not abort reporting."""
    write_manifest(tmp_path)
    (tmp_path / "metrics.json").write_text("{not-json", encoding="utf-8")

    report = build_report(tmp_path)

    assert "METRICS_INVALID_JSON" in {warning.code for warning in report.warnings}
    assert report.metrics == []


def test_report_rejects_boolean_values_invalid_samples_and_negative_costs(tmp_path: Path) -> None:
    """Relaxing the schema must not convert booleans or estimates into reported evidence."""
    write_manifest(tmp_path)
    (tmp_path / "metrics.json").write_text(
        json.dumps(
            {
                "baseline": {"score": True, "samples": 100},
                "candidate": {"score": 0.68, "samples": True},
                "holdout": {"score": 0.65, "samples": 120, "cost_usd": -0.01},
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)

    assert report.metrics == []
    assert {warning.code for warning in report.warnings} == {
        "METRIC_SCORE_INVALID",
        "METRIC_SAMPLES_INVALID",
        "METRIC_COST_INVALID",
    }


def test_write_report_puts_evidence_warnings_before_reported_metrics(tmp_path: Path) -> None:
    """A layout change must not let reported scores obscure their evidence limitations."""
    write_manifest(tmp_path)
    (tmp_path / "metrics.json").write_text(
        json.dumps(
            {
                "baseline": {"score": 0.62, "samples": 100, "cost_usd": None},
                "candidate": {"score": True, "samples": 100, "cost_usd": None},
            }
        ),
        encoding="utf-8",
    )

    json_path, markdown_path = write_report(build_report(tmp_path), tmp_path / "report-output")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["metrics"] == [
        {"cost_usd": None, "samples": 100, "score": 0.62, "split": "baseline"}
    ]
    assert "METRIC_SCORE_INVALID" in markdown
    assert markdown.index("Evidence warnings / 证据警告") < markdown.index(
        "Reported metrics / 已报告指标"
    )


def test_report_cli_writes_and_prints_both_report_paths(tmp_path: Path, capsys) -> None:
    """Removing the CLI report path contract must make local artifacts undiscoverable."""
    write_manifest(tmp_path)
    output_directory = tmp_path / "report-output"

    assert main(["report", "--run-dir", str(tmp_path), "--output-dir", str(output_directory)]) == 0

    output = capsys.readouterr().out
    assert str(output_directory / "report.json") in output
    assert str(output_directory / "report.md") in output


def test_report_cli_returns_two_for_a_missing_manifest(tmp_path: Path, capsys) -> None:
    """Treating a missing manifest as success would make a report look more evidenced than it is."""
    run_directory = tmp_path / "missing-run"
    run_directory.mkdir()

    assert main(["report", "--run-dir", str(run_directory)]) == 2

    assert "manifest.json" in capsys.readouterr().err
