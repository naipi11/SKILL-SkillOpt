import json
from dataclasses import replace
from pathlib import Path
from shutil import copytree
from types import SimpleNamespace

import pytest

from agent_skillopt.cli import main
from agent_skillopt.errors import ConfirmationError, SpecError
from agent_skillopt.installation import build_install_plan, execute_install
from agent_skillopt.models import InstallPlan
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


@pytest.mark.parametrize(
    "character", ("&", "|", "<", ">", "(", ")", "^", "%", "!", '"', "'", "\n", "\r")
)
def test_build_plan_rejects_windows_command_metacharacters_in_a_local_root(character: str):
    unsafe_root = Path(f"bundle{character}root")

    with pytest.raises(SpecError, match="unsafe"):
        build_install_plan("codex", unsafe_root, None)


@pytest.mark.parametrize(
    "source", ("owner/repository&next", 'owner/"repository', "owner/repository\nnext")
)
def test_build_plan_rejects_windows_command_metacharacters_in_hermes_source(
    source: str, valid_bundle: Path
):
    with pytest.raises(SpecError, match="unsafe"):
        build_install_plan("hermes", valid_bundle, source)


def test_local_root_with_spaces_stays_a_single_argv_token(valid_bundle: Path, tmp_path: Path):
    spaced_root = tmp_path / "bundle root"
    valid_bundle.rename(spaced_root)

    plan = build_install_plan("codex", spaced_root, None)

    assert plan.steps[0][-1] == str(spaced_root)
    assert len(plan.steps[0]) == 5


def test_plan_uses_a_canonical_root_when_relative_cwd_changes(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path, tmp_path: Path
):
    monkeypatch.chdir(valid_bundle)
    plan = build_install_plan("codex", Path("."), None)
    expected_root = valid_bundle.resolve()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    calls: list[tuple[str, ...]] = []

    assert plan.bundle_root == expected_root
    assert plan.steps[0][-1] == str(expected_root)

    monkeypatch.chdir(elsewhere)
    assert execute_install(plan, plan.confirmation_token, lambda step: calls.append(step) or 0) == 0

    assert calls == list(plan.steps)


def test_execute_install_rejects_in_place_bundle_content_drift_without_a_runner(valid_bundle: Path):
    plan = build_install_plan("codex", valid_bundle, None)
    calls: list[tuple[str, ...]] = []
    (valid_bundle / "README.md").write_text("changed in place", encoding="utf-8")
    changed_plan = build_install_plan("codex", valid_bundle, None)

    assert changed_plan.bundle_fingerprint != plan.bundle_fingerprint
    assert changed_plan.confirmation_token != plan.confirmation_token

    with pytest.raises(ConfirmationError, match="stale"):
        execute_install(plan, plan.confirmation_token, calls.append)

    assert calls == []


def test_execute_install_rejects_same_name_root_replacement_without_a_runner(
    valid_bundle: Path, tmp_path: Path
):
    plan = build_install_plan("codex", valid_bundle, None)
    original_root = tmp_path / "original-root"
    valid_bundle.rename(original_root)
    copytree(original_root, valid_bundle)
    calls: list[tuple[str, ...]] = []

    with pytest.raises(ConfirmationError, match="stale"):
        execute_install(plan, plan.confirmation_token, calls.append)

    assert calls == []


def test_execute_install_rejects_a_root_that_becomes_a_link_without_a_runner(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path
):
    plan = build_install_plan("codex", valid_bundle, None)
    calls: list[tuple[str, ...]] = []
    original_is_symlink = Path.is_symlink

    def root_is_link(path: Path) -> bool:
        return path == plan.bundle_root or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", root_is_link)

    with pytest.raises(ConfirmationError, match="stale"):
        execute_install(plan, plan.confirmation_token, calls.append)

    assert calls == []


def test_execute_install_rebuilds_a_forged_plan_before_any_runner(valid_bundle: Path):
    rendered = build_install_plan("codex", valid_bundle, None)
    forged = InstallPlan(
        host="codex",
        steps=(("untrusted-program", "--do-the-thing"),),
        confirmation_token="attacker-selected-token",
        network_required=False,
        bundle_root=rendered.bundle_root,
        bundle_fingerprint=rendered.bundle_fingerprint,
        bundle_root_identity=rendered.bundle_root_identity,
        bundle_name=rendered.bundle_name,
        source=None,
    )
    calls: list[tuple[str, ...]] = []

    with pytest.raises(ConfirmationError, match="stale"):
        execute_install(forged, forged.confirmation_token, calls.append)

    assert calls == []


