# RPG Content Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вынести проверяемый игровой контент в самостоятельно устанавливаемый пакет и сохранить поведение demo.

**Architecture:** `rpg_content` владеет immutable definitions, строгим JSON-контрактом и целостным snapshot. CLI использует тот же публичный API; `core.content_adapter` создаёт собственную боевую проекцию, composition root передаёт snapshot и GameService presentation adapter.

**Tech Stack:** Python >= 3.10, standard library runtime, setuptools, pytest, PowerShell.

**Spec:** `docs/superpowers/specs/2026-11-02-content-package-design.md` (прочитать целиком перед задачей).

## Global Constraints

- Distribution `rpg-content` версии `0.1.0`, Python >= 3.10, со стандартной библиотекой в runtime; без импортов core/main/Telegram, сети и transport IDs.
- Шесть секций: `items`, `monsters`, `locations`, `loot_tables`, `npcs`, `story_seeds`; schema_version только 1.
- Редкости в порядке `common`, `uncommon`, `rare`, `epic`, `legendary`, `mythic`; ID `[a-z][a-z0-9]*(?:_[a-z0-9]+)*`.
- Strict JSON: duplicate/unknown keys, bool вместо number/int, NaN/Infinity, неверные enum/null/диапазоны отклоняются; никаких coercion и fallback редкостей.
- Любое публичное конструирование проверяет invariants; ContentWorld проверяет полный граф. Все вложенные коллекции — defensive copies и read-only mappings/tuples.
- Add-only merge сохраняет порядок, не меняет входы, отклоняет любой duplicate ID, несовместимые canon/version; пустой merge даёт version 1/canon "".
- Контекст — одна секция, явные refs/index scope, Unicode char budget без усечения; библиотека ничего не печатает.
- CLI exit codes: 0 успех, 1 данные/ссылки/конфликт/бюджет, 2 аргументы, 3 I/O; stderr диагностика, атомарный output, запрет совпадения с input.
- Wheel контента не содержит игру/demo; wheel игры содержит core, зависимость `rpg-content>=0.1,<0.2`, без копии rpg_content.
- Не вводить quest execution, NPC runtime instances, hot reload, storage, Telegram SDK, Entity/Repository/EventBus/DI-container.
- Работать только в текущем checkout; оркестратор проверяет branch/status, сохраняет чужие изменения, использует git/gh CLI, не создаёт worktree.
- Tests: отдельный `gpt-6.1-sol/high`; production: `gpt-6.1-sol/medium`; промежуточный reviewer: `gpt-6.1-sol/low`, итоговый reviewer всей работы: `gpt-6.1-sol/high`, оба read-only. Каждый получает scope, spec, acceptance и команды.
- Каждая задача: tests first → подтверждённый red → implementation → green → review → исправления/проверка → scoped Conventional Commit. Ветки переключает только оркестратор без активных writers.

## Review Focus

- Ручной конструктор получает mutable dict/list, затем вызывающий их меняет: snapshot и вложенные определения должны оставаться прежними (Task 1).
- Narrative refs образуют цикл, а новый документ ссылается на базу: valid graph разрешается без рекурсии/мутации и без semantic quest execution (Task 1).
- Narrative context выбирает encounter-location: никакие spawn/loadout mechanics не раскрываются даже через прямые цели (Task 2).
- Output обозначает тот же input через relative path/symlink, либо replace падает: input/старый output целы, exit 3 для I/O (Task 2).
- Вне checkout отсутствуют core, PYTHONPATH и исходные ресурсы: установленный wheel сохраняет публичные query/context/CLI (Task 4).

## File Map and Execution Order

`packages/rpg_content/pyproject.toml` и `src/rpg_content/{__init__,models,validation,parser,merge,io}.py` — Task 1; `{context,__main__}.py` и `resources/` — Task 2. `core/content_adapter.py`, `content/demo.json`, `main.py`, root `pyproject.toml`, `README.md`, `ARCHITECTURE.md` — Task 3. Тесты каждой задачи перечислены ниже; Task 4 меняет только acceptance tests. Никаких изменений engine/service/model правил игры.

Порядок 1 → 2 → 3 → 4; до Task 3 тестовый агент сохраняет baseline старого Python-каталога. После заморозки Task 1 API допускаются независимые production scopes context/CLI и adapter/demo; никакой совместной записи одного файла. `__init__.py` принадлежит Task 1, поэтому сразу экспортирует build_context через отложенный import, пока Task 2 реализует его модуль.

