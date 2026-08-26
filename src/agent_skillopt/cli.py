"""Command-line entry point for Agent-SkillOpt."""

from __future__ import annotations

import argparse
import codecs
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from agent_skillopt.assessment import evaluate_bundle, review_bundle
from agent_skillopt.bundle import apply_plan, build_plan, render_preview
from agent_skillopt.errors import (
    AgentSkillOptError,
    ConfirmationError,
    SpecError,
    WriteConflictError,
)
from agent_skillopt.installation import build_install_plan, execute_install
from agent_skillopt.models import SkillSpec
from agent_skillopt.validation import validate_bundle


def _uses_utf8(encoding: object) -> bool:
    """Return whether an output encoding is a UTF-8 codec alias."""
    if not isinstance(encoding, str):
        return True
    try:
        return codecs.lookup(encoding).name == "utf-8"
    except (LookupError, TypeError):
        return False


def _configure_output_streams() -> None:
    """Prefer UTF-8 for CLI output when the active text streams support it.

    Windows consoles and redirected streams can inherit a legacy code page.  The
    CLI deliberately contains Chinese help and diagnostics, so configure both
    standard output and standard error before argparse can render either one.
    Test runners and embedders may replace these streams with capture objects
    that have no ``reconfigure`` method; those already accept text directly and
    must be left alone.
    """
    for stream in (sys.stdout, sys.stderr):
        if _uses_utf8(getattr(stream, "encoding", None)):
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, TypeError, ValueError):
            continue


def _unavailable_handler(arguments: argparse.Namespace) -> int:
    """Report commands whose behavior belongs to a later implementation task."""
    print(f"所选操作尚未可用，等待后续实现任务完成：{arguments.command}", file=sys.stderr)
    return 2


def _read_spec_argument(value: str) -> str:
    """Read a preview specification from standard input or one UTF-8 JSON file."""
    if value == "-":
        return sys.stdin.read()
    try:
        return Path(value).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SpecError("无法读取 UTF-8 JSON 规格文件。") from error


def _preview_handler(arguments: argparse.Namespace) -> int:
    """Render one write-free package preview from a strict JSON specification."""
    try:
        specification = SkillSpec.from_json(_read_spec_argument(arguments.spec))
        preview = render_preview(build_plan(specification))
    except AgentSkillOptError:
        print("预览失败：规格无效。", file=sys.stderr)
        return 2
    print(json.dumps(preview, ensure_ascii=False, sort_keys=True))
    return 0


def _apply_handler(arguments: argparse.Namespace) -> int:
    """Create one package only after its recomputed preview token is confirmed."""
    try:
        specification = SkillSpec.from_json(_read_spec_argument(arguments.spec))
        plan = build_plan(specification)
        if arguments.confirm != plan.confirmation_token:
            raise ConfirmationError("confirmation token is missing or stale.")
        apply_plan(plan, arguments.confirm)
    except ConfirmationError:
        print("应用失败：确认令牌无效。", file=sys.stderr)
        return 2
    except WriteConflictError:
        print("应用失败：输出目录已存在。", file=sys.stderr)
        return 2
    except AgentSkillOptError:
        print("应用失败：规格无效。", file=sys.stderr)
        return 2
    print(f"已创建 Skill 包：{plan.output_directory}")
    return 0


def _validate_handler(arguments: argparse.Namespace) -> int:
    """Report deterministic offline bundle validation results."""
    issues = validate_bundle(arguments.path)
    if issues:
        for issue in issues:
            print(f"{issue.code} {issue.path}: {issue.message}", file=sys.stderr)
        return 1
    print("VALID")
    return 0


