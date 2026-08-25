# Agent-SkillOpt Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a tested, Chinese-first Agent-SkillOpt CLI that safely integrates a pinned Microsoft SkillOpt checkout with OpenAI-compatible providers.

**Architecture:** Agent-SkillOpt is a small Python package with a standard-library argparse CLI. It loads a safe YAML project configuration, validates a local upstream checkout, renders an upstream command, gates live subprocess execution, and preserves redacted reproducibility evidence. The package uses an OpenAI-compatible child-process environment rather than patching SkillOpt.

**Tech Stack:** Python 3.10+, PyYAML, pytest, Ruff, GitHub Actions, argparse, dataclasses, subprocess.

**Spec:** docs/superpowers/specs/2026-08-19-agent-skillopt-design.md

## Global Constraints

- Python version floor is 3.10.
- The supported compatible-training baseline is Microsoft SkillOpt commit 9c776fcb51ae681c046d6f619b55e5f337d4f900, not PyPI v0.2.0.
- No production or test fixture file may contain an API-key value.
- Dry-run mode must neither launch a subprocess nor make a network call.
- Live execution requires --allow-network and the configured environment variable.
- The wrapper must never edit upstream files.
- All new production behavior is introduced red-green-refactor with pytest.

---

### Task 1: Package foundation, legal identity, and offline verification

**Files:**

- Create: pyproject.toml
- Create: src/agent_skillopt/__init__.py
- Create: src/agent_skillopt/__main__.py
- Create: src/agent_skillopt/cli.py
- Create: tests/test_cli_help.py
- Create: scripts/validate.sh
- Create: .github/workflows/ci.yml
- Create: .gitignore
- Create: LICENSE
- Create: NOTICE
- Create: README.md
- Create: docs/security.md
- Create: docs/compatibility.md
- Create: SKILL.md

**Interfaces:**

- Produces an agent-skillopt console script bound to agent_skillopt.cli:main.
- main(argv: Sequence[str] | None = None) returns a process status and exposes subcommand placeholders.

- [ ] **Step 1: Write the failing CLI help test**

    from agent_skillopt.cli import main

    def test_help_returns_zero_and_names_product(capsys):
        assert main(["--help"]) == 0
        assert "Agent-SkillOpt" in capsys.readouterr().out

- [ ] **Step 2: Run the test to verify it fails because the package does not exist**

    Run: python -m pytest tests/test_cli_help.py -v
    Expected: collection/import failure for agent_skillopt.

- [ ] **Step 3: Add minimal package metadata and CLI implementation**

    Use a src-layout setuptools project, package version 0.1.0, requires-python >=3.10, PyYAML >=6.0, and optional development dependencies pytest >=8.0 and ruff >=0.4.0. Implement argparse with visible init, doctor, run, and report subcommands whose temporary handlers return 0. Keep all display text free of provider secrets.

- [ ] **Step 4: Add release hygiene and offline CI files**

    Add MIT license text for this project and NOTICE attribution to Microsoft SkillOpt. Add a Chinese README that describes the no-network workflow and explicitly states that v0.2.0 is unsupported for compatible training. Add a compatibility matrix and security policy. Add SKILL.md with a compatibility declaration rather than a universal-agent claim. Add scripts/validate.sh with Python compilation, pytest, and Ruff. Add CI jobs for Windows and Ubuntu on Python 3.10 and 3.12; Ubuntu also runs shell syntax validation.

- [ ] **Step 5: Run the test and static checks**

    Run: python -m pytest tests/test_cli_help.py -v
    Expected: PASS.

    Run: python -m compileall src
    Run: python -m ruff check src tests
    Run: bash -n scripts/validate.sh
    Expected: all commands exit 0.

- [ ] **Step 6: Commit the foundation**

    Run: git add pyproject.toml src tests scripts .github .gitignore LICENSE NOTICE README.md docs/security.md docs/compatibility.md SKILL.md
    Run: git commit -m "feat: scaffold Agent-SkillOpt CLI"

### Task 2: Typed configuration and secret-safe diagnostics

**Files:**

- Create: src/agent_skillopt/errors.py
- Create: src/agent_skillopt/models.py
- Create: src/agent_skillopt/config.py
- Create: tests/test_config.py
- Create: presets/searchqa-deepseek.yaml

**Interfaces:**