@pytest.mark.parametrize(
    "field",
    (
        "steps",
        "host",
        "network_required",
        "source",
        "bundle_root",
        "bundle_fingerprint",
        "bundle_root_identity",
        "bundle_name",
        "confirmation_token",
    ),
)
def test_execute_install_rejects_each_altered_stored_plan_invariant(
    field: str, valid_bundle: Path, tmp_path: Path
):
    rendered = build_install_plan("hermes", valid_bundle, "owner/repository")
    replacements: dict[str, object] = {
        "steps": (("untrusted-program",),),
        "host": "unsupported-host",
        "network_required": False,
        "source": "owner/other-repository",
        "bundle_root": tmp_path / "other-bundle",
        "bundle_fingerprint": "0" * 64,
        "bundle_root_identity": (0, 0),
        "bundle_name": "other-skill",
        "confirmation_token": "attacker-selected-token",
    }
    forged = replace(rendered, **{field: replacements[field]})
    calls: list[tuple[str, ...]] = []

    with pytest.raises(ConfirmationError, match="stale"):
        execute_install(forged, forged.confirmation_token, calls.append)

    assert calls == []


def test_execute_install_accepts_a_normal_hermes_plan_after_reconstruction(valid_bundle: Path):
    plan = build_install_plan("hermes", valid_bundle, "owner/repository")
    calls: list[tuple[str, ...]] = []

    assert execute_install(plan, plan.confirmation_token, lambda step: calls.append(step) or 0) == 0

    assert calls == list(plan.steps)


def test_execute_install_rejects_a_file_that_changes_during_snapshot_capture(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path
):
    import agent_skillopt.installation as installation

    plan = build_install_plan("codex", valid_bundle, None)
    calls: list[tuple[str, ...]] = []
    original_update = installation._update_fingerprint_file
    changed = False

    def mutate_after_hash(digest: object, root: Path, path: Path):
        nonlocal changed
        state = original_update(digest, root, path)
        if path.name == "README.md" and not changed:
            changed = True
            path.write_text("changed during capture", encoding="utf-8")
        return state

    monkeypatch.setattr(installation, "_update_fingerprint_file", mutate_after_hash)

    with pytest.raises(ConfirmationError, match="stale"):
        execute_install(plan, plan.confirmation_token, calls.append)

    assert changed is True
    assert calls == []


def test_build_plan_rejects_identity_file_change_during_snapshot_capture(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path
):
    import agent_skillopt.installation as installation

    original_read_identity = installation._read_validated_bundle_name

    def mutate_identity_after_read(root: Path):
        result = original_read_identity(root)
        manifest_path = root / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["homepage"] = "https://example.test/changed-during-capture"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return result

    monkeypatch.setattr(installation, "_read_validated_bundle_name", mutate_identity_after_read)

    with pytest.raises(SpecError, match="changed during snapshot"):
        build_install_plan("codex", valid_bundle, None)


def test_build_plan_rejects_a_valid_file_mutated_at_the_final_validation_boundary(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path
):
    """Do not return the pre-validation fingerprint when a valid file races validation."""
    import agent_skillopt.installation as installation

    original_validate = installation.assert_valid_bundle
    validations = 0

    def validate_then_mutate_after_final_pre_snapshot(root: Path) -> None:
        nonlocal validations
        original_validate(root)
        validations += 1
        if validations == 3:
            (root / "README.md").write_text(
                "valid content changed at the final validation boundary", encoding="utf-8"
            )

    monkeypatch.setattr(
        installation,
        "assert_valid_bundle",
        validate_then_mutate_after_final_pre_snapshot,
    )

    with pytest.raises(SpecError, match="changed during snapshot"):
        build_install_plan("codex", valid_bundle, None)

    assert validations == 3


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


def test_install_execute_reports_a_runner_os_error_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, valid_bundle: Path, capsys
):
    plan = build_install_plan("codex", valid_bundle, None)

    def missing_host(*args: object, **kwargs: object) -> SimpleNamespace:
        raise FileNotFoundError("host command is absent")

    monkeypatch.setattr("agent_skillopt.cli.subprocess.run", missing_host)

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
                plan.confirmation_token,
            ]
        )
        == 1
    )

    error_output = capsys.readouterr().err
    assert "安装执行失败" in error_output
    assert "Traceback" not in error_output


def test_hermes_render_warning_describes_the_mutable_remote_content_boundary(
    valid_bundle: Path, capsys
):
    assert (
        main(
            [
                "install",
                "--host",
                "hermes",
                "--path",
                str(valid_bundle),
                "--source",
                "owner/repository",
            ]
        )
        == 0
    )

    warning = capsys.readouterr().err
    assert "执行时" in warning
    assert "远程内容" in warning
    assert "可能变化" in warning
