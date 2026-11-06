"""Static pre-migration evidence and the real composition boundary."""

import inspect
import json
from pathlib import Path

import pytest

import main as demo
from content_helpers import legacy_traces, normalize_legacy
from core import GameService
from rpg_content import load

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / 'content' / 'demo.json'


@pytest.fixture(scope='module')
def legacy():
    return json.loads((Path(__file__).parent / 'fixtures' / 'legacy_catalog.json').read_text(encoding='utf-8'))


def test_demo_projection_matches_every_legacy_field_type_value_and_order(legacy):
    from core.content_adapter import to_catalog

    actual = normalize_legacy(to_catalog(load(DEMO_PATH)))
    assert actual == legacy['catalog']
    # JSON preserves order and distinguishes the legacy integer/float representation.
    assert json.dumps(actual, ensure_ascii=False) == json.dumps(legacy['catalog'], ensure_ascii=False)


@pytest.mark.parametrize('seed', [0, 42, 123])
def test_migrated_demo_retains_fixed_seed_encounter_and_loot_traces(legacy, seed):
    from core.content_adapter import to_catalog

    assert legacy_traces(to_catalog(load(DEMO_PATH)), seed) == legacy['traces'][str(seed)]


def test_compatibility_wrapper_has_no_parameters_and_returns_fresh_catalogs(legacy):
    assert not inspect.signature(demo.create_content).parameters
    first, second = demo.create_content(), demo.create_content()
    assert normalize_legacy(first) == normalize_legacy(second) == legacy['catalog']
    first.monsters['slime'].loadouts.clear()
    first.locations['forgotten_forest'].rarity_weights.clear()
    first.items.clear()
    assert len(second.monsters['slime'].loadouts) == 6
    assert len(second.locations['forgotten_forest'].rarity_weights) == 6
    assert 'steel_sword' in second.items


@pytest.mark.parametrize('support', [False, True])
def test_main_loads_once_and_passes_world_service_to_console_boundary(monkeypatch, tmp_path, support):
    from core.content_adapter import to_catalog

    loads, consumed = [], []
    real_load = demo.load

    def observed_load(path):
        world = real_load(path)
        loads.append((Path(path).resolve(), world))
        return world

    def consume(world, game, selected_support):
        assert isinstance(game, GameService)
        assert normalize_legacy(game.catalog) == normalize_legacy(to_catalog(world))
        player = demo.create_player(game, selected_support)
        assert game.character_equipment(player).weapon.id == ('healing_staff' if support else 'steel_sword')
        consumed.append((world, selected_support))

    monkeypatch.setattr(demo, 'load', observed_load)
    monkeypatch.setattr(demo, 'run_cli', consume)
    monkeypatch.setattr('sys.argv', ['main.py', '--seed', '42'] + (['--support'] if support else []))
    monkeypatch.chdir(tmp_path)
    demo.main()
    assert len(loads) == len(consumed) == 1
    assert loads[0][0] == DEMO_PATH
    assert consumed[0] == (loads[0][1], support)
