# Standalone CLI delivery

## Delivered

Independent `rpg-cli` distribution with a public typed-input FSA, RPG screens,
console adapter, externally supplied character presets and a demo composition
root. Core has no dependency on the interface. All 14 new production classes
have individual modules. Core files and game rules were not changed.

## Verification

- Baseline: 397 passed, 2 skipped.
- Final orchestrator run: `.venv/Scripts/python -m pytest -q -rs`:
  448 passed, 2 skipped in 47.39s.
- Skips are existing content-CLI symlink tests: Windows does not grant symlink
  creation privileges on this host.
- New regression failures were observed before fixing UTF-8 stdin, pending
  navigation, console input guidance and explicit surrender labeling.
- CLI wheel installed offline with local core/content wheels in a clean venv;
  exercised from another cwd with alternate content/preset IDs, no checkout or
  demo files. Core was imported successfully before installing CLI.
- Package Python syntax parses using the Python 3.10 grammar. Actual runtime
  test interpreter: Python 3.14.3.
- `git diff --check` clean. Task reviews and final Sol high review found no
  Critical or Important issues. Final OOP review confirms responsibility and
  dependency separation without an abstract game port or graph framework.

## Execution rulings

1. Both execution skills were requested. Use subagent-driven implementation,
   test and review roles, with sequential progress accounting from executing-plans.
   This follows AGENTS.md; the cost of an incorrect choice is process overhead.
2. Use native PowerShell equivalents for bash artifact helpers. The environment
   is Windows; the cost if wrong is manual artifact bookkeeping.
3. Keep `Session(initial_screen, on_close)` generic and expose `create_session`
   to assemble RPG screens. This supports custom screens and typed integer input
   tests through a real interface, without test-only production hooks. The cost
   if wrong is one additional public factory to maintain.

## Nonblocking review findings deferred

- An explicit empty-string preset ID falls back to the default during finalize,
  although the configuration validator accepts it. Use nonempty preset IDs;
  normal demo and documented usage use nonempty IDs.
- The cooldown tests assert state preservation but their text checks do not
  specifically identify the error; the initial potion test only checks that
  explanatory text is nonempty; it could assert the cooldown error more closely.
- The initial empty-location test checks safe navigation and nonempty text,
  rather than the exact semantic explanation.
- The victory session test checks that rewards are not duplicated; initial
  reward issuance is covered by the existing core tests rather than a separate
  interface-level assertion.

The final reviewer classified these as Minor; none blocks the approved flow.
