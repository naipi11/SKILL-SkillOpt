# Task 5 — Explicit, confirmation-gated host installation plans

## Scope delivered

- Added immutable `HostName` and `InstallPlan` models plus
  `agent_skillopt.installation`.
- `build_install_plan()` first requires the formal portable-bundle validator,
  then reads the validated root manifest identity. It never guesses an
  installation name from the directory name.
- Rendered exact argv-tuple plans for Codex, Claude, Hermes, and OpenClaw.
  Every local bundle path and Hermes source remains one argv element. Hermes
  alone requires an explicit non-option, non-whitespace Git source and is the
  only plan marked `network_required`.
- `execute_install()` accepts only an exact deterministic plan token, passes
  the rendered tuples unchanged to its injected runner, and returns on the
  first nonzero runner status. It never builds a shell command.
- Replaced the placeholder CLI install handler. Default `install` emits
  deterministic JSON (`steps`, `network_required`, `confirmation_token`) and
  performs no host action. `--execute` is gated by that exact token; the real
  runner is the explicit `subprocess.run(command, shell=False, check=False)`
  adapter. Hermes render/execute requests also receive a concise network
  warning on standard error.

## TDD evidence

1. Added `tests/test_installation.py` before creating the production module.
   `C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe -m pytest tests/test_installation.py -v`
   failed at collection as expected with
   `ModuleNotFoundError: No module named 'agent_skillopt.installation'`.
2. Added the models, renderer, executor, and CLI wiring. The first green
   focused run passed 18 tests; added further source-option rejection and
   exact Claude/OpenClaw argv assertions, then the final focused run passed
   21 tests.
3. The focused suite covers invalid formal bundles, all exact host tuples,
   Hermes-only source/network behavior, deterministic tokens, paths containing
   spaces as one argv element, wrong/missing confirmation with zero runner
   calls, first-failure termination, render-only CLI subprocess prevention,
   and the real CLI adapter's `shell=False`/`check=False` invocation under a
   subprocess mock.

## Fresh verification

All Python checks used
`C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe`.

