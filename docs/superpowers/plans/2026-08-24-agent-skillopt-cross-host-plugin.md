# Agent-SkillOpt Cross-Host Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Rebuild Agent-SkillOpt as an offline-safe Skill authoring plugin that creates one portable, four-host Skill package after an explicit preview-and-confirmation workflow.

**Architecture:** The repository root becomes an Agent Plugins v1 package with Codex and Claude Code marketplace adapters. A standard-library Python core parses a creation specification, renders a deterministic plan and confirmation token, atomically writes a new package only after confirmation, validates package contracts offline, and renders explicit host-installation commands. The installed agent-skillopt Skill is the conversational front door and invokes the bundled standalone scaffolder without a pip installation.

**Tech Stack:** Python 3.10+ standard library, pytest, Ruff, JSON, Markdown, GitHub Actions, Agent Plugins v1, Codex plugin marketplace metadata, Claude Code plugin metadata.

**Spec:** docs/superpowers/specs/2026-08-24-agent-skillopt-plugin-design.md

## Global Constraints

- Target project release version is 0.2.0; generated user packages start at 0.1.0.
- Runtime and bundled scripts use only the Python standard library; PyYAML is removed.
- Root plugin.json uses exactly https://agent-plugins.org/schemas/1.0.0/plugin.schema.json and no non-standard top-level component fields.
- All generated packages contain one canonical skills/name/SKILL.md and four host compatibility surfaces.
- Preview writes no target directory or temporary specification file.
- Apply requires a confirmation token derived from the exact normalized specification and output path, and never overwrites an existing target in 0.2.0.
- Validation and creation never make network calls, inspect secrets, install dependencies, or execute generated Skill scripts.
- Host installation is separately requested; execute requires a fresh explicit confirmation token and passes an argv tuple to a runner without shell=True.
- The root plugin's user-facing documentation remains Chinese-first. Every host-specific compatibility claim needs a current documented contract or locally reproducible evidence.
- Every production behavior follows red-green-refactor with pytest before implementation.

---

### Task 1: Replace the legacy training surface with the 0.2.0 CLI foundation

**Files:**

- Modify: pyproject.toml
- Modify: src/agent_skillopt/__init__.py
- Modify: src/agent_skillopt/__main__.py
- Modify: src/agent_skillopt/cli.py
- Modify: .gitignore
- Modify: scripts/validate.sh
- Modify: CONTRIBUTING.md
- Create: tests/test_cli.py
- Delete: src/agent_skillopt/config.py
- Delete: src/agent_skillopt/doctor.py
- Delete: src/agent_skillopt/init_project.py
- Delete: src/agent_skillopt/invocation.py
- Delete: src/agent_skillopt/manifest.py
- Delete: src/agent_skillopt/report.py
- Delete: src/agent_skillopt/assets/searchqa-deepseek.yaml
- Delete: presets/searchqa-deepseek.yaml
- Delete: examples/metrics.example.json
- Delete: examples/report.example.md
- Delete: tests/conftest.py
- Delete: tests/test_cli_help.py
- Delete: tests/test_config.py
- Delete: tests/test_doctor.py
- Delete: tests/test_exit_codes.py
- Delete: tests/test_init_project.py
- Delete: tests/test_invocation.py
- Delete: tests/test_manifest.py
- Delete: tests/test_report.py
- Delete: tests/fixtures/data/searchqa_split/.gitkeep
- Delete: tests/fixtures/fake-skillopt/configs/searchqa/default.yaml
- Delete: tests/fixtures/fake-skillopt/scripts/train.py
- Delete: tests/fixtures/fake-skillopt/skillopt/model/openai_compatible_backend.py
- Delete: tests/fixtures/report-run/manifest.json
- Delete: tests/fixtures/valid-config.yaml

**Interfaces:**

- Produces agent-skillopt commands preview, apply, validate, and install.
- main(argv: Sequence[str] | None = None) -> int remains the sole public CLI entry point.
- The foundation parser returns 0 for help, 2 for malformed command input, and does not retain legacy init, doctor, run, or report commands.

- [ ] **Step 1: Write failing CLI contract tests**

~~~python
from agent_skillopt.cli import main


def test_help_exposes_the_skill_package_workflow(capsys):
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "preview" in output
    assert "apply" in output
    assert "validate" in output
    assert "install" in output
    assert "Microsoft SkillOpt" not in output


def test_legacy_training_command_is_not_a_supported_subcommand(capsys):
    assert main(["run"]) == 2
    assert "invalid choice" in capsys.readouterr().err