Для всех команд установить `$env:PYTHONUTF8='1'`; Python: `.venv/Scripts/python.exe`. После создания package metadata рабочая установка: `.venv/Scripts/python.exe -m pip install --no-build-isolation -e ./packages/rpg_content`; после Task 3: `.venv/Scripts/python.exe -m pip install --no-build-isolation -e ./packages/rpg_content -e .`. Не менять sys.path/PYTHONPATH для обхода установки.

### Task 1: Standalone model, strict parser, graph, merge and serialization

**Files:** Create `packages/rpg_content/pyproject.toml`, `packages/rpg_content/src/rpg_content/{__init__,models,validation,parser,merge,io}.py`; tests `tests/test_content_models.py`, `tests/test_content_validation.py`, `tests/test_content_io.py`.

**Interfaces:** Export `ContentError` (source/path/code), `UnknownContentReference` (section/id), `ContextBudgetExceeded` (actual_chars/max_chars), six Definition types and `Definition` union, `ContentRef(section, id)`/`parse(text: str) -> ContentRef`, `ContentDocument`, `ContentWorld`. Definitions expose JSON-contract field names/defaults, replacing ref strings with ContentRef; collections are immutable. `ContentDocument` owns schema_version/canon and six ordered section mappings; `ContentWorld` exposes those mappings plus `resolve(ref: ContentRef) -> Definition`, `npcs_at(location_id: str) -> tuple[NpcDefinition, ...]`.

**Constructor contract:** `ContentWorld(*, schema_version=1, canon="", items={}, monsters={}, locations={}, loot_tables={}, npcs={}, story_seeds={})` describes keyword defaults, implemented with independent default factories/copies. Each mapping is `Mapping[str, CorrespondingDefinition]`. `NpcDefinition(*, id: str, name: str, role: str, description: str = "", location: ContentRef | None = None, lines: tuple[str, ...] = (), refs: tuple[ContentRef, ...] = ())`; `LocationDefinition(*, id: str, name: str, mode: str, description: str = "", spawns=(), rarity_weights={})` uses defensive copies. Freeze these signatures before test delegation; other definitions are exercised through parse/load and dataclasses.replace.

**Interfaces:** Export `parse(text: str, source: str = "<memory>") -> ContentDocument`, `load(path: str | Path) -> ContentWorld`, `validate(document: ContentDocument, base: ContentWorld | None = None) -> ContentWorld`, `merge(documents: Iterable[ContentDocument]) -> ContentWorld`. Internal `io.serialize(world: ContentWorld) -> str` emits deterministic UTF-8 JSON text with ref strings; `io.write_atomic(path: str | Path, text: str) -> None` owns temporary sibling/replace/cleanup and public I/O errors. No additional public serialization API is required. Single field-rule source in validation serves constructors/parser, without parser→game imports.

- [ ] Test agent writes minimal public API tests, six valid sections and parameterized strict failures: duplicate keys/IDs, unknown nested fields, all types/enums/null/ranges, missing required fields, slot-kind mismatch, complete rarities, potion rules, duplicate loot/spawn/refs. Example:
  ```python
  from rpg_content import ContentRef, parse, validate
  world = validate(parse('{"schema_version":1,"npcs":[{"id":"mira","name":"Мира","role":"Картограф"}]}'))
  assert world.resolve(ContentRef.parse('npcs:mira')) is world.npcs['mira']
  assert world.npcs['mira'].location is None
  ```
- [ ] Pin Review Focus 1–2: mutate caller-owned nested dict/list after direct constructors, reject direct invalid definitions/world key-ID mismatch/dangling graph, allow narrative cycles. Test mapping KeyError versus domain errors, known empty npcs_at, merge empty/add-only/canon/version/order/base invariance, cross-document refs and serialization/load roundtrip. Require errors source/path/code and silence via capsys; simulate read/write/replace failure and unchanged output.
- [ ] Run `.venv/Scripts/python.exe -m pytest tests/test_content_models.py tests/test_content_validation.py tests/test_content_io.py -q`; retain genuine missing-package/API red output before implementation.
- [ ] Product agent creates standalone src-layout metadata (setuptools, no runtime dependencies), frozen defensive models, shared validation, strict JSON hooks, full graph validation, ordered merge, deterministic serializer and atomic I/O. Constructors cannot bypass validation; snapshot graph validation must not recursively chase narrative cycles.
- [ ] Install editable as above, rerun three suites green; read-only reviewer checks constructor/parser parity, complete schema coverage, no shared mutable input, and no unchecked world path. Orchestrator stages explicit Task 1 files and commits `feat(content): add standalone validated content package`.

