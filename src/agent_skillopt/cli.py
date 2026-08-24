"""Command-line entry point for Agent-SkillOpt."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path


def _unavailable_handler(arguments: argparse.Namespace) -> int:
    """Report commands whose behavior belongs to a later implementation task."""
    print(f"所选操作尚未可用，等待后续实现任务完成：{arguments.command}", file=sys.stderr)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    """Build the 0.2.0 command parser."""
    parser = argparse.ArgumentParser(
        prog="agent-skillopt",
        description="Agent-SkillOpt：跨宿主 Skill 创作工具。",
    )
    subcommands = parser.add_subparsers(dest="command", title="commands")

    preview = subcommands.add_parser("preview", help="预览将要创建的四宿主 Skill 包。")
    preview.add_argument("--spec", required=True, help="JSON 规格文件路径，或 - 表示标准输入。")
    preview.set_defaults(handler=_unavailable_handler)

    apply = subcommands.add_parser("apply", help="在确认后创建四宿主 Skill 包。")
    apply.add_argument("--spec", required=True)
    apply.add_argument("--confirm", required=True)
    apply.set_defaults(handler=_unavailable_handler)

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