~~~

- [ ] **Step 2: Run the new test and verify it fails for the missing command surface**

Run: python -m pytest tests/test_cli.py -v

Expected: the help test fails because the existing parser lists init, doctor, run, and report instead of the four 0.2.0 commands.

- [ ] **Step 3: Replace packaging metadata and implement the minimal parser**

Set the package version to 0.2.0, change the project description to cross-host Skill authoring, and remove the PyYAML runtime dependency. Keep pytest>=8.0 and ruff>=0.4.0 in the dev extra. Replace cli.py with an argparse parser that registers these arguments:

~~~python
preview = subcommands.add_parser("preview", help="预览将要创建的四宿主 Skill 包。")
preview.add_argument("--spec", required=True, help="JSON 规格文件路径，或 - 表示标准输入。")

apply = subcommands.add_parser("apply", help="在确认后创建四宿主 Skill 包。")
apply.add_argument("--spec", required=True)
apply.add_argument("--confirm", required=True)

validate = subcommands.add_parser("validate", help="离线验证一个四宿主 Skill 包。")
validate.add_argument("--path", type=Path, required=True)

install = subcommands.add_parser("install", help="渲染或显式执行宿主安装命令。")
install.add_argument("--host", choices=("codex", "claude", "hermes", "openclaw"), required=True)
install.add_argument("--path", type=Path, required=True)
install.add_argument("--execute", action="store_true")
install.add_argument("--confirm")
install.add_argument("--source", help="Hermes Git 安装源，例如 owner/repository。")
~~~

In this task the handlers may return 2 with a Chinese message that the selected operation is unavailable until its implementation task lands. Help itself must be complete and correct.

- [ ] **Step 4: Remove the retired training implementation and fixtures**

Delete the exact legacy modules, presets, examples, tests, and tracked fixtures listed above with targeted patches. Remove runs/ and .tmp-report/ from .gitignore; retain generic Python build and virtual-environment ignores. Rewrite CONTRIBUTING.md to require offline validation, no credentials, no unapproved installation, and tests before behavior changes. Keep compileall, pytest, and Ruff in scripts/validate.sh; Task 7 adds root package validation.

- [ ] **Step 5: Verify the foundation is green**

Run: python -m compileall src

Run: python -m pytest tests/test_cli.py -v

Run: python -m ruff check src tests

Expected: all commands exit 0 and no legacy test or fixture remains tracked.

- [ ] **Step 6: Commit the product-surface reset**

~~~bash
git add pyproject.toml src/agent_skillopt .gitignore scripts/validate.sh CONTRIBUTING.md tests
git add -u presets examples tests src/agent_skillopt
git commit -m "feat: reset Agent-SkillOpt for plugin authoring"
~~~

### Task 2: Build the pure-stdlib creation specification and preview planner

**Files:**

- Create: src/agent_skillopt/errors.py
- Create: src/agent_skillopt/models.py
- Create: src/agent_skillopt/naming.py
- Create: src/agent_skillopt/bundle.py
- Modify: src/agent_skillopt/cli.py
- Create: tests/test_bundle_plan.py

**Interfaces:**

- SkillSpec.from_json(text: str) -> SkillSpec parses exactly one JSON object with name, description, body, output_directory, optional version, and optional resources.
- normalize_skill_name(value: str) -> str accepts already normalized lowercase-hyphenated names and rejects all other names rather than silently renaming user output.
- build_plan(spec: SkillSpec) -> BundlePlan renders the complete package tree in memory and performs no writes.
- BundlePlan.confirmation_token is the first 16 lowercase hex characters of SHA-256 over canonical JSON containing the normalized spec and resolved output directory.
- render_preview(plan: BundlePlan) -> dict[str, object] returns JSON-serializable path, purpose, and token data without exposing a secret.

- [ ] **Step 1: Write failing planner tests**

~~~python
import json
from pathlib import Path

import pytest

from agent_skillopt.bundle import build_plan, render_preview
from agent_skillopt.errors import SpecError
from agent_skillopt.models import SkillSpec


def test_preview_builds_all_host_files_without_creating_the_target(tmp_path: Path):
    target = tmp_path / "skills" / "release-notes"
    spec = SkillSpec.from_json(json.dumps({
        "name": "release-notes",
        "description": "Draft release notes when a versioned change needs a concise summary.",
        "body": "Collect verified changes before drafting the release notes.",
        "output_directory": str(target),
    }))

    preview = render_preview(build_plan(spec))

    assert target.exists() is False
    assert preview["confirmation_token"]
    assert {item["path"] for item in preview["files"]} >= {
        "plugin.json",
        ".codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json",
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        "skills/release-notes/SKILL.md",
        "README.md",
        "tests/validate_bundle.py",
    }