### Task 2: Public context builder, bundled rules/examples and CLI

**Files:** Create `packages/rpg_content/src/rpg_content/context.py`, `__main__.py`, `resources/common.md`, `resources/{items,monsters,locations,loot_tables,npcs,story_seeds}.md`, one JSON under `resources/examples/` for each of those six names; modify package metadata resource inclusion only. Tests `tests/test_content_context.py`, `tests/test_content_cli.py`.

**Interfaces:** Implement already exported `build_context(world: ContentWorld, *, section: str, task: str, refs: tuple[ContentRef, ...] = (), index_refs: tuple[ContentRef, ...] = (), max_chars: int) -> str`. Consume Task 1 API/internal io helpers; `python -m rpg_content` dispatches validate/merge/context with spec's exact flags. No context-specific world lookup or resource plumbing in consumer/CLI.

- [ ] Test agent adds context assertions using a tiny valid world (NPC Mira plus narrative location `bridge`) and subprocess CLI tests:
  ```python
  text = build_context(world, section='npcs', task='Добавь NPC', refs=(ContentRef('locations', 'bridge'),), index_refs=(), max_chars=10000)
  assert 'bridge' in text
  with pytest.raises(ContextBudgetExceeded) as error:
      build_context(world, section='npcs', task='Добавь NPC', max_chars=1)
  assert error.value.actual_chars > error.value.max_chars == 1
  ```
- [ ] Test all six resources/examples against actual parser/shared kind rules; selected profiles, direct-ref dedup/no second hop, index scope/link permission, result-only selected section, canon/task, exact Unicode len boundary, empty/invalid task/section, bool/nonpositive budget, unknown refs and silent library. Pin Review Focus 3 with mechanical sentinel fields/IDs that must never appear in narrative context.
- [ ] CLI tests cover required mutually exclusive `--ref/--no-refs`, `--index-ref/--no-index`, required max-chars/output for merge, stdout versus output, size on stderr including budget failure, exit 0/1/2/3, no partial output, UTF-8 and deterministic JSON. Pin Review Focus 4 with resolved path aliases, symlink where supported, and injected replace failure; keep original bytes unchanged.
- [ ] Run `.venv/Scripts/python.exe -m pytest tests/test_content_context.py tests/test_content_cli.py -q` and record red; product agent implements importlib.resources loading, profile projection and one-hop summaries, exact full-text budget, argparse dispatch and atomic output after validation/path checks.
- [ ] Rerun both suites plus Task 1 tests green; reviewer checks rule drift, prompt scope, library silence and output safety. Stage Task 2 files explicitly; commit `feat(content): add scoped context builder and CLI`.

### Task 3: Game adapter, demo migration, local installation and docs

**Files:** Create `core/content_adapter.py`, `content/demo.json`, `tests/fixtures/legacy_catalog.json`; modify `main.py`, root `pyproject.toml`, `README.md`, `ARCHITECTURE.md`. Tests `tests/test_content_adapter.py`, `tests/test_content_demo.py`; existing test files retained.

**Interfaces:** `core.content_adapter.to_catalog(world: ContentWorld) -> Catalog`; existing `main.create_content() -> Catalog` remains compatibility wrapper. `main.main() -> None` loads `Path(__file__).resolve().parent / 'content' / 'demo.json'` once, constructs catalog/GameService and calls presentation helper `run_cli(world: ContentWorld, game: GameService, support: bool) -> None` containing current player/encounter/play setup. Existing create_player/play contracts remain. No duplicated world load on main path.

