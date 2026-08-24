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
