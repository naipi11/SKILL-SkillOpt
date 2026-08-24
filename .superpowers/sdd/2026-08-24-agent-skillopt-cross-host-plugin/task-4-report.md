# Task 4 — Offline package validation and portable validator copies

## Scope delivered

- Added `agent_skillopt.validation` with deterministic `ValidationIssue`,
  `validate_bundle`, `assert_valid_bundle`, and aggregate `BundleValidationError`.
- Validated the exact Agent Plugins v1 schema URL; required root, Codex, and
  Claude manifests; identity and semantic-version consistency; host
  `./skills/` declarations; marketplace local-source shape; one matching
  immediate Skill directory; strict two-field frontmatter; unfinished markers;
  Markdown parent-path references; and resolved paths which escape the bundle.
- Added `agent-skillopt validate --path BUNDLE`: it emits `VALID` on success or
  one `CODE path: message` line per structural issue on standard error and exits
  one.
- Added `scripts/validate_bundle.py`, which resolves this checkout's `src/`
  before delegating to the public CLI command.
- Replaced the generated validator stub with the exact self-contained
  `tests/validate_bundle.py` copy. The minimal fixture carries the same copy;
  it imports only Python standard-library modules.
- Gated `apply_plan` by formal validation of its staging directory immediately
  before no-clobber publication.

## TDD evidence

1. Added the fixture and validator contract tests before `validation.py`.
   `python -m pytest tests/test_validation.py -v` failed at collection with
   `ModuleNotFoundError: No module named 'agent_skillopt.validation'`.
2. Added the validator and re-ran that test module: 7 passed.
3. Added CLI, exact portable-copy, and staging-publication tests before wiring
   the CLI/copy/gate code. The focused run failed at the expected four
   boundaries: validate returned the placeholder status, root copy was absent,
   and invalid staged content was published.
4. Wired those interfaces and re-ran: 19 focused tests passed.
5. Direct wrapper verification exposed an import-boundary failure: invoking
   `scripts/validate_bundle.py` selected an older globally installed package
   whose CLI lacked `validate`. Added a subprocess regression test first; it
   failed with exit status 2 and that legacy CLI usage text. The wrapper now
   prepends this checkout's `src/` before importing the public CLI; its focused
   regression passed.

## Fresh verification

All commands used
`C:\Users\33384\Documents\ChatGPT\Agent-SkillOpt\.venv\Scripts\python.exe`.

- `python -m pytest tests/test_validation.py tests/test_bundle_apply.py -v` —
  20 passed.
- `python -m pytest tests -v` — 32 passed.
- `python -m compileall src scripts tests` — passed.
- `ruff check src tests scripts` — passed.
- `python scripts/validate_bundle.py tests/fixtures/minimal-skill` — `VALID`.
- `python tests/validate_bundle.py tests/fixtures/minimal-skill` — `VALID`.
- `git diff --check` — passed.

## Safety and deferred scope

The validator performs only local filesystem and UTF-8/JSON/Markdown text
inspection. It has no PyYAML dependency and does not invoke generated content,
network access, host CLIs, user scripts, or subprocesses. Installation and root
plugin manifests, skills, and documentation remain untouched. As required, the
repository root is intentionally not yet a valid package; Task 6 supplies its
required manifests and Skill files.
