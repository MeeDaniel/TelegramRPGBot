"""Acceptance uses real wheels and a fresh interpreter outside the checkout."""

from email import message_from_bytes
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import textwrap
import venv
from zipfile import ZipFile

import pytest

from content_helpers import SECTIONS, six_section_payload

ROOT = Path(__file__).resolve().parents[1]


def _environment():
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(key, None)
    env.update(PYTHONUTF8='1', PIP_NO_INDEX='1', PIP_NO_CACHE_DIR='1',
               PIP_DISABLE_PIP_VERSION_CHECK='1',
               PIP_CONFIG_FILE=os.devnull)
    return env


def _run(args, cwd):
    return subprocess.run([str(arg) for arg in args], cwd=cwd, env=_environment(),
                          capture_output=True, text=True, encoding='utf-8', timeout=120)


def _success(result):
    assert result.returncode == 0, f'{result.args!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}'


@pytest.fixture(scope='session')
def distribution_artifacts(tmp_path_factory):
    """Build once from disposable source copies so build output stays outside git."""
    work = tmp_path_factory.mktemp('content-distribution')
    content_source, game_source = work / 'content-source', work / 'game-source'
    shutil.copytree(ROOT / 'packages' / 'rpg_content', content_source,
                    ignore=shutil.ignore_patterns('__pycache__', '*.egg-info', 'build', 'dist'))
    game_source.mkdir()
    shutil.copy2(ROOT / 'pyproject.toml', game_source / 'pyproject.toml')
    for name in ('README.md', 'ARCHITECTURE.md'):
        shutil.copy2(ROOT / name, game_source / name)
    shutil.copytree(ROOT / 'core', game_source / 'core', ignore=shutil.ignore_patterns('__pycache__'))
    wheels = work / 'wheels'
    wheels.mkdir()
    builds = {}
    for name, source in (('content', content_source), ('game', game_source)):
        builds[name] = _run([sys.executable, '-m', 'pip', 'wheel', '--no-build-isolation',
                             '--no-deps', '--wheel-dir', wheels, source], work)
    world_path = work / 'outside-world.json'
    world_path.write_text(json.dumps(six_section_payload(), ensure_ascii=False), encoding='utf-8')
    return {'work': work, 'wheels': wheels, 'builds': builds, 'world': world_path,
            'content_source': content_source, 'game_source': game_source}


def _wheel(artifacts, name):
    _success(artifacts['builds'][name])
    pattern = 'rpg_content-*.whl' if name == 'content' else 'telegram_rpg_core-*.whl'
    wheels = tuple(artifacts['wheels'].glob(pattern))
    assert len(wheels) == 1
    return wheels[0]


def _metadata(archive):
    paths = [path for path in archive.namelist() if path.endswith('.dist-info/METADATA')]
    assert len(paths) == 1
    return message_from_bytes(archive.read(paths[0]))


@pytest.fixture(scope='session')
def isolated_content(distribution_artifacts):
    artifacts = distribution_artifacts
    wheel = _wheel(artifacts, 'content')
    env_dir = artifacts['work'] / 'isolated-venv'
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(env_dir)
    python = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    outside = artifacts['work'] / 'outside'
    outside.mkdir()
    _success(_run([python, '-I', '-m', 'pip', 'install', '--no-index', '--no-deps', wheel], outside))
    return python, outside, artifacts['world']


def test_content_wheel_contains_only_library_and_all_bundled_resources(distribution_artifacts):
    with ZipFile(_wheel(distribution_artifacts, 'content')) as archive:
        names = archive.namelist()
        roots = {path.split('/')[0] for path in names}
        assert roots == {'rpg_content', 'rpg_content-0.1.0.dist-info'}
        assert 'rpg_content/__main__.py' in names
        assert 'rpg_content/resources/common.md' in names
        for section in SECTIONS:
            assert f'rpg_content/resources/{section}.md' in names
            assert f'rpg_content/resources/examples/{section}.json' in names
        assert not any('demo.json' in path or path.startswith(('core/', 'main.')) for path in names)
        metadata = _metadata(archive)
        assert metadata['Name'] == 'rpg-content'
        assert metadata['Version'] == '0.1.0'
        assert metadata['Requires-Python'] == '>=3.10'
        assert not metadata.get_all('Requires-Dist', [])


def test_game_wheel_contains_core_and_declares_content_dependency(distribution_artifacts):
    with ZipFile(_wheel(distribution_artifacts, 'game')) as archive:
        names = archive.namelist()
        assert {path.split('/')[0] for path in names} == {'core', 'telegram_rpg_core-0.1.0.dist-info'}
        assert 'core/content_adapter.py' in names
        assert not any(path.startswith('rpg_content/') for path in names)
        dependencies = _metadata(archive).get_all('Requires-Dist', [])
        required = [value for value in dependencies if ';' not in value]
        assert len(required) == 1
        match = re.fullmatch(r'rpg-content\s*([^;]+)', required[0])
        assert match is not None
        assert set(match[1].replace(' ', '').split(',')) == {'>=0.1', '<0.2'}


