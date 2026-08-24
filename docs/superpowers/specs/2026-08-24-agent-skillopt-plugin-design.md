# Agent-SkillOpt Cross-Host Plugin Design

**Status:** Approved architecture design
**Date:** 2026-08-24
**Target release:** 0.2.0

## 1. Decision

Agent-SkillOpt will be rebuilt from a Microsoft SkillOpt training wrapper into a
Chinese-first, cross-host Skill authoring plugin. A user invokes the same
Agent-SkillOpt capability from Codex, Claude Code, Hermes Agent, or OpenClaw
to create a new, version-controllable Skill package that works across all four
hosts.

The product uses one portable Agent Plugins v1 core and thin host metadata
adapters. It does not maintain four copies of a generated Skill body.

## 2. Goals

- Let users create a complete, shareable Skill package through normal Agent
  interaction in any supported host.
- Generate all four host installation surfaces by default.
- Use a two-stage write workflow: preview first, write only after explicit
  user confirmation.
- Refuse to overwrite an existing target by default.
- Keep creation and validation offline; require a separate explicit request
  before rendering or executing an installation operation.
- Make generated packages self-contained and suitable for Git commits.
- Preserve the prior project's safety posture: no embedded credentials, no
  default network activity, no execution of generated user scripts during
  creation or validation.

## 3. Non-goals

- Continue Microsoft SkillOpt model-training, provider configuration,
  experiment execution, or evidence reporting from the 0.1.x product.
- Claim every host exposes exactly the same slash command or automatic-skill
  selection behavior.
- Install a generated package, download dependencies, or publish a package
  without an explicit user request and confirmation.
- Generate arbitrary executable tooling when a concise instruction-only Skill
  is enough.
- Add native OpenClaw runtime code, MCP servers, hooks, or credentials in
  version 0.2.0.

## 4. Repository package architecture

The Agent-SkillOpt repository is itself an installable multi-host plugin:

```text
Agent-SkillOpt/
├── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── .agents/plugins/
│   └── marketplace.json
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   └── agent-skillopt/
│       ├── SKILL.md
│       ├── scripts/
│       │   └── scaffold_bundle.py
│       ├── references/
│       │   ├── portable-bundle-contract.md
│       │   ├── host-installation.md
│       │   └── skill-authoring-rubric.md
│       └── assets/
│           └── skill-package-template/
├── scripts/
│   └── validate_bundle.py
├── tests/
│   ├── fixtures/
│   │   └── minimal-skill/
│   └── test_bundle_contract.py
├── docs/
│   └── migration-v0.2.md
└── README.md
```

### 4.1 Portable core

`plugin.json` is an Agent Plugins v1.0.0 manifest. It contains only fields
allowed by that standard, including the required schema identifier and name:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "agent-skillopt",
  "version": "0.2.0",
  "description": "Create review-gated portable Skill packages for coding agents.",
  "repository": "https://github.com/naipi11/Agent-SkillOpt",
  "license": "MIT"
}
```

Skills use the fixed portable location `skills/<skill-name>/SKILL.md`. The
portable manifest does not include a non-standard `skills` property.

### 4.2 Host adapters

| Host | Adapter | Runtime behavior in 0.2.0 |
| --- | --- | --- |
| Codex | `.codex-plugin/plugin.json` plus `.agents/plugins/marketplace.json` | Native Codex plugin marketplace and `skills/` root. |
| Claude Code | `.claude-plugin/plugin.json` plus `.claude-plugin/marketplace.json` | Native Claude Code plugin marketplace and namespaced Skill. |
| Hermes Agent | Root Agent Plugins v1 manifest | Hermes portable plugin with read-only, namespaced Skill content. |
| OpenClaw | Compatible bundle discovery | OpenClaw discovers the package as a Codex-compatible bundle because `.codex-plugin/` has precedence over root `plugin.json`; it loads the shared `skills/` content. |

No `openclaw.plugin.json` is included in 0.2.0. That would classify the
package as a native OpenClaw runtime plugin and require a separate runtime
entrypoint; this release intentionally ships a portable content bundle.

No Hermes `plugin.yaml` or native plugin code is included in 0.2.0. Hermes'
portable Agent Plugins implementation is the supported, least-coupled path for
this instruction-and-template product.

### 4.3 Marketplace identity

Both marketplace files use `agent-skillopt` as the marketplace and plugin
identifier, and point to the repository root with a `./` relative source. The
host manifests use the same identifier, version, repository URL, license, and
`./skills/` root. The validator rejects identity or version drift between
these files.

## 5. The generated user Skill package

By default Agent-SkillOpt creates one complete portable package under a
user-selected project-local directory. The package's initial version is
`0.1.0`; its plugin identity and its sole Skill identity use the normalized
lowercase-hyphenated name chosen by the user.

```text
<target>/<skill-name>/
├── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── .agents/plugins/
│   └── marketplace.json
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   └── <skill-name>/
│       └── SKILL.md
├── README.md
└── tests/
    └── validate_bundle.py