- [ ] Before replacing create_content, test agent captures old catalog from current git commit into normalized fixture (all fields, item types, six rarity order, loadouts, loot/spawn order, exact numeric values) and fixed-seed encounter/loot traces for seeds 0/42/123. Record source commit; fixture is static test evidence, never generated from migrated JSON. Run existing `.venv/Scripts/python.exe -m pytest tests/test_game.py tests/test_invariants.py -q` and confirm baseline 44 tests.
- [ ] Test old/new catalog structural equality and fixed-seed traces, independent adapter collections, encounter-only projection, full world narrative/NPC visibility, one main load, wrapper signature and independent calls. Tiny assertion after load/adapter:
  ```python
  assert 'bridge' in world.locations
  assert 'bridge' not in to_catalog(world).locations  # fixture: bridge is narrative
  assert list(to_catalog(world).locations) == ['forgotten_forest']
  ```
- [ ] Record red with `.venv/Scripts/python.exe -m pytest tests/test_content_adapter.py tests/test_content_demo.py -q`; product agent ports every legacy value to JSON, converts refs/enums/bonuses into fresh core objects, changes composition root/helper and wrapper, fixes root packages to `["core"]` and dependency to `rpg-content>=0.1,<0.2`.
- [ ] Product agent documents independent content installation/local two-project installation, explicit world path, CLI validate/merge/context examples with required scope flags, external public imports, context budget, add-only updates, no hot reload and transport composition; update architecture to make Catalog a derived combat view.
- [ ] Install both editables as above; run `.venv/Scripts/python.exe -m pytest -q`; smoke ` '5' | .venv/Scripts/python.exe main.py --seed 42` and `'5' | .venv/Scripts/python.exe main.py --seed 42 --support`. Reviewer checks baseline parity/composition/no game-rule changes. Commit scoped files as `feat(game): load demo through content adapter`.

### Task 4: Wheel isolation, cross-transport acceptance and regression review

**Files:** Create `tests/test_content_distribution.py`, `tests/test_content_consumers.py`; tests own temporary venv/wheel/work directories, never checked-in build outputs. Product fixes discovered here return to owning agent/file scope.

**Interfaces:** Use only public rpg_content API, `to_catalog`, existing GameService and `run_cli` composition; fake CLI-shaped and Telegram-shaped adapters are test-only, accept `(world, game)`, no SDK. Package acceptance subprocesses use the temporary venv Python, absolute wheel/world paths, cwd outside repository, environment stripped of PYTHONPATH.

- [ ] Test agent writes packaging acceptance and runs it red against missing/incorrect wheel behavior: build each wheel via `.venv/Scripts/python.exe -m pip wheel --no-build-isolation --no-deps --wheel-dir <temp-wheel-dir> ./packages/rpg_content` and analogous root `.`; inspect archives and METADATA. Build prerequisites must exist in working venv; wheel consumers install actual wheels with `--no-index --no-deps` into fresh stdlib `venv` environments.
- [ ] Pin Review Focus 5: isolated content consumer must fail to find core, import no core/main, enumerate all six sections including narrative locations/unplaced NPC, query resolve/npcs_at/errors, build context, run CLI validate/context, and read all bundled rules/examples. Assert package Requires-Dist has no runtime dependencies, external demo absent; game wheel contains core only and required content dependency. Separately verify documented local two-source pip install in disposable venv using locally available build prerequisites/wheels, without network fallback.
- [ ] Test both query adapters against one shared world/game, including all locations/NPC, empty npcs_at, unknown domain refs and mapping KeyError. Stateful sequences use two fresh GameServices/Random(42)/stores and equivalent characters; normalize generated UUIDs, compare encounters/actions/events/loot and verify second state untouched before its run:
  ```python
  assert cli.world is telegram.world is world
  assert cli.locations() == telegram.locations() == tuple(world.locations)
  assert cli.npcs_at('bridge') == telegram.npcs_at('bridge')
  ```
- [ ] Run `.venv/Scripts/python.exe -m pytest tests/test_content_distribution.py tests/test_content_consumers.py -q`, resolve proven failures through owning production agents, then `.venv/Scripts/python.exe -m pytest -q`; repeat both demo smoke commands. Report baseline 44 retained plus actual new count and packaging results, without treating checkout imports as isolation evidence.
- [ ] Fresh read-only reviewer checks full branch against spec, Review Focus and AGENTS, validates wheel evidence and deterministic seed baseline. Fix actionable findings, rerun affected tests; commit `test(content): verify isolated distributions and transport parity`. Orchestrator checks clean/scoped git status, pushes feature branch and opens `gh pr create --base main` with problem/change/checks/limitations; no merge. If remote access fails, keep verified local commits and report exact unavailable step.