def test_preview_rejects_an_unnormalized_skill_name(tmp_path: Path):
    with pytest.raises(SpecError, match="lowercase letters, digits, and hyphens"):
        SkillSpec.from_json(json.dumps({
            "name": "Release Notes",
            "description": "A valid sentence.",
            "body": "A valid body.",
            "output_directory": str(tmp_path / "release-notes"),
        }))
~~~

- [ ] **Step 2: Run the planner test and verify it fails for missing modules**

Run: python -m pytest tests/test_bundle_plan.py -v

Expected: collection fails because agent_skillopt.bundle, agent_skillopt.models, and agent_skillopt.errors do not exist.

- [ ] **Step 3: Implement strict data models and deterministic planning**

Create immutable dataclasses:

~~~python
@dataclass(frozen=True, slots=True)
class ResourceSpec:
    kind: Literal["reference", "script", "asset"]
    filename: str
    content: str


@dataclass(frozen=True, slots=True)
class SkillSpec:
    name: str
    description: str
    body: str
    output_directory: Path
    version: str = "0.1.0"
    resources: tuple[ResourceSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class PlannedFile:
    relative_path: PurePosixPath
    content: str
    purpose: str


@dataclass(frozen=True, slots=True)
class BundlePlan:
    output_directory: Path
    files: tuple[PlannedFile, ...]
    confirmation_token: str
~~~

Reject non-object JSON, unknown top-level keys, empty descriptions/bodies, invalid semantic versions, absolute or traversal resource names, duplicate generated paths, and a body that already starts with YAML frontmatter. Render the portable root manifest, Codex and Claude manifests, both marketplaces, one canonical Skill file, package README, and copied validator in a deterministic sorted order. Planning code must not call mkdir, write_text, subprocesses, or network APIs.

- [ ] **Step 4: Wire preview through stdin or a UTF-8 JSON file**

Implement _read_spec_argument(value: str) -> str: standard input is permitted only for --spec -, otherwise require a UTF-8 file. The preview handler prints one JSON object from render_preview and returns 0; malformed JSON or invalid specification returns 2 with a Chinese, secret-free error.

- [ ] **Step 5: Run focused regression checks**

Run: python -m pytest tests/test_bundle_plan.py tests/test_cli.py -v

Run: python -m ruff check src tests

Expected: all checks pass and preview never creates the selected output directory.

- [ ] **Step 6: Commit deterministic preview support**

~~~bash
git add src/agent_skillopt tests/test_bundle_plan.py tests/test_cli.py
git commit -m "feat: plan portable skill bundles offline"
~~~

### Task 3: Apply approved plans transactionally and preserve user files

**Files:**

- Modify: src/agent_skillopt/bundle.py
- Modify: src/agent_skillopt/errors.py
- Modify: src/agent_skillopt/cli.py
- Create: tests/test_bundle_apply.py

**Interfaces:**

- apply_plan(plan: BundlePlan, confirmation_token: str) -> tuple[Path, ...] writes only when the token is exact.
- WriteConflictError(path: Path) identifies an existing target without changing it.
- ConfirmationError identifies a missing or stale confirmation token.
- An apply operation writes into a unique sibling staging directory, validates the staged layout before publication, and atomically renames the staging directory to the absent target.

- [ ] **Step 1: Write failing approval and no-overwrite tests**

~~~python
import json
from pathlib import Path

import pytest

from agent_skillopt.bundle import apply_plan, build_plan
from agent_skillopt.errors import ConfirmationError, WriteConflictError
from agent_skillopt.models import SkillSpec


@pytest.fixture
def sample_spec(tmp_path: Path) -> SkillSpec:
    return SkillSpec.from_json(json.dumps({
        "name": "release-notes",
        "description": "Draft release notes from verified changes.",
        "body": "Collect verified changes before drafting the release notes.",
        "output_directory": str(tmp_path / "release-notes"),
    }))


def test_apply_requires_the_exact_preview_token(sample_spec: SkillSpec):
    plan = build_plan(sample_spec)

    with pytest.raises(ConfirmationError, match="confirmation token"):
        apply_plan(plan, "not-the-preview-token")

    assert sample_spec.output_directory.exists() is False


def test_apply_refuses_existing_target_without_changing_it(sample_spec: SkillSpec):
    sample_spec.output_directory.mkdir(parents=True)
    marker = sample_spec.output_directory / "user-file.txt"
    marker.write_text("preserve", encoding="utf-8")
    plan = build_plan(sample_spec)

    with pytest.raises(WriteConflictError):
        apply_plan(plan, plan.confirmation_token)

    assert marker.read_text(encoding="utf-8") == "preserve"


def test_apply_writes_a_complete_package_after_confirmation(sample_spec: SkillSpec):
    plan = build_plan(sample_spec)

    written = apply_plan(plan, plan.confirmation_token)

    assert sample_spec.output_directory / "plugin.json" in written
    assert (sample_spec.output_directory / "skills" / sample_spec.name / "SKILL.md").is_file()
~~~

- [ ] **Step 2: Run the test and verify it fails because apply is unavailable**

Run: python -m pytest tests/test_bundle_apply.py -v

Expected: collection or assertion failure because apply_plan, ConfirmationError, and WriteConflictError do not exist.

- [ ] **Step 3: Implement transactional apply**

Use tempfile.mkdtemp with a prefix based on the target name and a parent equal to plan.output_directory.parent. Do this only after resolving the parent and confirming it is writable. Write every PlannedFile under the staging directory only after verifying its resolved path remains below the staging root. Recheck that the final target is absent immediately before Path.replace.

On every exception, remove only the unique staging directory created for this operation and leave the target untouched. The public 0.2.0 CLI has no overwrite option. An existing target always returns status 2; users must select a new directory or deliberately manage old files themselves.

- [ ] **Step 4: Implement the apply CLI handler**

Read the same specification format as preview, rebuild its plan, compare --confirm to the recomputed token, and print a Chinese success line naming the final directory only after publication. Never print specification body content, resource content, or environment data in an error path.

- [ ] **Step 5: Run apply and complete-suite checks**

Run: python -m pytest tests/test_bundle_apply.py tests/test_bundle_plan.py tests/test_cli.py -v

Run: python -m pytest tests -v

Expected: all tests pass; a preview-only flow leaves no output or staging directory, and an existing file survives a rejected apply unchanged.

- [ ] **Step 6: Commit confirmed package writes**

~~~bash
git add src/agent_skillopt tests/test_bundle_apply.py tests
git commit -m "feat: create confirmed skill packages safely"
~~~

### Task 4: Add offline package validation and portable validator copies

**Files:**

- Create: src/agent_skillopt/validation.py
- Create: scripts/validate_bundle.py
- Modify: src/agent_skillopt/bundle.py
- Modify: src/agent_skillopt/cli.py
- Create: tests/conftest.py
- Create: tests/validate_bundle.py
- Create: tests/test_validation.py
- Create: tests/fixtures/minimal-skill/plugin.json
- Create: tests/fixtures/minimal-skill/.codex-plugin/plugin.json
- Create: tests/fixtures/minimal-skill/.agents/plugins/marketplace.json
- Create: tests/fixtures/minimal-skill/.claude-plugin/plugin.json
- Create: tests/fixtures/minimal-skill/.claude-plugin/marketplace.json
- Create: tests/fixtures/minimal-skill/skills/minimal-skill/SKILL.md
- Create: tests/fixtures/minimal-skill/README.md
- Create: tests/fixtures/minimal-skill/tests/validate_bundle.py

**Interfaces:**

- ValidationIssue(code: str, path: Path, message: str) represents one deterministic, secret-free structural failure.
- validate_bundle(root: Path) -> tuple[ValidationIssue, ...] performs no subprocess or network operation.
- assert_valid_bundle(root: Path) -> None raises BundleValidationError containing every issue code when validation fails.
- scripts/validate_bundle.py bundle-root exits 0 on success and 1 on structural errors.

- [ ] **Step 1: Write failing validator tests**

Create tests/conftest.py with reusable fixture roots:

~~~python
from pathlib import Path
from shutil import copytree

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def minimal_bundle(tmp_path: Path, project_root: Path) -> Path:
    destination = tmp_path / "minimal-skill"
    copytree(project_root / "tests" / "fixtures" / "minimal-skill", destination)
    return destination


@pytest.fixture
def valid_bundle(minimal_bundle: Path) -> Path:
    return minimal_bundle
~~~

Then create tests/test_validation.py:

~~~python
import json

from agent_skillopt.validation import validate_bundle


def test_minimal_fixture_is_a_valid_four_host_bundle(minimal_bundle):
    assert validate_bundle(minimal_bundle) == ()


def test_validator_rejects_manifest_identity_drift(minimal_bundle):
    codex_manifest = minimal_bundle / ".codex-plugin" / "plugin.json"
    document = json.loads(codex_manifest.read_text(encoding="utf-8"))
    document["version"] = "9.9.9"
    codex_manifest.write_text(json.dumps(document), encoding="utf-8")

    issues = validate_bundle(minimal_bundle)

    assert "MANIFEST_VERSION_MISMATCH" in {issue.code for issue in issues}


def test_validator_rejects_path_traversal_resource(minimal_bundle):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        "---\nname: minimal-skill\ndescription: Valid description.\n---\nRead [secret](../secret.md)",
        encoding="utf-8",
    )

    issues = validate_bundle(minimal_bundle)

    assert "SKILL_PATH_TRAVERSAL" in {issue.code for issue in issues}
