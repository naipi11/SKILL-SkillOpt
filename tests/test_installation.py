import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_skillopt.cli import main
from agent_skillopt.errors import ConfirmationError, SpecError
from agent_skillopt.installation import build_install_plan, execute_install
from agent_skillopt.validation import BundleValidationError


def test_codex_plan_adds_a_local_marketplace_then_the_plugin(valid_bundle: Path):
    plan = build_install_plan("codex", valid_bundle, None)

    assert plan.steps == (
        ("codex", "plugin", "marketplace", "add", str(valid_bundle)),
        ("codex", "plugin", "add", "minimal-skill@minimal-skill"),
    )
    assert plan.network_required is False


def test_claude_plan_adds_a_local_marketplace_then_installs_the_plugin(valid_bundle: Path):
    plan = build_install_plan("claude", valid_bundle, None)

    assert plan.steps == (
        ("claude", "plugin", "marketplace", "add", str(valid_bundle)),
        ("claude", "plugin", "install", "minimal-skill@minimal-skill"),
    )
    assert plan.network_required is False


def test_openclaw_plan_installs_inspects_then_restarts(valid_bundle: Path):
    plan = build_install_plan("openclaw", valid_bundle, None)

    assert plan.steps == (
        ("openclaw", "plugins", "install", str(valid_bundle)),
        ("openclaw", "plugins", "inspect", "minimal-skill"),
        ("openclaw", "gateway", "restart"),
    )
    assert plan.network_required is False


def test_hermes_plan_requires_an_explicit_git_source(valid_bundle: Path):
    with pytest.raises(SpecError, match="--source"):
        build_install_plan("hermes", valid_bundle, None)


@pytest.mark.parametrize("source", ("", " owner/repository", "--unexpected-option"))
def test_hermes_plan_rejects_an_inappropriate_git_source(source: str, valid_bundle: Path):
    with pytest.raises(SpecError, match="--source"):
        build_install_plan("hermes", valid_bundle, source)


def test_hermes_plan_marks_the_explicit_source_as_network_required(valid_bundle: Path):
    plan = build_install_plan("hermes", valid_bundle, "owner/repository")

    assert plan.steps == (
        ("hermes", "plugins", "install", "owner/repository", "--no-enable"),
        ("hermes", "plugins", "enable", "minimal-skill"),
    )
    assert plan.network_required is True


@pytest.mark.parametrize("host", ("codex", "claude", "openclaw"))
def test_local_hosts_reject_an_inappropriate_source(host: str, valid_bundle: Path):
    with pytest.raises(SpecError, match="--source"):
        build_install_plan(host, valid_bundle, "owner/repository")


def test_build_plan_rejects_an_unsupported_host(valid_bundle: Path):
    with pytest.raises(SpecError, match="unsupported host"):
        build_install_plan("unknown", valid_bundle, None)


def test_build_plan_rejects_a_bundle_that_fails_formal_validation(valid_bundle: Path):
    (valid_bundle / "plugin.json").write_text("not json", encoding="utf-8")

    with pytest.raises(BundleValidationError):
        build_install_plan("codex", valid_bundle, None)


def test_plan_token_is_deterministic_and_captures_the_rendered_operation(valid_bundle: Path):
    first = build_install_plan("hermes", valid_bundle, "owner/repository")
    second = build_install_plan("hermes", valid_bundle, "owner/repository")
    changed_source = build_install_plan("hermes", valid_bundle, "owner/other-repository")

    assert first.confirmation_token == second.confirmation_token
    assert first.confirmation_token != changed_source.confirmation_token


def test_local_root_with_spaces_stays_a_single_argv_token(valid_bundle: Path, tmp_path: Path):
    spaced_root = tmp_path / "bundle root"
    valid_bundle.rename(spaced_root)

    plan = build_install_plan("codex", spaced_root, None)

    assert plan.steps[0][-1] == str(spaced_root)
    assert len(plan.steps[0]) == 5


def test_execute_install_requires_the_rendered_token(valid_bundle: Path):
    plan = build_install_plan("openclaw", valid_bundle, None)
    calls: list[tuple[str, ...]] = []

    with pytest.raises(ConfirmationError):
        execute_install(plan, "wrong", calls.append)

    assert calls == []


def test_execute_install_passes_each_argv_step_to_the_runner(valid_bundle: Path):
    plan = build_install_plan("claude", valid_bundle, None)
    calls: list[tuple[str, ...]] = []

    assert execute_install(plan, plan.confirmation_token, lambda step: calls.append(step) or 0) == 0

    assert calls == list(plan.steps)


def test_execute_install_stops_after_the_first_nonzero_runner_status(valid_bundle: Path):
    plan = build_install_plan("openclaw", valid_bundle, None)
    calls: list[tuple[str, ...]] = []

    assert execute_install(plan, plan.confirmation_token, lambda step: calls.append(step) or 7) == 7

    assert calls == [plan.steps[0]]


def test_install_command_renders_json_without_running_a_host_command(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path, capsys
):
    def unexpected_subprocess(*args: object, **kwargs: object) -> None:
        raise AssertionError("rendering must not start a subprocess")

    monkeypatch.setattr("agent_skillopt.cli.subprocess.run", unexpected_subprocess)

    assert main(["install", "--host", "codex", "--path", str(valid_bundle)]) == 0

    rendered = json.loads(capsys.readouterr().out)
    assert rendered == {
        "confirmation_token": build_install_plan("codex", valid_bundle, None).confirmation_token,
        "network_required": False,
        "steps": [
            ["codex", "plugin", "marketplace", "add", str(valid_bundle)],
            ["codex", "plugin", "add", "minimal-skill@minimal-skill"],
        ],
    }


def test_install_execute_rejects_a_missing_or_wrong_token_without_subprocess(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path, capsys
):
    calls: list[tuple[object, ...]] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("agent_skillopt.cli.subprocess.run", runner)

    assert main(["install", "--host", "codex", "--path", str(valid_bundle), "--execute"]) == 2
    assert (
        main(
            [
                "install",
                "--host",
                "codex",
                "--path",
                str(valid_bundle),
                "--execute",
                "--confirm",
                "wrong",
            ]
        )
        == 2
    )

    assert calls == []
    assert capsys.readouterr().err.count("确认令牌无效") == 2


def test_install_execute_uses_shell_false_after_an_exact_confirmation(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path
):
    plan = build_install_plan("claude", valid_bundle, None)
    calls: list[tuple[tuple[str, ...], bool, bool]] = []

    def runner(command: tuple[str, ...], *, shell: bool, check: bool) -> SimpleNamespace:
        calls.append((command, shell, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("agent_skillopt.cli.subprocess.run", runner)

    assert (
        main(
            [
                "install",
                "--host",
                "claude",
                "--path",
                str(valid_bundle),
                "--execute",
                "--confirm",
                plan.confirmation_token,
            ]
        )
        == 0
    )

    assert calls == [(step, False, False) for step in plan.steps]