- ConfigurationError(message: str) signals invalid user configuration.
- ProjectConfig contains skillopt, provider, data, run, and safety dataclasses.
- load_config(path: Path) returns ProjectConfig and raises ConfigurationError for malformed or missing required fields.
- redacted_config_summary(config: ProjectConfig) returns a dictionary that emits no secret value and stores endpoint hostname only.

- [ ] **Step 1: Write failing configuration tests**

    def test_load_config_requires_provider_key_environment_name(tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("version: 1\nprovider: {}\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="api_key_env"):
            load_config(path)

    def test_redacted_summary_never_contains_environment_secret(tmp_path):
        config = load_config(write_valid_config(tmp_path))
        summary = redacted_config_summary(config)
        assert "test-secret-value" not in json.dumps(summary)
        assert summary["provider"]["base_url_host"] == "api.deepseek.com"

- [ ] **Step 2: Run the tests to verify they fail for missing symbols**

    Run: python -m pytest tests/test_config.py -v
    Expected: import failure for agent_skillopt.config.

- [ ] **Step 3: Implement minimal schema validation**

    Use yaml.safe_load only. Require version 1, an HTTPS provider base URL unless safety.allow_insecure_localhost is true and the host is loopback, a nonempty api_key_env identifier, model, SkillOpt root, entry script, required_ref, upstream config, data path, output_root, and integer seed. Reject provider.api_key. Resolve relative paths relative to the YAML file. The shipped preset uses DEEPSEEK_API_KEY, https://api.deepseek.com, deepseek-v4-flash, the pinned upstream commit, configs/searchqa/default.yaml, data/searchqa_split, and runs.

- [ ] **Step 4: Run configuration tests and Ruff**

    Run: python -m pytest tests/test_config.py -v
    Run: python -m ruff check src tests
    Expected: PASS and no lint violations.

- [ ] **Step 5: Commit configuration support**

    Run: git add src/agent_skillopt tests/test_config.py presets/searchqa-deepseek.yaml
    Run: git commit -m "feat: validate safe project configuration"

### Task 3: Doctor and non-destructive initialization

**Files:**

- Create: src/agent_skillopt/doctor.py
- Create: src/agent_skillopt/init_project.py
- Modify: src/agent_skillopt/cli.py
- Create: tests/test_doctor.py
- Create: tests/test_init_project.py
- Create: tests/conftest.py

**Interfaces:**

- Diagnostic(level, code, message, remediation) is JSON serializable.
- run_doctor(config: ProjectConfig, environ: Mapping[str, str]) returns a list of Diagnostic items and performs only local checks.
- initialize_project(destination: Path, preset_name: str, force: bool) writes agent-skillopt.yaml and adds run output ignores.

- [ ] **Step 1: Write failing doctor tests**

    def test_doctor_reports_missing_compatible_backend_and_redacts_secret(fake_config):
        fake_environment = {"DEEPSEEK_API_KEY": "test-secret-value"}
        diagnostics = run_doctor(fake_config, fake_environment)
        rendered = json.dumps([item.to_dict() for item in diagnostics])
        assert "UPSTREAM_COMPAT_BACKEND_MISSING" in rendered
        assert "test-secret-value" not in rendered

    def test_doctor_accepts_feature_complete_fake_checkout(fake_config, fake_skillopt_root):
        diagnostics = run_doctor(fake_config.with_root(fake_skillopt_root), {})
        assert not [item for item in diagnostics if item.level == "error"]

- [ ] **Step 2: Write failing initialization tests**

    def test_init_refuses_to_overwrite_existing_config(tmp_path):
        target = tmp_path / "agent-skillopt.yaml"
        target.write_text("existing", encoding="utf-8")
        with pytest.raises(FileExistsError):
            initialize_project(tmp_path, "searchqa-deepseek", force=False)

    def test_init_writes_preset_and_run_ignore(tmp_path):
        path = initialize_project(tmp_path, "searchqa-deepseek", force=False)
        assert path.name == "agent-skillopt.yaml"
        assert "runs/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")

- [ ] **Step 3: Run tests to verify they fail for missing modules**

    Run: python -m pytest tests/test_doctor.py tests/test_init_project.py -v
    Expected: collection/import failures.

- [ ] **Step 4: Implement local diagnostics and initializer**

    Check the configured root, scripts/train.py, selected upstream config, data path, generic compatible backend file, and a Git HEAD revision. The doctor reports a required-ref mismatch as warning and a missing feature file as error. It reports a configured key environment variable only as set or missing. The initializer copies the shipped preset, preserves existing .gitignore lines, and never downloads or clones anything. Wire human and JSON doctor output plus init CLI flags.

- [ ] **Step 5: Run tests and CLI smoke checks**

    Run: python -m pytest tests/test_doctor.py tests/test_init_project.py -v
    Run: python -m agent_skillopt --help
    Run: python -m agent_skillopt init --help
    Run: python -m agent_skillopt doctor --help
    Expected: all commands exit 0.

- [ ] **Step 6: Commit P0 diagnostics**

    Run: git add src/agent_skillopt tests presets
    Run: git commit -m "feat: add doctor and safe project initialization"

### Task 4: Deterministic invocation rendering and execution gates

**Files:**

- Create: src/agent_skillopt/invocation.py
- Create: src/agent_skillopt/manifest.py
- Modify: src/agent_skillopt/cli.py
- Create: tests/test_invocation.py
- Create: tests/test_manifest.py

**Interfaces:**

- RenderedInvocation(command, child_environment, working_directory, run_directory) contains the local launch contract.
- render_invocation(config, config_path, now) returns RenderedInvocation and makes no subprocess or network call.
- require_execution_permission(config, allow_network, environ) raises ExecutionGateError when authorization or key is absent.
- create_manifest(invocation, config, status) writes redacted JSON atomically.
- execute(invocation, runner) updates the manifest around a child process.

- [ ] **Step 1: Write failing dry-run and gate tests**

    def test_dry_run_command_uses_compatible_backends_and_no_secret(valid_config, config_path):
        invocation = render_invocation(valid_config, config_path, FIXED_TIME)
        assert "--optimizer_backend" in invocation.command
        assert "openai_compatible" in invocation.command
        assert "test-secret-value" not in " ".join(invocation.command)
        assert invocation.child_environment["OPENAI_COMPATIBLE_BASE_URL"] == "https://api.deepseek.com"

    def test_live_execution_requires_explicit_network_acknowledgement(valid_config):
        fake_environment = {"DEEPSEEK_API_KEY": "test-secret-value"}
        with pytest.raises(ExecutionGateError, match="--allow-network"):
            require_execution_permission(valid_config, False, fake_environment)

    def test_live_execution_requires_configured_key_environment(valid_config):
        with pytest.raises(ExecutionGateError, match="DEEPSEEK_API_KEY"):
            require_execution_permission(valid_config, True, {})

- [ ] **Step 2: Run tests to verify they fail for missing invocation code**

    Run: python -m pytest tests/test_invocation.py tests/test_manifest.py -v
    Expected: collection/import failures.

- [ ] **Step 3: Implement rendering, gate, and manifest behavior**

    Render a command that invokes the configured Python interpreter and upstream scripts/train.py from the configured SkillOpt root. Pass --config, --optimizer_backend openai_compatible, --target_backend openai_compatible, --optimizer_model, --target_model, --data_path, --out_root, --seed, and user-approved upstream_args. Inject OPENAI_COMPATIBLE_BASE_URL, OPENAI_COMPATIBLE_API_KEY, and OPENAI_COMPATIBLE_MODEL only into the child environment. Store only endpoint hostname, command arguments without keys, config SHA-256, upstream Git revision, model, seed, and timestamps in manifest.json. Do not run any child process for dry-run. Map a nonzero child result to exit code 4.

- [ ] **Step 4: Wire CLI run output and test redacted lifecycle**

    Add run --dry-run and run --allow-network. Dry-run prints a shell-escaped display command and a missing-key warning but returns 0 when every non-secret prerequisite is valid. The live path writes manifest.json with status started before runner invocation and status succeeded or failed afterward. Tests use an injected fake runner; no test creates a network client.

- [ ] **Step 5: Run all invocation tests and dry-run fixture**

    Run: python -m pytest tests/test_invocation.py tests/test_manifest.py -v
    Run: python -m agent_skillopt run --config tests/fixtures/valid-config.yaml --dry-run
    Expected: exit 0, rendered command visible, no API-key value visible.

- [ ] **Step 6: Commit safe run support**

    Run: git add src/agent_skillopt tests
    Run: git commit -m "feat: add gated compatible-provider execution"

### Task 5: Evidence-first reporting and P2 metric contract

**Files:**

- Create: src/agent_skillopt/report.py
- Modify: src/agent_skillopt/cli.py
- Create: tests/test_report.py
- Create: examples/metrics.example.json
- Create: examples/report.example.md
- Create: docs/evaluation.md
- Create: docs/experiment-checklist.md

**Interfaces:**

- Metric(split, score, samples, cost_usd) represents only reported evidence.
- build_report(run_directory) reads manifest.json and optional metrics.json without inferring scores.
- write_report(report, output_directory) writes report.json and report.md.

- [ ] **Step 1: Write failing evidence tests**

    def test_report_warns_when_metrics_are_absent(tmp_path):
        write_manifest(tmp_path)
        report = build_report(tmp_path)
        assert "METRICS_UNAVAILABLE" in {warning.code for warning in report.warnings}
        assert report.metrics == []

    def test_report_rejects_holdout_metric_without_samples(tmp_path):
        write_manifest(tmp_path)
        (tmp_path / "metrics.json").write_text('{"holdout": {"score": 0.8}}', encoding="utf-8")
        report = build_report(tmp_path)
        assert "HOLDOUT_SAMPLES_REQUIRED" in {warning.code for warning in report.warnings}

- [ ] **Step 2: Run report tests to verify they fail for missing report module**

    Run: python -m pytest tests/test_report.py -v
    Expected: collection/import failure.

- [ ] **Step 3: Implement strict metric parsing and report writers**

    Require a numeric score and integer samples for every accepted metric. Accept a null cost_usd, but never synthesize price or usage. Include raw upstream summary metadata only under a clearly labeled field. Markdown writes an Evidence warnings section before metrics. CLI report prints paths to generated files and returns validation exit code 2 for a missing manifest.

- [ ] **Step 4: Add sanitized examples and research guidance**

    Include a synthetic metrics example with baseline, candidate, and holdout data. Documentation must distinguish validation selection from final holdout evaluation and require a separate authorization for paid live experiments.

- [ ] **Step 5: Run reporting tests and CLI smoke check**

    Run: python -m pytest tests/test_report.py -v
    Run: python -m agent_skillopt report --run-dir tests/fixtures/report-run --output-dir .tmp-report
    Expected: exit 0 and JSON/Markdown reports created; remove .tmp-report after inspection.

- [ ] **Step 6: Commit reporting and P2 evidence support**

    Run: git add src/agent_skillopt tests examples docs
    Run: git commit -m "feat: add evidence-first experiment reports"

### Task 6: Full verification, documentation audit, and release readiness

**Files:**

- Modify: README.md
- Modify: docs/compatibility.md
- Modify: docs/security.md
- Modify: docs/evaluation.md
- Modify: tests as needed for verified behavior only

**Interfaces:**

- No new public interface. This task validates the completed command surface and documentation claims.

- [ ] **Step 1: Write final regression tests for command failure exit codes**

    def test_doctor_returns_two_when_configuration_is_invalid(tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("version: 1\n", encoding="utf-8")
        assert main(["doctor", "--config", str(bad)]) == 2

    def test_run_returns_three_without_allow_network(valid_config_path, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")
        assert main(["run", "--config", str(valid_config_path)]) == 3

- [ ] **Step 2: Run the tests to verify completed CLI exit codes**

    Run: python -m pytest tests -v
    Expected: PASS.

- [ ] **Step 3: Audit documentation against behavior**

    Ensure every copyable command is no-network by default, every supported upstream statement names the required feature baseline, and every use of a key uses only an environment-variable name. Search all tracked text for common key prefixes and remove any match that is not a placeholder name.

- [ ] **Step 4: Run complete verification**

    Run: python -m compileall src
    Run: python -m pytest tests -v
    Run: python -m ruff check src tests
    Run: bash -n scripts/validate.sh
    Run: git diff --check
    Expected: all commands exit 0.

- [ ] **Step 5: Commit verified reconstruction**

    Run: git add README.md docs tests src presets examples scripts .github SKILL.md pyproject.toml
    Run: git commit -m "docs: complete Agent-SkillOpt reconstruction"

## Plan Self-Review

- Every P0 requirement is covered by Tasks 1 through 3.
- Every P1 requirement is covered by Task 4, including an explicit non-network dry run and manifest lifecycle.
- Every P2 requirement is covered by Task 5 and final audit in Task 6.
- No task makes a paid API call, clones or patches the upstream repository, or stores a secret.
- All production modules have an associated failing-test step before implementation.
