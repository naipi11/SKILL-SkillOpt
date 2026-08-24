"""Command-line entry point for Agent-SkillOpt."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from agent_skillopt.bundle import apply_plan, build_plan, render_preview
from agent_skillopt.errors import (
    AgentSkillOptError,
    ConfirmationError,
    SpecError,
    WriteConflictError,
)
from agent_skillopt.models import SkillSpec


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


def _build_parser() -> argparse.ArgumentParser:
    """Build the 0.2.0 command parser."""
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
    validate.set_defaults(handler=_unavailable_handler)

    install = subcommands.add_parser("install", help="渲染或显式执行宿主安装命令。")
    install.add_argument(
        "--host", choices=("codex", "claude", "hermes", "openclaw"), required=True
    )
    install.add_argument("--path", type=Path, required=True)
    install.add_argument("--execute", action="store_true")
    install.add_argument("--confirm")
    install.add_argument("--source", help="Hermes Git 安装源，例如 owner/repository。")
    install.set_defaults(handler=_unavailable_handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its process status without exiting the caller."""
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