~~~

- [ ] **Step 2: Run the validation tests and verify they fail for the missing validator**

Run: python -m pytest tests/test_validation.py -v

Expected: collection fails because agent_skillopt.validation does not exist.

- [ ] **Step 3: Implement strict JSON, frontmatter, and containment checks**

Use json.loads and a small frontmatter parser that accepts a first-line ---, exactly one name:, exactly one description:, and a closing ---. Do not reintroduce YAML dependencies. Validate the Agent Plugins schema URL exactly, one immediate child Skill directory, plugin/skill name equality, semantic versions, marketplace source structure, ./skills/ in host manifests, and the absence of .. path references in generated resource links. Compare only metadata fields that are present in a manifest; require name, version, and description in generated Codex and Claude manifests.

Have apply_plan call assert_valid_bundle(staging_root) before final publication. Create a self-contained root tests/validate_bundle.py and copy that exact file into every generated package at tests/validate_bundle.py. The copied file must contain no import that escapes the generated package root.

- [ ] **Step 4: Wire the public validate command and root wrapper**

agent-skillopt validate --path bundle prints VALID on success. On failure, print one CODE path: message line per issue to standard error and return 1. scripts/validate_bundle.py delegates to the same public validation entry point and accepts exactly one positional bundle root.

- [ ] **Step 5: Run validator regression checks**

