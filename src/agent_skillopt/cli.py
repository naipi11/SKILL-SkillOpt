"""Command-line entry point for Agent-SkillOpt."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from agent_skillopt.config import load_config
from agent_skillopt.doctor import run_doctor
from agent_skillopt.errors import ConfigurationError, ExecutionGateError
from agent_skillopt.init_project import available_presets, initialize_project
from agent_skillopt.invocation import execute, render_invocation, require_execution_permission
from agent_skillopt.report import build_report, write_report


def _placeholder_handler(_: argparse.Namespace) -> int:
    """Temporarily acknowledge a registered command until it is implemented."""
    return 0


def _init_handler(arguments: argparse.Namespace) -> int:
    try:
        config_path = initialize_project(arguments.path, arguments.preset, arguments.force)
    except (FileExistsError, ValueError) as error:
        print(f"初始化失败：{error}", file=sys.stderr)
        return 2
    print(f"已创建配置：{config_path}")
    return 0


def _doctor_handler(arguments: argparse.Namespace) -> int:
    try:
        config = load_config(arguments.config)
    except ConfigurationError as error:
        print(f"配置错误：{error}", file=sys.stderr)
        return 2

    diagnostics = run_doctor(config, os.environ)
    if arguments.json:
        print(json.dumps([item.to_dict() for item in diagnostics], ensure_ascii=False))
    else:
        for item in diagnostics:
            print(f"{item.level.upper()} {item.code}: {item.message}")
            if item.remediation:
                print(f"  建议：{item.remediation}")
    return 2 if any(item.level == "error" for item in diagnostics) else 0


def _run_handler(arguments: argparse.Namespace) -> int:
    try:
        config = load_config(arguments.config)
        invocation = render_invocation(config, arguments.config, datetime.now(timezone.utc))
    except ConfigurationError as error:
        print(f"配置或本地前置条件错误：{error}", file=sys.stderr)
        return 2

    if arguments.dry_run:
        print("Dry-run command:")
        print(shlex.join(invocation.command))
        if not os.environ.get(config.provider.api_key_env):
            print(f"警告：环境变量 {config.provider.api_key_env} 未设置；dry-run 不需要它。")
        return 0

    try:
        require_execution_permission(config, arguments.allow_network, os.environ)
        return_code = execute(invocation, _subprocess_runner)
    except ExecutionGateError as error:
        print(f"运行门禁：{error}", file=sys.stderr)
        return error.exit_code
    return 0 if return_code == 0 else 4


def _report_handler(arguments: argparse.Namespace) -> int:
    manifest_path = arguments.run_dir / "manifest.json"
    if not manifest_path.is_file():
        print(f"报告输入错误：未找到 manifest.json：{manifest_path}", file=sys.stderr)
        return 2

    try:
        report = build_report(arguments.run_dir)
        output_directory = arguments.output_dir or arguments.run_dir
        json_path, markdown_path = write_report(report, output_directory)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"报告输入错误：{error}", file=sys.stderr)
        return 2

    print(f"已生成 JSON 报告：{json_path}")
    print(f"已生成 Markdown 报告：{markdown_path}")
    return 0


def _subprocess_runner(
    command: tuple[str, ...], working_directory: Path, child_environment: dict[str, str]
) -> int:
    result = subprocess.run(
        command,
        cwd=working_directory,
        env=child_environment,
        check=False,
    )
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the public command parser."""
    parser = argparse.ArgumentParser(
        prog="agent-skillopt",
        description="Agent-SkillOpt：安全集成 Microsoft SkillOpt 的工具包。",
    )
    subcommands = parser.add_subparsers(dest="command", title="commands")

    init = subcommands.add_parser("init", help="创建本地项目配置。")
    init.add_argument("--path", type=Path, default=Path("."), help="目标项目目录。")
    init.add_argument(
        "--preset",
        choices=available_presets(),
        default="searchqa-deepseek",
        help="要写入的起始配置。",
    )
    init.add_argument("--force", action="store_true", help="允许覆盖已有 agent-skillopt.yaml。")
    init.set_defaults(handler=_init_handler)

    doctor = subcommands.add_parser("doctor", help="诊断本地配置和上游检出。")
    doctor.add_argument("--config", type=Path, required=True, help="项目 YAML 配置路径。")
    doctor.add_argument("--json", action="store_true", help="输出稳定的 JSON 诊断数组。")
    doctor.set_defaults(handler=_doctor_handler)

    run = subcommands.add_parser("run", help="渲染或执行经授权的上游训练。")
    run.add_argument("--config", type=Path, required=True, help="项目 YAML 配置路径。")
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只渲染命令，不启动子进程。")
    mode.add_argument("--allow-network", action="store_true", help="确认允许真实网络运行。")
    run.set_defaults(handler=_run_handler)

    report = subcommands.add_parser("report", help="生成证据优先的实验报告。")
    report.add_argument(
        "--run-dir", type=Path, required=True, help="包含 manifest.json 的运行目录。"
    )
    report.add_argument("--output-dir", type=Path, help="报告输出目录；默认写入运行目录。")
    report.set_defaults(handler=_report_handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its process status without exiting the caller."""
    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    handler = getattr(arguments, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(arguments)
