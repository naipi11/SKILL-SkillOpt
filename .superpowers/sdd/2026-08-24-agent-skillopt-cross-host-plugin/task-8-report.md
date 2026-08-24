# Task 8 — Final verification and compatibility evidence

## Scope and safety boundary

This record covers fresh observations on Windows on 2026-08-25 from commit
`b65914e0ea6bf62bb8d95b2cd1f3518c2117534b`. No marketplace add, plugin add or
install, enablement, inspection, restart, remote fetch, `--execute`, push, or
merge command was run. A rendered installation plan is not an installation or
runtime result.

## Offline verification

Source-first validation used
`C:\Users\33384\Documents\ChatGPT\Agent-SkillOpt\.venv\Scripts\python.exe`
with `PYTHONPATH` set to this worktree's `src` directory:

| Command | Fresh result |
| --- | --- |
| `python -m compileall src` | Exit 0. |
| `python -m pytest tests -v` | Exit 0; 166 passed in 5.34 s. |
| `python -m ruff check src tests scripts/validate_bundle.py skills/agent-skillopt/scripts/scaffold_bundle.py` | Exit 0; `All checks passed!`. |
| `python scripts/validate_bundle.py .` | Exit 0; `VALID`. |
| `git diff --check` | Exit 0; no output. |
| Git-Bash `bash -n scripts/validate.sh` | Exit 0. |
| Git-Bash `scripts/validate.sh` with the source venv's `Scripts` directory first on `PATH` | Exit 0; 166 passed, `VALID`, and `All checks passed!`. |

For reproducibility, a first bare Git-Bash execution of `scripts/validate.sh`
resolved `python` to system Python 3.12 and failed with `No module named
pytest`. That environment did not satisfy the specified source-venv boundary;
the final result above explicitly prepended the required venv and passed.

The required Windows Python 3.12 wrapper proof also passed:

```text
C:\Users\33384\AppData\Local\Programs\Python\Python312\python.exe skills\agent-skillopt\scripts\scaffold_bundle.py install --host codex --path .
```

It exited 0 and emitted JSON containing `confirmation_token`,
`network_required: false`, and the planned `codex plugin marketplace add` plus
`codex plugin add` argv arrays. The invocation did not include `--execute`; no
rendered argv was run.

## Host CLI evidence

Only the approved read-only commands were invoked. None of their output emits a
host-binary version; version claims below are therefore limited to fields the
commands actually returned rather than inferred executable versions.

| Host | Command | Exact result and bounded claim |
| --- | --- | --- |
| Codex | `codex plugin list --available --json` | Exit 0; returned JSON `installed` and `available` arrays, with a `version` field on plugin entries. This proves the list/read surface was available only; it does not prove this package was added, enabled, or runnable. |
| Claude Code | `claude plugin validate . --strict` | Exit 0; `Validating marketplace manifest: ...\.claude-plugin\marketplace.json` followed by `Validation passed`. This is strict marketplace-manifest validation, not installation or runtime proof. |
| Hermes Agent | `hermes plugins --help` | Exit 0; help explicitly states that it manages native Hermes plugins and portable Agent Plugins v1 packages, and lists `install` and `enable` commands. This is CLI-surface evidence only. |
| Hermes Agent | `hermes skills --help` | Exit 0; help listed its skills management command family. This is CLI-surface evidence only. |
| OpenClaw | Read-only PATH availability check only | Exit 1 with `openclaw-path=absent`; no `openclaw` command was invoked. OpenClaw remains contract-only and has no local installation, inspection, restart, or runtime evidence. |

## Residual scope

The portable bundle's structure, shipped wrapper render path, and the listed
host CLI surfaces are freshly verified. No actual host installation, discovery,
enablement, execution, remote fetch, or OpenClaw runtime behavior is verified.
Such claims require separate authorization and a new observation after the
corresponding host action.