def test_content_wheel_public_api_queries_context_and_resources_without_game(isolated_content):
    python, outside, world_path = isolated_content
    script = textwrap.dedent('''
        import importlib.util
        from importlib.resources import files
        from pathlib import Path
        import sys
        assert importlib.util.find_spec('core') is None
        assert importlib.util.find_spec('main') is None
        from rpg_content import (
            ContentRef, ContentWorld, UnknownContentReference,
            build_context, load, merge, parse, validate,
        )
        import rpg_content
        assert Path(rpg_content.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
        world = load(sys.argv[1])
        assert isinstance(world, ContentWorld)
        assert tuple(world.locations) == ('forest', 'bridge', 'empty')
        assert tuple(world.npcs) == ('mira', 'wanderer', 'guard')
        assert world.npcs['wanderer'].location is None
        assert [npc.id for npc in world.npcs_at('bridge')] == ['mira', 'guard']
        assert world.npcs_at('empty') == ()
        assert world.resolve(ContentRef.parse('npcs:mira')) is world.npcs['mira']
        for query in (lambda: world.resolve(ContentRef('npcs', 'absent')),
                      lambda: world.npcs_at('absent')):
            try:
                query()
            except UnknownContentReference as error:
                assert error.id == 'absent'
            else:
                raise AssertionError('missing domain error')
        try:
            world.items['absent']
        except KeyError:
            pass
        else:
            raise AssertionError('mapping must retain KeyError')
        sections = ('items', 'monsters', 'locations', 'loot_tables', 'npcs', 'story_seeds')
        for section in sections:
            assert getattr(world, section)
        addon = parse('{"schema_version":1,"npcs":[{"id":"guest","name":"Гость","role":"Путник","location":"locations:bridge"}]}')
        extended = validate(addon, base=world)
        assert tuple(extended.npcs)[-1] == 'guest'
        assert 'guest' not in world.npcs
        assert merge(()).schema_version == 1
        resources = files('rpg_content').joinpath('resources')
        assert resources.joinpath('common.md').read_text(encoding='utf-8').strip()
        for section in sections:
            assert resources.joinpath(section + '.md').read_text(encoding='utf-8').strip()
            example = parse(resources.joinpath('examples', section + '.json').read_text(encoding='utf-8'))
            assert getattr(example, section)
        context = build_context(world, section='npcs', task='Добавь смотрителя моста',
                                refs=(ContentRef('locations','bridge'),), index_refs=(), max_chars=30000)
        assert 'bridge' in context and 'Добавь смотрителя моста' in context
        assert 'core' not in sys.modules and 'main' not in sys.modules
        print('isolated-public-api-ok')
    ''')
    result = _run([python, '-I', '-c', script, world_path], outside)
    _success(result)
    assert result.stdout.strip() == 'isolated-public-api-ok'
    assert result.stderr == ''


def test_content_wheel_cli_works_from_unrelated_directory(isolated_content):
    python, outside, world_path = isolated_content
    _success(_run([python, '-I', '-m', 'rpg_content', 'validate', world_path], outside))
    result = _run([python, '-I', '-m', 'rpg_content', 'context', world_path,
                   '--type', 'npcs', '--task', 'Добавь смотрителя моста',
                   '--ref', 'locations:bridge', '--no-index', '--max-chars', '30000'], outside)
    _success(result)
    assert 'bridge' in result.stdout and 'Добавь смотрителя моста' in result.stdout
    assert result.stderr.strip()  # CLI reports context size.


def test_documented_two_source_install_uses_both_distributions_without_network(distribution_artifacts):
    artifacts = distribution_artifacts
    target = artifacts['work'] / 'two-source-target'
    # Working interpreter supplies existing setuptools/wheel; no environment mutation.
    result = _run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-build-isolation',
                   '--target', target, artifacts['content_source'], artifacts['game_source']],
                  artifacts['work'])
    _success(result)
    result = _run([sys.executable, '-c', textwrap.dedent('''
        from importlib.metadata import distribution
        from pathlib import Path
        import core
        import rpg_content
        from core.content_adapter import to_catalog
        from rpg_content import load
        import sys
        target = Path.cwd().resolve()
        assert Path(core.__file__).resolve().is_relative_to(target)
        assert Path(rpg_content.__file__).resolve().is_relative_to(target)
        assert distribution('rpg-content').version == '0.1.0'
        assert distribution('telegram-rpg-core').version == '0.1.0'
        assert tuple(to_catalog(load(sys.argv[1])).locations) == ('forest',)
        print('two-source-install-ok')
    '''), artifacts['world']], target)
    _success(result)
    assert result.stdout.strip() == 'two-source-install-ok'