```

`references/`, `scripts/`, `assets/`, and additional test fixtures are added
only when the approved Skill design has a concrete use for them. Empty
directories, generic boilerplate, and duplicated manuals are not generated.

The generated `SKILL.md` always contains YAML frontmatter with a normalized
`name` and a discriminating `description`. Its body records the requested
outcome, non-obvious constraints, authorization boundaries, and only the
references or scripts required by the approved workflow.

## 6. Creation workflow

The `agent-skillopt` Skill is the interactive front door. It uses a bundled,
standard-library Python 3.10+ scaffolder, so creation needs no separate `pip`
installation, dependency download, or network access. If a host cannot run
Python, the Skill may still prepare and show a proposal, but it must not bypass
the deterministic scaffolder to write a package.

1. Collect the minimum brief: Skill name, desired outcome, when it should be
   used, important constraints, target directory, and meaningful validation.
2. Decide whether the Skill needs only `SKILL.md` or a concrete reference,
   template, script, or test resource. Do not create optional resources by
   default.
3. Pass the complete, in-memory creation specification to
   `scaffold_bundle.py preview`. The script returns a canonical proposal,
   exact output directory, full file tree, each file's purpose, all four host
   installation paths, and a confirmation token derived from the proposal.
   It writes no files in preview mode.
4. Stop and wait for the user to explicitly confirm the proposal.
5. On confirmation, invoke `scaffold_bundle.py apply` with the same complete
   specification and confirmation token. The script recomputes the token,
   then writes the package one file at a time with no-overwrite checks. If any
   destination exists, it stops before modifying any existing file and reports
   the conflicting path.
6. Run offline structural validation and report the result plus copyable host
   installation instructions.

The proposal phase never writes a target directory, temporary specification,
or partial package. A user can refine or cancel the proposal without any
filesystem mutation. `scaffold_bundle.py` accepts the specification through
standard input and never persists its input outside an approved package.

## 7. Validation and installation

### 7.1 Offline validator

`skills/agent-skillopt/scripts/scaffold_bundle.py` and
`scripts/validate_bundle.py` use only the Python standard library. The
scaffolder renders the proposal, derives and verifies its confirmation token,
and writes only approved package files. The validator never executes content
inside the package. Given a bundle root, it validates:

- Agent Plugins v1 manifest JSON and its exact `$schema` value.
- Required root and host adapter files.
- JSON parseability and allowed required metadata types.
- Equal plugin name, version, description, repository, and license where the
  relevant host manifest supports that field.
- `./skills/` references in Codex and Claude manifests.
- Marketplace entries that point to the local package root with a `./` path.
- One immediate `skills/<skill-name>/SKILL.md` directory matching the manifest
  name.
- YAML frontmatter name/description and absence of unfinished scaffold markers.
- No relative path that contains `..`, and no resolved package path outside the
  bundle root.

The validator returns a nonzero status on any violation and emits actionable,
secret-free messages. It does not inspect environment variables, perform web
requests, start a subprocess other than itself, or load generated scripts.

### 7.2 Explicit host installation

Generated README instructions offer a render-only install plan first. Actual
installation must be separately requested and reconfirmed for one selected
host.

| Host | Explicit installation path |
| --- | --- |
| Codex | Add the package's marketplace with `codex plugin marketplace add`, then add the named plugin with `codex plugin add`. |
| Claude Code | Add the marketplace with `claude plugin marketplace add`, then use `claude plugin install <plugin>@<marketplace>`. |
| Hermes Agent | Install a Git-hosted portable package with `hermes plugins install <owner>/<repo> --no-enable`, then explicitly enable it. |
| OpenClaw | Install a local bundle with `openclaw plugins install <bundle-root>`, inspect it, then explicitly restart the gateway. |

The creation Skill may render these commands and explain their effects. It
must not execute them until the user explicitly asks to install the selected
package into the selected host and confirms the exact command.

## 8. Migration from 0.1.x

Version 0.2.0 is a deliberate breaking product change. It removes the
Microsoft SkillOpt-specific Python package modules, training presets, test
fixtures, training report examples, and P0/P1/P2 evaluation documentation.

`docs/migration-v0.2.md` states that users needing the previous training
wrapper should pin the last 0.1.x commit or release before upgrading. It also
states that a 0.1.x `agent-skillopt.yaml` is not read or migrated by 0.2.0.

The new README replaces training instructions with four-host installation,
creation, validation, and explicit-install walkthroughs. It remains
Chinese-first and uses the repository's current name, `Agent-SkillOpt`.

## 9. Test and release evidence

All new behavior follows red-green-refactor. CI remains on Windows and Ubuntu
and performs only offline checks.

Required automated coverage:

- A valid minimal generated Skill package passes the validator.
- Each malformed portable or host manifest produces the expected failure.
- Cross-manifest identity drift is rejected.
- Missing or malformed Skill frontmatter is rejected.
- Path traversal and package-root escape are rejected.
- A no-overwrite conflict leaves existing user files unchanged.
- A proposed, unconfirmed creation leaves the output directory absent.
- Optional template/script/reference resources are absent unless requested.
- The repository's own package passes the same validator.

When the corresponding host CLI is present in a development environment, the
release checklist also runs host-provided read-only validation, including
`claude plugin validate --strict`. Codex, Hermes, and OpenClaw install and
enable commands are not run automatically because they alter user-level host
state. The compatibility matrix distinguishes these structural checks from a
manually verified host installation.

## 10. Acceptance criteria

The refactor is complete only when all of the following hold:

1. The repository root is a valid Agent Plugins v1 package plus Codex and
   Claude Code marketplace/plugin package.
2. All four supported hosts have accurate, copyable installation and invocation
   documentation with no unsupported capability claims.
3. The installed Agent-SkillOpt Skill guides a user through proposal,
   confirmation, package creation, and offline validation.
4. A generated package contains one canonical Skill body and all required
   host manifests without duplicated Skill instructions.
5. Existing user files are preserved unless an explicit overwrite path is
   approved.
6. No creation or validation path reads a secret, installs dependencies,
   makes a network request, or executes user-provided code.
7. Full CI and the offline package validator pass on the repository root and
   fixture package.

## 11. Contract sources

- Agent Plugins v1 portable manifest and fixed `skills/` discovery:
  <https://agent-plugins.org/specification>
- Codex plugin marketplace and `.codex-plugin/plugin.json` conventions:
  verified against the repository's installed Codex CLI 0.147.0 and bundled
  plugin marketplace fixtures on 2026-08-24.
- Claude Code plugin schema and marketplace layout:
  <https://code.claude.com/docs/en/plugins-reference>
- Hermes portable Agent Plugins support:
  <https://hermes-agent.nousresearch.com/docs/developer-guide/plugins>
- OpenClaw bundle detection and precedence:
  <https://docs.openclaw.ai/plugins/bundles>
