"""CLI wheels must work outside the checkout with only declared dependencies."""

import json
import os
from pathlib import Path
import re
import shutil
import sys
import textwrap
import venv
from zipfile import ZipFile

import pytest

from content_helpers import six_section_payload
from test_content_distribution import (
    ROOT, _metadata, _run, _success, _wheel, distribution_artifacts,
)


@pytest.fixture(scope='session')
def cli_artifacts(distribution_artifacts):
    artifacts = distribution_artifacts
    source = artifacts['work'] / 'cli-source'
    shutil.copytree(ROOT / 'packages' / 'rpg_cli', source,
                    ignore=shutil.ignore_patterns('__pycache__', '*.egg-info', 'build', 'dist'))
    result = _run([sys.executable, '-m', 'pip', 'wheel', '--no-build-isolation',
                   '--no-deps', '--wheel-dir', artifacts['wheels'], source], artifacts['work'])
    _success(result)
    wheels = tuple(artifacts['wheels'].glob('rpg_cli-*.whl'))
    assert len(wheels) == 1
    return artifacts, wheels[0]


def test_cli_wheel_contains_library_only_and_declares_both_dependencies(cli_artifacts):
    _, wheel = cli_artifacts
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        assert 'rpg_cli/__init__.py' in names
        assert all(path.startswith('rpg_cli/') or '.dist-info/' in path for path in names)
        assert not any('demo' in path or path.startswith(('main.', 'core/', 'rpg_content/'))
                       for path in names)
        metadata = _metadata(archive)
        assert metadata['Name'] == 'rpg-cli'
        requirements = metadata.get_all('Requires-Dist', [])
        required = [item for item in requirements if ';' not in item]
        assert len(required) == 2
        for package in ('telegram-rpg-core', 'rpg-content'):
            matches = [re.fullmatch(re.escape(package) + r'\s*([^;]+)', value)
                       for value in required]
            matches = [match for match in matches if match]
            assert len(matches) == 1
            assert set(matches[0][1].replace(' ', '').split(',')) == {'>=0.1', '<0.2'}


def test_cli_installs_and_plays_outside_checkout_with_other_ids(cli_artifacts):
    artifacts, cli_wheel = cli_artifacts
    env_dir = artifacts['work'] / 'cli-clean-venv'
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(env_dir)
    python = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    outside = artifacts['work'] / 'cli-outside'
    outside.mkdir()
    # Install core/content before UI and prove the dependency direction at runtime.
    _success(_run([python, '-I', '-m', 'pip', 'install', '--no-index',
                   '--find-links', artifacts['wheels'], _wheel(artifacts, 'game')], outside))
    core_only = _run([python, '-I', '-c', textwrap.dedent('''
        import importlib.util
        import core
        from core import Character, GameService
        from core.world import Catalog
        assert importlib.util.find_spec('rpg_cli') is None
        assert importlib.util.find_spec('main') is None
        game = GameService(Catalog())
        hero = Character('Independent')
        game.register_character(hero)
        assert game.store.characters[hero.id] is hero
        print('core-independent-ok')
    ''')], outside)
    _success(core_only)
    assert core_only.stdout.strip() == 'core-independent-ok'
    # Resolve both declared dependencies normally, offline, rather than --no-deps.
    _success(_run([python, '-I', '-m', 'pip', 'install', '--no-index',
                   '--find-links', artifacts['wheels'], cli_wheel], outside))
    payload = json.dumps(six_section_payload(), ensure_ascii=False)
    script = textwrap.dedent('''
        import importlib.util
        import json
        from pathlib import Path
        from random import Random
        import sys
        import core
        import rpg_cli
        from core import Character, GameService, BattleStatus
        from core.content_adapter import to_catalog
        from rpg_content import parse
        from rpg_cli import CharacterPreset, create_session
        assert importlib.util.find_spec('main') is None
        assert Path(rpg_cli.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
        assert Path(core.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
        world = parse(sys.argv[1])
        game = GameService(to_catalog(world), rng=Random(9))
        created = []
        def create(name):
            hero = Character(name)
            game.register_character(hero)
            weapon = hero.inventory.add_item('sword')
            game.equip(hero.id, 'weapon', weapon)
            hero.inventory.add_consumable('potion', 2)
            game.equip(hero.id, 'potion_id', 'potion')
            created.append(hero)
            return hero
        session = create_session(world, game,
            (CharacterPreset('traveler', 'Путник', create),), 'traveler', 'Дальний герой')
        session.select('home')
        assert created[0].name == 'Дальний герой'
        assert len(game.store.characters) == 1
        view = session.select('locations')
        choices = {button.id for button in view.buttons if button.id.startswith('location:')}
        assert choices == {'location:forest'}
        session.select('location:forest')
        battle = next(iter(game.store.battles.values()))
        assert battle.status == BattleStatus.WAITING
        assert battle.location_id == 'forest'
        assert battle.monster_id == 'wolf'
        session.select('guard')
        assert battle.round_number == 2
        session.select('home')
        assert battle.status == BattleStatus.FINISHED
        assert battle.finish_reason == 'surrender'
        session.close()
        assert session.view() is None
        assert len(created) == 1
        print('isolated-cli-ok')
    ''')
    result = _run([python, '-I', '-c', script, payload], outside)
    _success(result)
    assert result.stdout.strip() == 'isolated-cli-ok'
    assert result.stderr == ''
