# Agent-SkillOpt Design

**Date:** 2026-08-19

## Goal

Build Agent-SkillOpt, a Chinese-first reproducible integration kit for Microsoft SkillOpt and OpenAI-compatible model providers. It must diagnose a supported setup before it spends API credits, preserve reproducibility metadata for every run, and avoid maintaining a fork of SkillOpt's optimisation core.

## Product Position

Agent-SkillOpt is an integration layer, not a replacement training framework. It owns:

- Chinese documentation and ready-to-copy presets for DeepSeek and compatible endpoints.
- Local environment, configuration, data, and upstream compatibility diagnostics.
- Safe construction of an upstream invocation, including a no-network dry run.
- A normalized run manifest and report generated from an upstream result directory.
- A tested compatibility matrix for operating systems and agent hosts.

It does not own or fork Microsoft's optimisation loop, mutate files inside a SkillOpt checkout, claim universal Agent compatibility, or make real network/API calls by default.

## Scope

### P0: Trustworthy foundation

P0 produces an installable Python package with the agent-skillopt command. It includes:

1. Actual project licensing, attribution, security policy, contribution guide, and Chinese README.
2. A declarative YAML configuration format plus a shipped searchqa-deepseek preset.
3. agent-skillopt doctor, which checks Python, configuration, required environment variables, a local SkillOpt checkout, the configured entry script, and supported upstream version metadata without printing secrets.
4. agent-skillopt init, which writes a commented project configuration and a .gitignore entry for run artefacts. Existing files are never overwritten without --force.
5. Test and static verification: Python compilation, unit tests, shell syntax validation, and Windows/Linux GitHub Actions jobs.

### P1: Safe execution and reproducibility

P1 adds:

1. agent-skillopt run --dry-run, which validates all inputs and renders the exact upstream command without launching a subprocess or making a network call.
2. A real run gate: agent-skillopt run requires both a configured API key and --allow-network; it writes a manifest before launching the upstream process.
3. A run manifest containing the Agent-SkillOpt version, upstream checkout revision, config hash, data path/hash when available, model identifier, endpoint hostname only, seed, invocation arguments, and start/end status. API keys and full endpoint query strings are excluded.
4. agent-skillopt report, which consumes an upstream result directory and emits JSON and Markdown summaries without fabricating metrics when expected result files are absent.
5. A compatibility matrix containing only environments exercised by CI or recorded manual validation.

### P2: Evaluation discipline and durable evidence

P2 adds:

1. A schema for baseline/candidate/holdout metrics with explicit sample counts and cost fields.
2. Report warnings when validation and final-test results are mixed or when required evidence is absent.
3. A sanitized example report and an experiment checklist for external API/data use.
4. Templates for publishing a reproducibility bundle: config, manifests, aggregate metrics, anonymized best skill, and provenance.

P2 does not include a billed live experiment, a proprietary data upload, or a claimed performance improvement. Those require separate user approval of an exact model, budget, concurrency, and data-handling scope.

## User-facing Interface

The package exposes this stable command surface:

    agent-skillopt init [--path PATH] [--preset searchqa-deepseek] [--force]
    agent-skillopt doctor --config PATH [--json]
    agent-skillopt run --config PATH --dry-run
    agent-skillopt run --config PATH --allow-network
    agent-skillopt report --run-dir PATH [--output-dir PATH]

Exit status meanings:

- 0: requested operation completed and all required checks passed.
- 2: configuration or environment validation failed.
- 3: an execution gate was not explicitly acknowledged.
- 4: the upstream subprocess completed unsuccessfully.

Doctor returns all discoverable failures in one invocation. Human-readable output is concise; --json is stable enough for CI and agent consumption.

## Configuration Contract

Configuration is YAML and has these top-level sections:

    version: 1
    skillopt:
      root: ../SkillOpt
      entry_script: scripts/train.py
      required_ref: 9c776fcb51ae681c046d6f619b55e5f337d4f900
    provider:
      api_key_env: DEEPSEEK_API_KEY
      base_url: https://api.deepseek.com
      model: deepseek-v4-flash
    data:
      task: searchqa
      path: data/searchqa
    run:
      output_root: runs
      seed: 42
      upstream_args: []
    safety:
      require_allow_network: true