- `python -m pytest tests/test_installation.py -v` — 21 passed.
- `python -m ruff check src tests` — passed.
- `python -m compileall -q src tests` — passed.
- `python -m pytest tests -v` — 98 passed.
- With `PYTHONPATH` set to this checkout's `src`, `python -m agent_skillopt
  --help` displayed `preview`, `apply`, `validate`, and `install`.
- With that same source precedence, `python -m agent_skillopt install --host
  hermes --path tests\\fixtures\\minimal-skill --source owner/repository`
  rendered deterministic JSON and the Hermes network warning. It omitted
  `--execute`, so it made no host mutation or network request.
- `git diff --check` — passed.

## Safety and residual risk

No real Codex, Claude, Hermes, or OpenClaw installation, enablement,
inspection, restart, remote fetch, or other host-state mutation was run. All
execution coverage uses injected runners or a mocked `subprocess.run`.

The shared `.venv` has an older globally installed 0.1.x `agent-skillopt`.
Invoking `python -m agent_skillopt` without source precedence loads that stale
package and shows its old command surface; tests remain authoritative through
their checkout `src` path, and the smoke check explicitly set `PYTHONPATH` to
the current checkout. Packaging/reinstallation verification belongs to a
later task.

## Repair round 1 — batch-wrapper arguments and stale bundle plans

### Scope delivered

- Treat Windows CMD metacharacters (`&`, `|`, redirections, parentheses,
  caret, percent/expansion markers), either quote, and control/line characters
  as unsafe in every dynamic argv value. The direct path, canonical path,
  Hermes source, validated bundle name, and plugin reference are checked before
  an `InstallPlan` is constructed; rendered steps are checked again before a
  runner can receive them. This remains active on every platform because a
  host executable can resolve to a Windows batch wrapper independently of the
  test host.
- `InstallPlan` now immutably records the canonical direct bundle root, a
  deterministic sorted full-tree content fingerprint, and root filesystem
  identity. The confirmation-token payload binds all three, the host, network
  flag, and exact argv tuples. CLI JSON intentionally remains limited to
  `steps`, `network_required`, and `confirmation_token`.
- Snapshot creation first runs the formal no-link validator on the supplied
  direct root, resolves it, validates that canonical root, then fingerprints
  only guarded regular files/directories through `lstat` checks and sorted
  `os.walk`. It neither invokes package content nor accesses a network.
- `execute_install()` performs its token check first, then revalidates,
  re-resolves, and re-fingerprints the stored root before invoking any runner.
  Root relocation/replacement, a newly invalid link, or in-place content drift
  raises `ConfirmationError` with zero runner calls.
- Hermes retains the documented `owner/repository` source form. Its token
  binds the exact source text, while the warning now clearly says execution
  fetches mutable remote content and that this is a trust boundary rather than
  a remote-revision pin.
- The CLI now converts a runner `OSError` such as a missing host executable
  into a concise `安装执行失败` diagnostic and exit status 1, without a traceback.

### TDD and verification evidence

1. Added focused regressions before repair. The initial
   `python -m pytest tests/test_installation.py -v` collected 43 tests and
   produced 22 expected failures: unfiltered CMD characters, absent canonical
   root fields, stale content/root/link plans reaching runners, uncaught runner
   `OSError`, and the insufficient Hermes trust-boundary warning.
2. Added the guarded snapshot/fingerprint/identity implementation and source
   filters. The focused installation suite then passed 43 tests, including
   relative `.` planning followed by a different CWD, same-name root
   replacement with identical copied content, simulated root-link invalidation,
   in-place `README.md` drift, and zero-runner stale rejection.
3. Fresh checks, using
   `C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe`:

   - `python -m pytest tests/test_installation.py -v` — 43 passed.
   - `python -m ruff check src tests` — passed.
   - `python -m compileall -q src tests` — passed.
   - `python -m pytest tests -q` — 120 passed.
   - `git diff --check` — passed.
   - With `PYTHONPATH` set to this checkout's `src`, `python -m agent_skillopt
     --help` and the Hermes render-only command from the original verification
     both succeeded. The latter omitted `--execute`, printed the mutable-remote
     warning and JSON plan, and performed no host mutation or network fetch.

### Repair residual risk

The local plan is checked immediately before the first runner call; an
uncooperative concurrent process can still modify filesystem content in the
narrow OS-level interval after that check and before a host consumes it. Hermes
remote content is intentionally not revision-pinned, so its execution-time
fetch remains a user-visible trust boundary. The shared virtual environment's
stale installed 0.1.x CLI remains a packaging-environment issue; source-first
checks are used until a later installation/packaging task addresses it.

## Repair round 2 — provenance reconstruction and coherent snapshots

### Scope delivered

- Added immutable bundle_name and source fields to InstallPlan. The
  confirmation token now binds the validated identity, canonical root, content
  fingerprint, root identity, selected host, explicit Hermes source, network
  flag, and exact argv tuples. The CLI JSON contract remains only steps,
  network_required, and confirmation_token.
- execute_install() first checks the caller token against the supplied object,
  then independently rebuilds a complete plan from the current formally
  validated canonical root and the explicit stored source. It accepts only
  exact dataclass equality with that rebuilt plan and executes the rebuilt
  tuples, never the untrusted object's tuples. Unsupported hosts, non-Hermes
  sources, missing Hermes sources, forged names/roots/fingerprints/identities,
  changed network flags, altered steps, and arbitrary matching tokens therefore
  fail before any runner call.
- A snapshot now keeps no-follow directory metadata before and after direct and
  canonical validation, reads plugin.json through a stable descriptor,
  fingerprints sorted files through lstat plus pre-read fstat, post-read fstat,
  and post-read lstat comparisons, and performs a second complete no-data
  metadata traversal. It rejects added, removed, relinked, replaced, or
  metadata-changing entries instead of mixing identity and tree states.
- When O_NOFOLLOW is available, file descriptors use it. On platforms such as
  this Windows host where it is unavailable, no descriptor data is read until
  its fstat exactly matches the prior no-follow lstat; post-read
  descriptor/path comparisons and the second traversal fail closed on an
  unexpected link or replacement.

### TDD and fresh evidence

1. Added direct-forgery and mutation tests before the repair. The initial
   focused run collected 55 tests: 8 new tests failed (forged argv/token,
   altered stored invariants, and mid-capture mutation), while 47 existing
   tests passed. The missing explicit source/bundle_name fields also made the
   direct forged-plan constructor fail at the intended interface boundary.
2. Added a further identity/tree mixed-snapshot regression after reviewing the
   first green implementation. It initially failed because changing the root
   manifest after name capture but before hashing silently produced a mixed
   snapshot. The snapshot now carries the stable identity-file metadata and
   compares it with the hashed-tree observation; that regression passed after
   the repair.
3. Fresh commands, all with
   C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe:

   - python -m pytest tests/test_installation.py -v — 56 passed.
   - python -m ruff check src tests — passed.
   - python -m compileall -q src tests — passed.
   - python -m pytest tests -q — 133 passed.
   - git diff --check — passed.
   - With PYTHONPATH set to this checkout's src, python -m agent_skillopt
     --help and the Hermes render-only command from earlier rounds succeeded.
     The latter omitted --execute, rendered the explicit plan/warning, and
     performed no host mutation, remote fetch, enablement, inspection, or
     restart.

### Unresolved boundary

The final reconstruction/snapshot check is immediately before the first
runner call, but it cannot atomically cover a same-privilege process changing
the local tree after that check and before a host consumes it. This narrow
external-host consumption interval is an unavoidable operating-system boundary
and is not claimed to be pinned or transactional. Hermes still intentionally
fetches mutable owner/repository content at execution time; the rendered
warning presents that separate remote trust boundary explicitly. The shared
virtual environment's stale installed 0.1.x CLI also remains a later packaging
task concern; source-priority smoke checks avoid treating it as current code.

## Repair round 3 — close the final-validation snapshot boundary

### Scope delivered

- A bundle snapshot now captures a guarded identity/name, fingerprint, root
  identity, and full-tree metadata observation before the final formal
  validation and captures a second guarded observation immediately after it.
  The snapshots must match in canonical root, name, fingerprint, root identity,
  and every observed entry before a plan is returned.
- The returned InstallPlan snapshot is specifically the post-final-validation
  observation. A valid regular-file change after the old final tree observation
  but at the final-validation boundary therefore fails closed rather than
  returning a stale fingerprint.

### TDD and fresh evidence

1. Added the final-validation-boundary regression before the implementation.
   `C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe -m pytest tests/test_installation.py -k final_validation_boundary -v`
   initially failed as intended: one selected test reported `DID NOT RAISE
   SpecError` after a valid `README.md` mutation was injected immediately after
   the prior final validation.
2. Added matching pre/post-validation guarded observations and exact equality
   checks. The selected regression then passed, and the normal plan tests
   remained green.
3. Fresh commands, all with
   `C:\\Users\\33384\\Documents\\ChatGPT\\Agent-SkillOpt\\.venv\\Scripts\\python.exe`:

   - `python -m pytest tests/test_installation.py -v` — 57 passed.
   - `python -m ruff check src tests` — passed.
   - `python -m compileall -q src tests` — passed.
   - `python -m pytest tests -q` — 134 passed.
   - `git diff --check` — passed.
   - With `PYTHONPATH` set to this checkout's `src`, `python -m agent_skillopt
     --help` and the Hermes render-only command succeeded. The render omitted
     `--execute` and made no host invocation, remote fetch, enablement,
     inspection, or restart.

### Remaining boundary

The comparison closes the interval through the final formal validation and
post-validation capture, but cannot atomically prevent a same-privilege change
after that capture returns and before an external host consumes the local tree.
That external consumption interval remains explicitly unresolved. Hermes
continues to fetch mutable remote `owner/repository` content only at explicit
execution time, which remains a separately rendered trust boundary.