def _review_handler(arguments: argparse.Namespace) -> int:
    """Emit an offline quality and security report for one Skill package."""
    try:
        report = review_bundle(arguments.path)
    except (OSError, UnicodeError, ValueError):
        print("审查失败：Skill 包无法读取。", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report["status"] == "blocked" else 0


def _evaluate_handler(arguments: argparse.Namespace) -> int:
    """Emit an offline response-based quality evaluation report."""
    try:
        report = evaluate_bundle(arguments.path, arguments.responses)
    except (OSError, UnicodeError, ValueError):
        print("评估失败：响应文件无效。", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["status"] == "blocked":
        return 1
    return 1 if report["evaluation"]["failed"] else 0


def _subprocess_runner(command: tuple[str, ...]) -> int:
    """Run one already-rendered argv tuple without invoking a shell."""
    return subprocess.run(command, shell=False, check=False).returncode


def _install_handler(arguments: argparse.Namespace) -> int:
    """Render a host plan, or run it only through the exact confirmation gate."""
    try:
        plan = build_install_plan(
            arguments.host, arguments.path, arguments.source, arguments.source_ref
        )
    except AgentSkillOptError:
        print("安装计划失败：Skill 包或安装参数无效。", file=sys.stderr)
        return 2

    if plan.network_required:
        if plan.source_ref is None:
            print(
                "警告：执行时会从指定 Git 源获取远程内容；远程内容可能变化，这是信任边界，"
                "确认令牌不固定远程修订。",
                file=sys.stderr,
            )
        else:
            print(
                "警告：执行时会从指定 Git 源获取远程内容；--source-ref 固定到指定 40 位 commit，"
                "但确认令牌不能替代来源审查或权限判断。",
                file=sys.stderr,
            )
    print(
        json.dumps(
            {
                "confirmation_token": plan.confirmation_token,
                "network_required": plan.network_required,
                "source": plan.source,
                "source_ref": plan.source_ref,
                "steps": [list(step) for step in plan.steps],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if not arguments.execute:
        return 0

    completed_steps: list[tuple[str, ...]] = []

    def tracked_runner(command: tuple[str, ...]) -> int:
        status = _subprocess_runner(command)
        if status == 0:
            completed_steps.append(command)
        return status

    def report_incomplete_install() -> None:
        print(
            f"安装未完成：已成功执行 {len(completed_steps)}/{len(plan.steps)} 步；"
            "宿主状态可能已部分改变，请按文档检查或清理后重试。",
            file=sys.stderr,
        )

    try:
        status = execute_install(plan, arguments.confirm, tracked_runner)
    except ConfirmationError:
        print("安装失败：确认令牌无效。", file=sys.stderr)
        return 2
    except OSError:
        print("安装执行失败：无法启动宿主命令。", file=sys.stderr)
        report_incomplete_install()
        return 1
    if status != 0:
        report_incomplete_install()
    return status


def _build_parser() -> argparse.ArgumentParser:
    """Build the 0.2.1 command parser."""
    parser = argparse.ArgumentParser(
        prog="agent-skillopt",
        description="Agent-SkillOpt：跨宿主 Skill 创作工具。",
    )
    subcommands = parser.add_subparsers(dest="command", title="commands")

    preview = subcommands.add_parser("preview", help="预览将要创建的四宿主 Skill 包。")
    preview.add_argument("--spec", required=True, help="JSON 规格文件路径，或 - 表示标准输入。")
    preview.set_defaults(handler=_preview_handler)

    apply = subcommands.add_parser("apply", help="在确认后创建四宿主 Skill 包。")
    apply.add_argument("--spec", required=True)
    apply.add_argument("--confirm", required=True)
    apply.set_defaults(handler=_apply_handler)

    validate = subcommands.add_parser("validate", help="离线验证一个四宿主 Skill 包。")
    validate.add_argument("--path", type=Path, required=True)
    validate.set_defaults(handler=_validate_handler)

    review = subcommands.add_parser("review", help="离线生成 Skill 质量与安全审查报告。")
    review.add_argument("--path", type=Path, required=True)
    review.set_defaults(handler=_review_handler)

    evaluate = subcommands.add_parser("evaluate", help="用离线响应案例生成 Skill 质量评分。")
    evaluate.add_argument("--path", type=Path, required=True)
    evaluate.add_argument("--responses", type=Path, required=True)
    evaluate.set_defaults(handler=_evaluate_handler)

    install = subcommands.add_parser("install", help="渲染或显式执行宿主安装命令。")
    install.add_argument(
        "--host", choices=("codex", "claude", "hermes", "openclaw"), required=True
    )
    install.add_argument("--path", type=Path, required=True)
    install.add_argument("--execute", action="store_true")
    install.add_argument("--confirm")
    install.add_argument("--source", help="Hermes 明确的 <owner>/<repository> Git 安装源。")
    install.add_argument(
        "--source-ref", help="Hermes 可选的固定 40 位 Git commit SHA（映射到 hermes --ref）。"
    )
    install.set_defaults(handler=_install_handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its process status without exiting the caller."""
    _configure_output_streams()
    parser = _build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    handler = getattr(arguments, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(arguments)
