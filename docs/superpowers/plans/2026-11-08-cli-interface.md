# Standalone CLI implementation

Spec: docs/superpowers/specs/2026-11-08-cli-interface-design.md

## Global Constraints

Independent rpg-cli distribution directly depends on existing core/content;
no reverse dependency, demo imports, content IDs or filesystem assumptions.
Each new class is in a separate file. Preserve old core imports and demo helpers.
All gameplay and FSA behavior follows the approved specification.
Work only in this checkout and branch; orchestrator owns Git operations.
Separate implementation, tests and read-only review roles per AGENTS.md.

## Task 1: Acceptance tests (test role)

Write tests/test_cli_session.py and tests/cli_helpers.py against public rpg_cli
Session, CharacterPreset, Button, InputButton, Screen, ScreenView, ConsoleAdapter.
create_session(world,game,presets,default_preset_id,default_name='Герой') builds initial
name screen. Expose stable IDs documented in test helper. Constructors of button
types match spec; generic integer input can use Session(initial_screen=screen,
on_close=callback) as an alternative low-level constructor if necessary; settle
this with implementer before coding. Test real core with small fixture data.
Run RED tests, recording missing feature evidence. No production edits or commits.
Report .superpowers/sdd/2026-11-08-cli-interface/task-1-report.md.

## Task 2: Package implementation (implementation role)

Read Task 1 tests and spec. Implement only packages/rpg_cli/** and main.py.
No test edits. Provide all screens and FSA, own pyproject, console, run_cli and
presets. Extend create_player optional name and delegate main.run_cli to package.
Preserve flags and UTF8; no core changes unless a demonstrated necessary fix.
Install editable via .venv/Scripts/python -m pip install --no-build-isolation
--no-deps -e ./packages/rpg_cli. Run Task 1 tests and report GREEN evidence.
Report .superpowers/sdd/2026-11-08-cli-interface/task-2-report.md; no commits.

## Task 3: Integration/distribution tests (test role)

Update obsolete demo smoke tests only for new flow. Add clean-wheel isolation
test, other IDs and presets, core import without UI, wheel payload check, plus
coverage gaps in Task 1. Run all tests. Do not edit production. Report
.superpowers/sdd/2026-11-08-cli-interface/task-3-report.md; no commits.

## Task 4: Documentation and final verification (orchestrator)

Update README and ARCHITECTURE with package install, API, factory registration
contract, independent usage and FSA flow. Target tests then full pytest. Commit
only task files. Final independent review whole branch incl OOP and isolation.
After fixes and verification push feature branch and gh pr create --base main.