Run: python -m pytest tests/test_validation.py tests/test_bundle_apply.py -v

Run: python scripts/validate_bundle.py tests/fixtures/minimal-skill

Expected: fixture validation exits 0; each corrupt manifest or path escape test fails only at the expected contract boundary.

- [ ] **Step 6: Commit offline validation**

~~~bash
git add src/agent_skillopt scripts/validate_bundle.py tests
git commit -m "feat: validate portable skill bundles offline"
~~~

### Task 5: Render explicit installation plans without hidden host mutations

**Files:**

- Create: src/agent_skillopt/installation.py
- Modify: src/agent_skillopt/models.py
- Modify: src/agent_skillopt/cli.py
- Create: tests/test_installation.py

**Interfaces:**

- HostName = Literal["codex", "claude", "hermes", "openclaw"] identifies one supported host.
- InstallPlan(host: HostName, steps: tuple[tuple[str, ...], ...], confirmation_token: str, network_required: bool) is an immutable rendered operation.
- build_install_plan(host: str, bundle_root: Path, source: str | None) -> InstallPlan supports codex, claude, hermes, and openclaw.
- execute_install(plan: InstallPlan, token: str, runner: Callable[[tuple[str, ...]], int]) -> int rejects an incorrect token and passes exactly the rendered argv tuple to the injected runner.

- [ ] **Step 1: Write failing host-installation tests**

~~~python
import pytest

from agent_skillopt.errors import ConfirmationError, SpecError
from agent_skillopt.installation import build_install_plan, execute_install


def test_codex_plan_adds_a_local_marketplace_then_the_plugin(valid_bundle):
    plan = build_install_plan("codex", valid_bundle, None)

    assert plan.steps == (
        ("codex", "plugin", "marketplace", "add", str(valid_bundle)),
        ("codex", "plugin", "add", "minimal-skill@minimal-skill"),
    )
    assert plan.network_required is False


def test_hermes_plan_requires_an_explicit_git_source(valid_bundle):
    with pytest.raises(SpecError, match="--source"):
        build_install_plan("hermes", valid_bundle, None)