api_key_env identifies an environment-variable name only. The value must never be stored in YAML, manifests, logs, test fixtures, or README examples. base_url is validated as HTTPS by default; a non-HTTPS endpoint requires an explicit opt-in field for local development.

The preset is a tested starting point, not a promise that every provider/model combination works. The model and endpoint remain user-configurable because providers change their catalogues independently.

## Architecture

    CLI
     +-- config: YAML loading, schema validation, secret-safe normalization
     +-- doctor: local Python/upstream/data/provider environment diagnostics
     +-- invocation: deterministic upstream command rendering and gated subprocess launch
     +-- manifest: atomic creation and final status update of run metadata
     +-- report: result discovery, normalized metrics, Markdown/JSON output
     +-- safety: redaction, HTTPS policy, --allow-network acknowledgement

The implementation package lives under src/agent_skillopt; tests live under tests. Each module has a focused public API so it can be tested without an API key, network access, or a real SkillOpt installation. Subprocess execution is injected behind an interface for tests.

## Upstream Integration

The wrapper targets a local, user-controlled Microsoft SkillOpt checkout. Doctor verifies the configured root, entry script, generic OpenAI-compatible backend files, and Git revision when available. For a compatible provider it passes the role backend selections as normal upstream arguments and supplies OPENAI_COMPATIBLE_BASE_URL, OPENAI_COMPATIBLE_API_KEY, and OPENAI_COMPATIBLE_MODEL only to the child process environment; it never edits azure_openai.py or any upstream file.

SearchQA setup delegates to the upstream materialization tooling when present. Agent-SkillOpt ships no copied benchmark data and does not silently download data. A missing data directory is a diagnostic failure with a precise remediation command.

The first DeepSeek-compatible training target is Microsoft SkillOpt commit 9c776fcb51ae681c046d6f619b55e5f337d4f900 on main. The generic OpenAI-compatible training backend landed after the v0.2.0 PyPI release, so v0.2.0 is explicitly unsupported for this path. A different revision with the required feature files is reported as unverified rather than silently accepted; a checkout without them is rejected.

## Safety and Cost Controls

- --dry-run is the default safe workflow and must make no network call.
- A real invocation requires --allow-network; this prevents accidental billable use from a copied command.
- No command prints an API-key value. Any environment-variable display reports only whether it is set.
- Manifests record endpoint hostname, not secrets or query parameters.
- Remote endpoint use is documented as a potential data-export event; users must review provider data policies before sending task trajectories.
- The package does not estimate a monetary total from stale hard-coded pricing. It records provider-reported usage when present and otherwise marks cost as unavailable.

## Testing and Acceptance Criteria

The test suite must prove the following without live credentials:

1. Invalid YAML and missing required fields return validation exit code 2.
2. Doctor detects absent upstream files and never emits an injected secret value.
3. Init refuses to overwrite an existing configuration unless --force is supplied.
4. Run --dry-run produces a deterministic command and makes no subprocess/network invocation.
5. Real run refuses to launch without --allow-network or the configured environment variable.
6. A gated run writes a redacted manifest before the subprocess starts and records the final status.
7. Report produces explicit missing-evidence warnings rather than invented scores.
8. Compilation, unit tests, linting, and shell syntax checks run in CI on Windows and Linux.

## Repository Layout

    Agent-SkillOpt/
    +-- src/agent_skillopt/
    +-- tests/
    +-- presets/
    +-- docs/
    |   +-- compatibility.md
    |   +-- security.md
    |   +-- superpowers/
    +-- scripts/
    +-- .github/workflows/
    +-- pyproject.toml
    +-- README.md
    +-- LICENSE
    +-- NOTICE

## Non-goals

- No direct integration test that consumes an API key or paid tokens.
- No automatic upstream cloning, patching, model downloading, or dataset downloading.
- No model-specific performance claim without a checked-in, sanitized evidence bundle.
- No assertion that a single SKILL.md works identically across every agent host.

## Definition of Done for This Reconstruction

The repository is named and documented as Agent-SkillOpt; a fresh Python environment can install it; the listed commands expose help text; unit and smoke tests pass without credentials; CI configuration covers Windows and Linux; the README provides an accurate, copyable no-network walkthrough; and no generated file, document, or log contains an API secret.
