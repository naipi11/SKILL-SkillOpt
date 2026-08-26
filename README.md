<div align="center">
  <img src="docs/assets/agent-skillopt-hero.gif" alt="Agent-SkillOpt: safe, reproducible, evidence-first Skill authoring" width="100%">
</div>

<h1 align="center">Agent-SkillOpt</h1>

<p align="center">Create and validate portable Skill packages for four coding-agent hosts with one explicit confirmation.</p>

<p align="center"><strong>English</strong> | <a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <a href="https://github.com/naipi11/Agent-SkillOpt/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/naipi11/Agent-SkillOpt/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-2ea44f.svg"></a>
</p>

Agent-SkillOpt is an offline-first Skill authoring tool. It combines a portable
[Agent Plugins v1](https://agent-plugins.org/specification) core with thin
adapters for the Codex marketplace, Claude Code marketplace, Hermes Agent, and
OpenClaw-compatible bundle discovery. Creation and validation do not access the
network, read secrets, install dependencies, or execute generated Skill scripts.

## Install the current Agent-SkillOpt plugin

This section installs the released `agent-skillopt` plugin itself, not the
`release-notes` bundle created in the example below. These commands access the
network and change user-level marketplace, cache, plugin, or gateway state.
Review `naipi11/Agent-SkillOpt` before running them. The current release is
`v0.3.0`, published at commit
`028e76a10d4c672936d65681c4f871323932d0f6`. The compatibility matrix records
the previous `v0.2.1` host snapshot, the current release's offline evidence,
unverified hosts, and recovery boundaries. None of these records prove that
the Skill scaffolder has run successfully in every project or host.

### Codex

```powershell
codex plugin marketplace add naipi11/Agent-SkillOpt --ref 028e76a10d4c672936d65681c4f871323932d0f6
codex plugin add agent-skillopt@agent-skillopt
```

### Claude Code

```powershell
claude plugin marketplace add naipi11/Agent-SkillOpt --scope user
claude plugin install agent-skillopt@agent-skillopt --scope user --yes
```

The prior local `v0.2.1` plugin was installed and enabled in user scope.
Claude Code reports that an install or update requires a restart before it is
loaded. This release has not been separately host-installed in this evidence
refresh, so installation metadata does not prove that the current session has
loaded or run the Skill.

### Hermes Agent

Hermes installations should be fixed to an exact 40-character commit SHA. For
the current `v0.3.0` release, use commit
`028e76a10d4c672936d65681c4f871323932d0f6`:

```powershell
hermes plugins install naipi11/Agent-SkillOpt --ref 028e76a10d4c672936d65681c4f871323932d0f6 --no-enable
hermes plugins show agent-skillopt
hermes plugins enable agent-skillopt
```

An instance that runs this sequence should keep `allow_tool_override: false`;
the plugin takes effect in the next Hermes session. A successful installation
does not prove that it has run in a new session.

### OpenClaw

OpenClaw is not installed on this machine. The following is a documented
compatibility flow for a local, validated bundle root, **not evidence of a
local successful installation**. Replace `<bundle-root>` with an absolute
directory that has passed `validate`, then run it in the target environment:

```text
openclaw plugins install <bundle-root>
openclaw plugins inspect agent-skillopt
openclaw gateway restart
```

`main` is mutable: later commits can change the content behind the same ref.
The current Codex CLI can use `--ref`, while Claude's GitHub shorthand uses its
default branch (currently `main`); do not describe these as the same ref
semantics. Claude's remote marketplace source accepts branch/tag refs and does
not promise a commit-SHA-pinned installation. A release tag is also only a Git
ref, not inherently immutable: use it only when protected and trusted, then
record and verify the resolved 40-character commit SHA in release notes.
According to the Claude Code plugin contract, Git marketplaces can refresh in
the background according to their settings; remote fetching can occur after
initial configuration even without a new explicit command. Explicit installs
and updates also access the network and alter host state. The previous installation
status snapshot completed on 2026-08-25 is in the [compatibility matrix](docs/compatibility.md);
a single-machine result does not generalize to every version or host. Running
the installed scaffolder requires Python 3.10+; obtaining a marketplace plugin
does not mean that the scaffolder has already run.

### Failure checks and recovery

These multi-step installs are **not atomic**. A marketplace may be added while
plugin installation fails; Hermes may download a plugin before enablement; or
OpenClaw may install a plugin before gateway restart fails. Stop the remaining
steps and inspect state read-only: use `codex plugin list` for Codex,
`claude plugin list` for Claude Code, and `hermes plugins show agent-skillopt`
for Hermes. After checking the state and error, follow the host's official
documentation to remove leftovers or retry only the missing step. OpenClaw was
not verified locally, so this repository does not invent inspection or removal
commands for it; use the target environment's OpenClaw documentation and real
output.

### Maintainer release rule

`pyproject.toml`, `src/agent_skillopt/__init__.py`, `plugin.json`,
`.codex-plugin/plugin.json`, and `.claude-plugin/plugin.json` currently all
declare static version `0.3.0`. Any release that changes remote plugin content
must increment all five versions together and record the resolved
40-character commit SHA in release notes; otherwise installed hosts may treat
the result as the same version and skip the update.

## Safely create a local Skill package

The workflow for a new locally generated Skill package is: natural-language
brief → stdin `preview` → inspect the returned directory, files, and token →
**one explicit confirmation** → exact `apply` → offline `validate` → render
`install` for the selected host. Actual host execution is a separate external
state change and requires another explicit request plus the token matching the
new installation plan.

The following is a local `preview` for a `release-notes` Skill. In a source
checkout, `$skillDirectory` is the repository's absolute path. In an installed
plugin, resolve the absolute directory containing the `SKILL.md` currently in
use instead; do not assume the current directory or checkout location.

```powershell
$skillDirectory = (Resolve-Path .\skills\agent-skillopt).Path
$bundleRoot = Join-Path (Get-Location) 'out\release-notes'
$spec = @'
{
  "name": "release-notes",
  "description": "Draft concise release notes from verified changes.",
  "body": "Collect verified changes before drafting release notes.",
  "output_directory": "REPLACE_WITH_ABSOLUTE_BUNDLE_ROOT"
}
'@.Replace('REPLACE_WITH_ABSOLUTE_BUNDLE_ROOT', $bundleRoot.Replace('\\', '\\\\'))
$spec | python "$skillDirectory\scripts\scaffold_bundle.py" preview --spec -
```

Inspect `output_directory`, `files`, and `confirmation_token` in the returned
JSON. Preview does not create the output directory. Optional resources are
paths in `files`; there is no top-level `resources` field. Only if all of that
is correct should you reuse the token unchanged:

```powershell
$spec | python "$skillDirectory\scripts\scaffold_bundle.py" apply --spec - --confirm <preview-token>
python "$skillDirectory\scripts\scaffold_bundle.py" validate --path "$bundleRoot"
```

`apply` never overwrites an existing directory. It writes and validates in a
unique sibling staging directory, then publishes without clobbering the target;
on failure it cleans up its own staging directory and reports any residual
directory blocked by a system lock. Do not install a bundle that fails
validation.

## Review and evaluate a generated Skill

Every generated bundle includes at least one offline case under `tests/cases/`
and instructions in `tests/README.md`. Add `test_cases` to the JSON spec when a
Skill needs positive or negative assertions. A case contains a `prompt`,
`required_contains`, and `forbidden_contains` list.

Run the static quality and security review first:

```powershell
python "$skillDirectory\scripts\scaffold_bundle.py" review --path "$bundleRoot"
```

`review` produces a deterministic JSON report with `quality_score`, security
status, findings, and explicit `executed: false` / `network_accessed: false`
flags. It never executes the Skill, model, host, script, or hook. High-risk
secret-like values, instruction overrides, destructive operations, and similar
patterns block the report; medium-risk shell, network, or environment access
patterns require human review.

After a user or host has collected responses separately, save them as:

```json
{"responses": {"case-name": "response text"}}
```

Then score the responses without running a model or Skill:

```powershell
python "$skillDirectory\scripts\scaffold_bundle.py" evaluate `
  --path "$bundleRoot" --responses responses.json
```

The evaluation score is a reproducible required/forbidden-text check, not a
claim that every host or model will produce the same result.

## Render an installation plan only

Local bundle plans for Codex, Claude, and OpenClaw do not need a source. The
following command returns only argv arrays, a network flag, and an installation
token; it is **PLAN ONLY**:

```powershell
python "$skillDirectory\scripts\scaffold_bundle.py" install --host <codex|claude|openclaw> --path "$bundleRoot"
```

Hermes requires an explicit `<owner>/<repository>` Git source. This also only
renders a plan; it does not access the network or execute a host command. The
optional `--source-ref` accepts only an exact 40-character commit SHA and maps
it to Hermes `--ref`:

```powershell
python "$skillDirectory\scripts\scaffold_bundle.py" install --host hermes --path "$bundleRoot" --source <owner>/<repository> --source-ref <40-char-sha>
```

Every step is an argv tuple: a path remains one argument rather than a
shell-concatenated string. Replace `<bundle-root>` with an absolute directory
already previewed and validated, and replace `release-notes` with a normalized
bundle name. The table below precisely matches the `build_install_plan` output:

| Host | Planned argv (execute only after later, independent confirmation) |
| --- | --- |
| [Codex](https://help.openai.com/en/articles/20001256-plugins-in-codex/) | `codex plugin marketplace add <bundle-root>`<br>`codex plugin add release-notes@release-notes` |
| [Claude Code](https://code.claude.com/docs/en/plugins-reference) | `claude plugin marketplace add <bundle-root>`<br>`claude plugin install release-notes@release-notes` |
| [Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins) | `hermes plugins install <owner>/<repository> --ref <40-char-sha> --no-enable`<br>`hermes plugins enable release-notes` |
| [OpenClaw](https://docs.openclaw.ai/plugins/bundles) | `openclaw plugins install <bundle-root>`<br>`openclaw plugins inspect release-notes`<br>`openclaw gateway restart` |

Hermes requires an explicit `<owner>/<repository>` Git source, not a bare
index name, local path, or URL. It accesses the network and its remote content
is mutable; `--source-ref` is optional but recommended, and can only be an
exact 40-character commit SHA. **Hermes Git install/enable and OpenClaw gateway
restart are external state changes; rendering a plan must never execute them
automatically.** Codex and Claude marketplace/add/install steps also alter
user-level host state. The installation token binds the host, validated path,
content snapshot, commands, and Hermes source, but does not pin a remote
commit or replace source review and authorization.

## Local validation

```powershell
python -m compileall src
python -m pytest tests -v
python scripts/validate_bundle.py .
python -m ruff check src tests
```

CI runs offline checks on Python 3.10 and 3.12 for Windows and Ubuntu, and does
not download host CLIs. See the [compatibility matrix](docs/compatibility.md),
[security boundaries](docs/security.md), and [0.2.0 migration notes](docs/migration-v0.2.md).
License: MIT.