def test_execute_install_requires_the_rendered_token(valid_bundle):
    plan = build_install_plan("openclaw", valid_bundle, None)
    calls = []

    with pytest.raises(ConfirmationError):
        execute_install(plan, "wrong", calls.append)

    assert calls == []


def test_execute_install_passes_each_argv_step_to_the_runner(valid_bundle):
    plan = build_install_plan("claude", valid_bundle, None)
    calls = []

    assert execute_install(plan, plan.confirmation_token, lambda step: calls.append(step) or 0) == 0

    assert calls == list(plan.steps)
~~~

- [ ] **Step 2: Run the test and verify the interfaces are absent**

Run: python -m pytest tests/test_installation.py -v

Expected: collection fails because agent_skillopt.installation does not exist.

- [ ] **Step 3: Implement argv-safe per-host plans**

Render these exact step tuples:

~~~python
codex_steps = (
    ("codex", "plugin", "marketplace", "add", str(root)),
    ("codex", "plugin", "add", f"{name}@{name}"),
)
claude_steps = (
    ("claude", "plugin", "marketplace", "add", str(root)),
    ("claude", "plugin", "install", f"{name}@{name}"),
)
hermes_steps = (
    ("hermes", "plugins", "install", source, "--no-enable"),
    ("hermes", "plugins", "enable", name),
)
openclaw_steps = (
    ("openclaw", "plugins", "install", str(root)),
    ("openclaw", "plugins", "inspect", name),
    ("openclaw", "gateway", "restart"),
)
~~~

Use str(root) as one argv item. network_required is true only for Hermes Git source installation. The executor runs each step through the injected runner after token verification and stops at the first nonzero status. It never invokes a shell.

- [ ] **Step 4: Implement render-first CLI behavior**

agent-skillopt install --host host --path root prints a JSON object with steps, network_required, and confirmation_token and performs no host mutation. --execute requires --confirm equal to the plan token. The CLI writes a concise warning when the selected path can require network access and delegates execution through:

~~~python
def _subprocess_runner(command: tuple[str, ...]) -> int:
    return subprocess.run(command, shell=False, check=False).returncode
~~~

- [ ] **Step 5: Run safe installation-plan tests**

Run: python -m pytest tests/test_installation.py -v

Run: python -m ruff check src tests

Expected: rendering does not call a runner, incorrect tokens call no runner, and a runner receives individual argv tokens rather than a shell string.

- [ ] **Step 6: Commit explicit installation support**

~~~bash
git add src/agent_skillopt tests/test_installation.py
git commit -m "feat: render explicit host installation plans"
~~~

### Task 6: Package Agent-SkillOpt itself as a four-host plugin

**Files:**

- Create: plugin.json
- Create: .codex-plugin/plugin.json
- Create: .agents/plugins/marketplace.json
- Create: .claude-plugin/plugin.json
- Create: .claude-plugin/marketplace.json
- Create: skills/agent-skillopt/SKILL.md
- Create: skills/agent-skillopt/scripts/scaffold_bundle.py
- Create: skills/agent-skillopt/references/portable-bundle-contract.md
- Create: skills/agent-skillopt/references/host-installation.md
- Create: skills/agent-skillopt/references/skill-authoring-rubric.md
- Create: skills/agent-skillopt/assets/skill-package-template/README.md
- Create: tests/test_plugin_package.py
- Modify: scripts/validate.sh
- Delete: SKILL.md

**Interfaces:**

- Root manifests identify agent-skillopt, version 0.2.0, the repository URL, MIT license, and the ./skills/ root where applicable.
- skills/agent-skillopt/scripts/scaffold_bundle.py resolves the repository root from its own path, adds root/src to sys.path, and delegates to agent_skillopt.cli.main without network or package installation.
- The installed Skill asks for a minimum brief, runs preview, waits for a user confirmation, invokes apply with the exact returned token, runs validation, and renders host installation commands without executing them.

- [ ] **Step 1: Write failing root-plugin contract tests**

~~~python
import json
import subprocess
import sys

from agent_skillopt.validation import validate_bundle


def test_repository_root_is_a_valid_agent_plugin_package(project_root):
    assert validate_bundle(project_root) == ()


def test_codex_and_claude_manifests_share_identity(project_root):
    codex = json.loads((project_root / ".codex-plugin" / "plugin.json").read_text())
    claude = json.loads((project_root / ".claude-plugin" / "plugin.json").read_text())

    assert codex["name"] == claude["name"] == "agent-skillopt"
    assert codex["version"] == claude["version"] == "0.2.0"


