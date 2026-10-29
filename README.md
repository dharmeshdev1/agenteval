# agenteval

[![ci](https://github.com/dharmeshdev1/agenteval/actions/workflows/ci.yml/badge.svg)](https://github.com/dharmeshdev1/agenteval/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

A harness for evaluating AI agents on real tasks: the agent works in a sandboxed
directory, then a hidden verifier it could never read decides whether it succeeded.
Reporting is statistical, with confidence intervals, unbiased pass@k and paired
comparisons built on [evalkit](https://github.com/dharmeshdev1/evalkit).

The point of the project is that every number it produces can be trusted, so most of the
code and tests are about preventing, detecting and ruling out ways the score could be wrong.

## What is inside

- **12 tasks** across 9 categories (Python bugs and features, shell, git, SQL, build systems,
  refactoring, performance), each with a workspace, a hidden verifier and a known-good solution.
- **Real isolation** on macOS using kernel-enforced `sandbox-exec` profiles, and a clearly
  labelled unconfined fallback elsewhere.
- **A validator** that proves each task is solvable, non-trivial, leak-free and strict
  enough to reject plausible wrong answers.
- **Baseline agents** (do nothing, apply the known solution) that calibrate the harness.
- **A model adapter** that lets an LLM drive the same tools over the Anthropic Messages API.
- **Reporting** with bootstrap confidence intervals, pass@k and paired significance tests.

## Baselines measured here

| Agent | Tasks passed | pass@1 |
| --- | --- | --- |
| null (does nothing) | 0 of 12 | 0.000 |
| oracle (applies the reference solution) | 12 of 12 | 1.000 |

Both ran under full kernel isolation. These two rows are calibration, not a result about
any model: they show the tasks are neither trivially passable nor broken. **I have not run a
language model through the harness**, so there is no model leaderboard here. The adapter is
tested against a local mock of the API and has not been run against the live service.

## Why a score here can be trusted

Evaluation harnesses fail quietly. These are the failure modes this one is built against,
and each has a test that attacks it.

### The agent must not be able to cheat

| Attack | Defence | How it is tested |
| --- | --- | --- |
| Read the hidden tests or the answer | Verifier and oracle live outside the workspace, and the sandbox denies reading them | An agent runs `cat` on them under the real sandbox and sees nothing |
| Edit the hidden tests | Writes are confined to the workspace by the kernel | An agent tries to overwrite a hidden test and the file is unchanged |
| Reach the files through `read_file` | Paths are resolved, including symlinks, and checked against the workspace | Traversal, absolute paths and symlinks to outside are all refused |
| Use the network | Denied by the sandbox | A control proves the same connection works outside the sandbox |
| Leak API keys from the harness | Environment is rebuilt from scratch, nothing is inherited | A test sets secrets in the parent and checks the command cannot see them |
| Edit the visible tests to make them pass | Protected files are hashed before and after | Editing or deleting one fails the episode as tampering, even if everything passes |
| Plant a fake `.verifier` directory | The agent's copy is excluded from the verification snapshot | A planted correct module would make the task pass without the defence, and a control test shows exactly that |
| Shadow a standard library module | The workspace is appended to `sys.path` after the standard library | A planted `colorsys.py` is ignored |
| Inject code through startup hooks or `PYTHONPATH` | Verifiers run `python3 -I`, and the validator rejects any that do not | Control: plain mode is fooled by `PYTHONPATH`, isolated mode is not |
| Hardcode the visible examples | Hidden tests use different data and check behaviours the instruction states | Each task has a hardcoding attempt that must fail |
| Leave a background process running | Each command runs in its own process group and the whole group is killed afterwards | Daemons and children are killed even after a normal exit |

### The harness must not blame the agent for its own faults

Infrastructure failures (a setup script that breaks, a verifier that cannot start) are
recorded as `infra_error` and excluded from pass rates, with a visible warning. They are never
silently counted as agent failures. A crashing model API is correctly an agent failure.

### The tasks themselves must be sound

`agenteval validate` checks every task, and CI runs it against all of them:

1. The null agent must fail.
2. The reference solution must pass, twice, to catch flakiness.
3. The reference solution must not touch protected files.
4. **Every plausible wrong solution must fail.** Each task ships several (a partial fix, a
   common mistake, a hardcoded answer, 37 in total).
5. No file in the workspace may be identical to a hidden file, and the visible tests must not
   reuse hidden test names.
6. Every verifier script that starts Python must use isolated mode.

Check 4 earned its place. When I added it, four of the twelve verifiers turned out to accept
a wrong answer. A tie-break test passed by luck because rows happened to be inserted in the
right order. A test for a missing graph node never reached that node. A log with no repeated
code on one line could not tell lines from occurrences. And one task described a Makefile bug
that did not actually exist. All four are fixed.

I also ran mutation checks on the defences themselves: disabling the verifier-planting
defence, the module-shadowing defence, tamper detection, path confinement and the sandbox's
network rule each makes at least one test fail. Three of those initially did not, because my
attack was not live, and I rewrote the tests until they did.

## What the sandbox does and does not enforce

| Backend | Network blocked | Writes confined to workspace | Hidden paths unreadable | Resource limits |
| --- | --- | --- | --- | --- |
| `seatbelt` (macOS) | yes | yes | yes | CPU, file size, open files |
| `process` (any OS) | **no** | **no** | **no** | CPU, file size, open files, memory on Linux |

Every result file records which level of isolation the run had. The `process` backend refuses
to run unless you pass `--allow-unconfined`, and is meant for trusted code only, such as running
the bundled tasks with the reference solution in CI. **Do not run an untrusted model's commands
with it.** A container backend would be the right addition for Linux and is not implemented.

Other honest limits: `sandbox-exec` is deprecated by Apple, though it works. Memory is not
limited on macOS. The sandbox is not a defence against kernel vulnerabilities.

## The tasks

| Task | Category | Difficulty |
| --- | --- | --- |
| fix-pagination | python-bugfix | easy |
| fix-shared-state | python-bugfix | easy |
| shell-fix-quoting | shell | easy |
| implement-lru-cache | python-implement | medium |
| deep-merge-config | python-implement | medium |
| csv-sales-report | scripting | medium |
| shell-top-errors | shell | medium |
| git-resolve-conflict | git | medium |
| refactor-rename-function | refactor | medium |
| sql-top-customers | sql | medium |
| build-fix-makefile | build | medium |
| perf-fast-shortest-path | performance | hard |

Each instruction states every behaviour the hidden tests check. A task that scores an agent on
requirements it was never told is measuring guessing, not ability.

## Quickstart

```bash
git clone https://github.com/dharmeshdev1/agenteval
cd agenteval
pip install -e ".[dev]"
pytest -q

agenteval list
agenteval validate                       # prove every task is sound
agenteval run --agent oracle --out runs/results.jsonl
agenteval report runs/results.jsonl
```

Evaluate a model (the key stays in the harness process and never reaches the sandbox):

```bash
export ANTHROPIC_API_KEY=...
agenteval run --agent llm --model <model-id> --trials 5 --workers 4 --out runs/results.jsonl
agenteval report runs/results.jsonl --k 1
agenteval compare runs/results.jsonl llm:<model-a> llm:<model-b>
```

Results are appended one episode per line as they finish, so an interrupted run loses at
most the episodes in flight and `--resume` picks up where it stopped. Every record carries
the task's fingerprint, the isolation level, the full trajectory and the verifier output.

## Writing a task

```
tasks/my-task/
  task.json     id, title, instruction, category, difficulty, limits, protected files
  workspace/    what the agent sees
  verifier/     verify.sh (exit 0 = pass) plus hidden tests and data
  oracle/       solve.sh, a known-good solution
  wrong/        *.sh, plausible incorrect solutions that must be rejected
  setup.sh      optional, runs in the sandbox before the agent starts
```

Python verifiers use the shared runner: `python3 -I .verifier/_shared/pyrun.py .verifier/tests`.
Run `agenteval validate --only my-task` until it passes.

## Design decisions

- **Judge the final state, not the transcript.** The agent saying it succeeded counts for
  nothing, and the verifier runs even after a step or time limit.
- **Verify a copy.** The verifier runs against a snapshot of the workspace in a fresh sandbox,
  so nothing the agent left running can interfere.
- **Statistics over the tasks.** Confidence intervals resample tasks, because trials of one task
  are not independent draws about the suite. Comparisons are paired.
- **File tools run in the harness, shell commands in the sandbox.** That makes path checks
  the harness's job, which is why symlink handling is tested directly.

## Limitations

- Twelve tasks is a small suite, and only one is rated hard. A pass rate here is a rough
  indicator, and the confidence intervals are wide at this size.
- Tasks were written and validated by one person, so they reflect one view of what matters.
- No model has been evaluated, and the adapter has not touched the live API.
- A verifier that checks behaviour on hidden inputs catches hardcoding, but cannot stop an agent
  from detecting the verifier by other means in an unconfined run.
- No container backend, so no isolation on Linux or Windows.
- One tool call per turn. No streaming, no parallel tool use, no cost budget beyond step and
  time limits.

## License

MIT
