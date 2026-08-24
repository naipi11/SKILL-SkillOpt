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

## Repair round 2 — independent review findings

- Added focused tests before implementation. Against the prior repair commit,
  `python -m pytest tests/test_validation.py -q` reported eight failures:
  five local or percent-encoded Markdown targets, optional host metadata drift,
  case-mismatched `Skills`, and suppressed independent checks after invalid root
  identity.
- Markdown target validation percent-decodes first. It permits only explicit
  remote schemes and `mailto`; `file:` URLs, unknown schemes, UNC paths, and
  POSIX/Windows absolute paths now fail closed, including reference-style
  targets.
- Root identity retains every Agent Plugins v1 optional metadata field.
  Codex/Claude manifests are compared for each optional field they provide:
  `author`, `homepage`, `repository`, `license`, `keywords`, and `extensions`.
- The canonical `skills` directory must be an exact-case, non-symlink regular
  directory. This closes Windows case-folding acceptance of `Skills`.
- Invalid root identity no longer suppresses host metadata/path checks,
  marketplace source/shape checks, or standalone Skill structure/frontmatter
  checks. Cross-manifest equality checks still run only when the root identity
  is available.
- The library validator and packaged standalone asset were updated together;
  the root test wrapper and minimal fixture remain byte-identical copies of the
  self-contained asset.

## Repair round 2 verification

All commands used
`C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe`.

- `python -m pytest tests/test_validation.py tests/test_bundle_apply.py -v` —
  44 passed.
- `python -m pytest tests -v` — 56 passed.
- `python -m compileall src` — passed.
- `python -m ruff check src tests scripts` — passed.
- `python scripts/validate_bundle.py tests/fixtures/minimal-skill` — `VALID`.
- `python tests/validate_bundle.py tests/fixtures/minimal-skill` — `VALID`.
- `git diff --check` — passed.
- SHA-256 of the packaged asset, root wrapper, and fixture wrapper — all
  `5C5F47DF2355C66E4F472C277A6A0530471A9D3BF542F4E3379AA2968CA961A6`.

## Safety and deferred scope

The validator performs only local filesystem and UTF-8/JSON/Markdown text
inspection. It has no PyYAML dependency and does not invoke generated content,
network access, host CLIs, user scripts, or subprocesses. Installation and root
plugin manifests, skills, and documentation remain untouched. As required, the
repository root is intentionally not yet a valid package; Task 6 supplies its
required manifests and Skill files.

## Repair evidence — validator portability and strict parsing

- Preserved the interrupted TDD additions in `tests/test_validation.py` and
  `tests/test_bundle_apply.py`. Before the repair,
  `python -m pytest tests/test_validation.py tests/test_bundle_apply.py -q`
  reported 12 failures: malformed or quoted frontmatter handling, external
  symlink reads, optional root metadata, packaged-resource loading,
  case-sensitive required paths, reference-style Markdown links, deterministic
  walk ordering, and generated escaped descriptions.
- The frontmatter parser now accepts only one-line unquoted plain scalars,
  complete JSON double-quoted strings, or YAML single-quoted strings with
  doubled apostrophes. It rejects malformed, multiline, block, and collection
  values.
- Validation now records escaping symlinks without reading their contents,
  uses exact directory-entry names for required files on case-insensitive
  filesystems, sorts `os.walk` directory and filename lists in place, and
  checks inline plus reference-style Markdown targets.
- The root manifest uses the closed Agent Plugins v1 field set with type checks
  for `author`, `homepage`, `repository`, `license`, `keywords`, and
  `extensions`. Optional `repository` and `license` are retained in root
  identity comparison.
- The standalone validator is now a package asset at
  `src/agent_skillopt/assets/validate_bundle.py`, read with
  `importlib.resources`. The identical self-contained file is used by the root
  test wrapper, fixture, and generated bundles; it imports no project package.
  Package data includes this asset for installed distributions.

## Repair verification

All commands used
`C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe`.

- `python -m pytest tests/test_validation.py tests/test_bundle_apply.py -q` —
  32 passed.
- `python -m pytest tests -v` — 44 passed.
- `python -m compileall src` — passed.
- `python -m ruff check src tests scripts` — passed.
- `python scripts/validate_bundle.py tests/fixtures/minimal-skill` — `VALID`.
- `python tests/validate_bundle.py tests/fixtures/minimal-skill` — `VALID`.
- `git diff --check` — passed.