def test_scaffolder_wrapper_forwards_help_without_writing(project_root, tmp_path):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    result = subprocess.run(
        [sys.executable, str(wrapper), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "preview" in result.stdout
    assert list(tmp_path.iterdir()) == []
~~~

- [ ] **Step 2: Run the root-plugin test and verify it fails because manifests and payload are absent**

Run: python -m pytest tests/test_plugin_package.py -v

Expected: validate_bundle(project_root) reports missing-manifest issue codes and the wrapper path does not exist.

- [ ] **Step 3: Add compatible manifest and marketplace files**

Create a root Agent Plugins v1 plugin.json with only standard fields. Create Codex and Claude manifests with skills set to ./skills/. Create both marketplace files with name agent-skillopt and a single plugin entry whose local source path is ./. Preserve all metadata parity demanded by the validator. Do not add openclaw.plugin.json, Hermes plugin.yaml, MCP configuration, runtime hooks, or host-specific executable code.

- [ ] **Step 4: Write the installed Skill and its progressive resources**

Keep SKILL.md focused on the proposal-and-confirmation workflow. It must make these decisions explicit:

~~~markdown
- Ask for one missing requirement at a time.
- Keep the full specification in memory and pass it to scaffold_bundle.py preview through standard input.
- Show the returned directory, files, optional resources, and confirmation token.
- Stop until the user explicitly approves the proposal.
- Never hand-write package files as a fallback when the deterministic scaffolder is unavailable.
- After successful validation, render only the selected host install plan; execute nothing without a separate user request and matching token.
~~~

Move portable schema details, host install commands, and authoring-quality rubrics into the three named references. Put a concise generated-package README skeleton in the asset directory. The wrapper calculates Path(__file__).resolve().parents[3], adds the root src directory to sys.path only in its own process, and calls main().

- [ ] **Step 5: Validate the repository package and local Claude manifest**

Run: python scripts/validate_bundle.py .

Run: python -m pytest tests/test_plugin_package.py tests/test_validation.py -v

Run: claude plugin validate . --strict

Expected: offline validator and pytest pass. If the installed Claude CLI reports a schema issue, correct the manifest before continuing. Do not run codex plugin marketplace add, hermes plugins install, or any OpenClaw install command because they mutate user-level host state.

- [ ] **Step 6: Commit the installable plugin package**

~~~bash
git add plugin.json .codex-plugin .agents .claude-plugin skills scripts/validate.sh tests
git rm SKILL.md
git commit -m "feat: package Agent-SkillOpt for four hosts"
~~~

### Task 7: Rewrite product documentation, migration material, and CI evidence

**Files:**

- Modify: README.md
- Modify: docs/compatibility.md
- Modify: docs/security.md
- Create: docs/migration-v0.2.md
- Delete: docs/evaluation.md
- Delete: docs/experiment-checklist.md
- Delete: NOTICE
- Modify: .github/workflows/ci.yml
- Modify: CONTRIBUTING.md
- Create: tests/test_documentation_contract.py

**Interfaces:**

- README includes verified, copyable local installation and usage routes for Codex, Claude Code, Hermes Agent, and OpenClaw, plus the preview/confirm/validate/install boundary.
- Compatibility documentation distinguishes local structural validation from a manually verified installation per host.
- Security documentation describes no credentials, no default network, no script execution during validation, staging cleanup, and explicit installation risk.
- Migration documentation identifies bcbad16 as the last pre-0.2.0 main commit and directs legacy users to pin a 0.1.x revision.

- [ ] **Step 1: Write failing documentation contract tests**

~~~python
def test_readme_lists_each_supported_host_and_safe_creation_boundary(project_root):
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    for host in ("Codex", "Claude Code", "Hermes", "OpenClaw"):
        assert host in readme
    assert "preview" in readme
    assert "确认" in readme
    assert "validate" in readme
    assert "install" in readme
    assert "DEEPSEEK_API_KEY" not in readme


def test_legacy_training_docs_are_not_present(project_root):
    assert not (project_root / "docs" / "evaluation.md").exists()
    assert not (project_root / "docs" / "experiment-checklist.md").exists()
~~~

- [ ] **Step 2: Run the documentation test and verify it fails against the training README**

Run: python -m pytest tests/test_documentation_contract.py -v

Expected: the README test fails because the current home page describes Microsoft SkillOpt and the legacy documentation files still exist.

- [ ] **Step 3: Replace the documentation with accurate plugin guidance**

Keep the approved hero image and project name. Explain the one-core/four-adapter model and give a Chinese end-to-end example from a natural-language brief through preview, confirmation, validation, and explicit local install rendering. Include host commands exactly as rendered by build_install_plan; label Hermes Git installation and OpenClaw gateway restart as externally state-changing steps. Link the four official host/standard contracts and migration document.

Rewrite docs/compatibility.md with rows for repository structural validation, local Codex CLI metadata inspection, local Claude validate --strict, local Hermes CLI detection, and OpenClaw contract-only status until an operator provides runtime verification. Rewrite docs/security.md around the new offline and explicit-install boundaries. Delete the two evaluation documents and Microsoft SkillOpt NOTICE only after README and migration documentation no longer reference them.

- [ ] **Step 4: Update CI and the project validation script**

Extend scripts/validate.sh with:

~~~bash
python -m compileall src
python -m pytest tests -v
python -m ruff check src tests
python scripts/validate_bundle.py .
~~~

Keep Windows and Ubuntu Python 3.10/3.12 tests. Add a CI step that invokes python scripts/validate_bundle.py . after pytest. Keep the Ubuntu shell-syntax job. Do not download Claude, Codex, Hermes, or OpenClaw in CI; host CLIs are optional developer-environment evidence, not dependency-install steps.

- [ ] **Step 5: Run documentation, CI-equivalent, and diff checks**

Run: python -m pytest tests/test_documentation_contract.py -v

Run: bash -n scripts/validate.sh

Run: bash scripts/validate.sh

Run: git diff --check

Expected: all commands exit 0, the README makes no legacy provider or credential claim, and the docs accurately mark OpenClaw runtime status.

- [ ] **Step 6: Commit documentation and CI completion**

~~~bash
git add README.md docs .github/workflows/ci.yml scripts/validate.sh CONTRIBUTING.md tests/test_documentation_contract.py
git add -u docs NOTICE
git commit -m "docs: document cross-host skill creation"
~~~

### Task 8: Perform final product verification and record compatibility evidence

**Files:**

- Modify: docs/compatibility.md
- Modify: README.md only if a verified command requires correction
- Test: all tests/

**Interfaces:**

- No new public interface. This task validates the completed package on the exact repository root and records only evidence actually observed.

- [ ] **Step 1: Verify all offline behavior on the final tree**

Run:

~~~bash
python -m compileall src
python -m pytest tests -v
python -m ruff check src tests
python scripts/validate_bundle.py .
bash -n scripts/validate.sh
bash scripts/validate.sh
git diff --check
~~~

Expected: every command exits 0.

- [ ] **Step 2: Run host-provided read-only validation where available**

Run:

~~~bash
codex plugin list --available --json
claude plugin validate . --strict
hermes plugins --help
hermes skills --help
~~~

Expected: Codex and Hermes commands confirm installed CLI surfaces without modifying configuration. Claude validates the root manifest strictly. Do not run a marketplace add, install, enable, restart, or remote package fetch command in this task.

- [ ] **Step 3: Update only evidence-backed compatibility rows**

Record the command family/version and result for Codex, Claude Code, and Hermes only if the command was successfully run. Leave OpenClaw as contract validated; runtime not locally exercised when no local CLI is present. Do not infer an installation result from manifest shape alone.

- [ ] **Step 4: Request a review before publishing**

Use the code-review workflow to inspect the final diff, including the deleted training surface, manifest contract, confirmation gate, and documentation claims. Address only review findings supported by code or official contract evidence.

- [ ] **Step 5: Commit final verification evidence**

~~~bash
git add docs/compatibility.md README.md tests src scripts .github plugin.json .codex-plugin .claude-plugin .agents skills
git commit -m "test: verify cross-host plugin package"
~~~

## Plan Self-Review

- Tasks 1 through 5 provide the product surface, deterministic preview/apply protocol, no-overwrite behavior, offline validation, and explicit installation protocol required by the approved specification.
- Task 6 implements all package markers and the installed Skill without inventing native Hermes or OpenClaw runtime code.
- Task 7 removes the retired SkillOpt product documentation and records the breaking migration path.
- Task 8 prevents compatibility claims from exceeding observed evidence.
- Each new public production interface has a preceding failing pytest step, a focused passing test step, and a commit boundary.
- No task performs a paid API call, stores a credential, automatically installs a host plugin, or runs generated user code.
