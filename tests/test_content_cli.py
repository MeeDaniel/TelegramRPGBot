"""CLI integration uses actual subprocesses and files, never patched dispatch."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


def cli(tmp_path, *arguments):
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    result = subprocess.run([sys.executable, '-m', 'rpg_content', *map(str, arguments)],
                            cwd=tmp_path, env=env, encoding='utf-8', capture_output=True,
                            timeout=30)
    # An interpreter startup failure is not the CLI's data-error exit code 1.
    assert 'No module named' not in result.stderr, result.stderr
    assert 'cannot be directly executed' not in result.stderr, result.stderr
    return result


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.fixture
def world_file(tmp_path):
    return write_json(tmp_path / 'мир.json', {
        'schema_version': 1, 'canon': 'Канон моста 🌓.',
        'locations': [{'id': 'bridge', 'name': 'Мост', 'mode': 'narrative'}],
        'npcs': [{'id': 'mira', 'name': 'Мира', 'role': 'Картограф',
                  'location': 'locations:bridge'}],
    })


def context_args(world_file):
    return ['context', world_file, '--type', 'npcs', '--task', 'Добавь жителя моста 🗺.',
            '--no-refs', '--no-index', '--max-chars', '100000']


def has_number(text, number):
    return re.search(r'(?<!\d)' + str(number) + r'(?!\d)', text) is not None


def test_validate_uses_explicit_world_and_emits_no_content(tmp_path, world_file):
    result = cli(tmp_path, 'validate', world_file)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ''


def test_validate_addition_resolves_base_without_modifying_files(tmp_path, world_file):
    addition = write_json(tmp_path / 'addition.json', {
        'schema_version': 1,
        'story_seeds': [{'id': 'trail', 'name': 'След', 'premise': 'Найти тропу.',
                         'refs': ['npcs:mira']}],
    })
    originals = (world_file.read_bytes(), addition.read_bytes())
    unresolved = cli(tmp_path, 'validate', addition)
    assert unresolved.returncode == 1
    assert unresolved.stderr
    resolved = cli(tmp_path, 'validate', addition, '--base', world_file)
    assert resolved.returncode == 0, resolved.stderr
    assert (world_file.read_bytes(), addition.read_bytes()) == originals


def test_merge_is_deterministic_utf8_and_roundtrips_through_public_load(tmp_path, world_file):
    from rpg_content import load

    addition = write_json(tmp_path / 'addition.json', {
        'schema_version': 1, 'npcs': [{'id': 'guard', 'name': 'Страж', 'role': 'Охрана'}],
    })
    first, second = tmp_path / 'first.json', tmp_path / 'second.json'
    originals = (world_file.read_bytes(), addition.read_bytes())
    for output in (first, second):
        result = cli(tmp_path, 'merge', world_file, addition, '--output', output)
        assert result.returncode == 0, result.stderr
        assert result.stdout == ''
    assert first.read_bytes() == second.read_bytes()
    assert 'Страж'.encode('utf-8') in first.read_bytes()
    assert list(load(first).npcs) == ['mira', 'guard']
    assert load(first).canon == 'Канон моста 🌓.'
    assert (world_file.read_bytes(), addition.read_bytes()) == originals


def test_context_stdout_and_output_report_full_unicode_character_size(tmp_path, world_file):
    arguments = context_args(world_file)
    result = cli(tmp_path, *arguments)
    assert result.returncode == 0, result.stderr
    assert 'Добавь жителя моста 🗺.' in result.stdout
    assert 'Канон моста 🌓.' in result.stdout
    assert has_number(result.stderr, len(result.stdout))
    output = tmp_path / 'контекст.txt'
    written = cli(tmp_path, *arguments, '--output', output)
    assert written.returncode == 0, written.stderr
    assert written.stdout == ''
    assert output.read_text(encoding='utf-8') == result.stdout
    assert has_number(written.stderr, len(result.stdout))


def test_context_reference_and_index_scopes_accept_repeated_flags(tmp_path, world_file):
    result = cli(tmp_path, 'context', world_file, '--type', 'story_seeds', '--task', 'История',
                 '--ref', 'npcs:mira', '--ref', 'locations:bridge',
                 '--index-ref', 'npcs:mira', '--index-ref', 'locations:bridge',
                 '--max-chars', '100000')
    assert result.returncode == 0, result.stderr
    assert 'mira' in result.stdout
    assert 'bridge' in result.stdout


@pytest.mark.parametrize('remove', ['--no-refs', '--no-index', '--max-chars', '--task', '--type'])
def test_context_requires_explicit_scope_task_type_and_budget(tmp_path, world_file, remove):
    arguments = context_args(world_file)
    index = arguments.index(remove)
    del arguments[index:index + (1 if remove in ('--no-refs', '--no-index') else 2)]
    result = cli(tmp_path, *arguments)
    assert result.returncode == 2
    assert result.stdout == ''
    assert result.stderr


@pytest.mark.parametrize('extra', [
    ['--ref', 'npcs:mira'], ['--index-ref', 'locations:bridge'],
    ['--max-chars', '0'], ['--max-chars', '-1'], ['--max-chars', '1.5'],
    ['--type', 'quests'], ['--task', '   '],
])
def test_context_invalid_cli_arguments_exit_two(tmp_path, world_file, extra):
    arguments = context_args(world_file)
    if extra[0] in ('--max-chars', '--type', '--task'):
        index = arguments.index(extra[0])
        del arguments[index:index + 2]
    result = cli(tmp_path, *arguments, *extra)
    assert result.returncode == 2
    assert result.stdout == ''
    assert result.stderr


def test_merge_requires_output_argument(tmp_path, world_file):
    result = cli(tmp_path, 'merge', world_file)
    assert result.returncode == 2
    assert result.stdout == ''
    assert result.stderr


def test_budget_failure_reports_actual_size_without_partial_stdout_or_output(tmp_path, world_file):
    success = cli(tmp_path, *context_args(world_file))
    assert success.returncode == 0, success.stderr
    arguments = context_args(world_file)
    arguments[-1] = '1'
    output = tmp_path / 'existing.txt'
    output.write_bytes(b'keep previous output\r\n')
    failure = cli(tmp_path, *arguments, '--output', output)
    assert failure.returncode == 1
    assert failure.stdout == ''
    assert has_number(failure.stderr, len(success.stdout))
    assert has_number(failure.stderr, 1)
    assert output.read_bytes() == b'keep previous output\r\n'


@pytest.mark.parametrize('command', ['merge', 'context'])
def test_invalid_data_preserves_existing_output(tmp_path, world_file, command):
    bad = tmp_path / 'bad.json'
    bad.write_text('{"schema_version":1,"npcs":[{"id":"broken"}]}', encoding='utf-8')
    output = tmp_path / 'existing.txt'
    output.write_bytes(b'previous data')
    arguments = ['merge', world_file, bad] if command == 'merge' else context_args(bad)
    result = cli(tmp_path, *arguments, '--output', output)
    assert result.returncode == 1
    assert result.stdout == ''
    assert result.stderr
    assert output.read_bytes() == b'previous data'


def test_duplicate_merge_conflict_preserves_existing_output(tmp_path, world_file):
    output = tmp_path / 'existing.json'
    output.write_bytes(b'previous data')
    result = cli(tmp_path, 'merge', world_file, world_file, '--output', output)
    assert result.returncode == 1
    assert result.stdout == ''
    assert result.stderr
    assert output.read_bytes() == b'previous data'


def test_merge_output_cannot_overwrite_second_input(tmp_path, world_file):
    addition = write_json(tmp_path / 'addition.json', {
        'schema_version': 1, 'npcs': [{'id': 'guard', 'name': 'Страж', 'role': 'Охрана'}],
    })
    originals = (world_file.read_bytes(), addition.read_bytes())
    result = cli(tmp_path, 'merge', world_file, addition, '--output', addition)
    assert result.returncode == 3
    assert result.stdout == ''
    assert result.stderr
    assert (world_file.read_bytes(), addition.read_bytes()) == originals


def test_unknown_context_reference_is_data_error(tmp_path, world_file):
    arguments = context_args(world_file)
    arguments.remove('--no-refs')
    result = cli(tmp_path, *arguments, '--ref', 'npcs:missing_npc')
    assert result.returncode == 1
    assert result.stdout == ''
    assert 'missing_npc' in result.stderr


@pytest.mark.parametrize('command', ['validate', 'merge', 'context'])
def test_missing_input_is_io_error_and_preserves_existing_output(tmp_path, command):
    missing = tmp_path / 'missing.json'
    output = tmp_path / 'existing.txt'
    output.write_bytes(b'previous data')
    arguments = context_args(missing) if command == 'context' else [command, missing]
    if command != 'validate':
        arguments += ['--output', output]
    result = cli(tmp_path, *arguments)
    assert result.returncode == 3
    assert result.stdout == ''
    assert result.stderr
    assert output.read_bytes() == b'previous data'


@pytest.mark.parametrize('command', ['merge', 'context'])
def test_unwritable_output_target_is_io_error(tmp_path, world_file, command):
    output_directory = tmp_path / 'directory'
    output_directory.mkdir()
    preserved = output_directory / 'preserved.txt'
    preserved.write_bytes(b'keep directory contents')
    arguments = context_args(world_file) if command == 'context' else ['merge', world_file]
    result = cli(tmp_path, *arguments, '--output', output_directory)
    assert result.returncode == 3
    assert result.stdout == ''
    assert result.stderr
    assert preserved.read_bytes() == b'keep directory contents'


@pytest.mark.parametrize('command', ['merge', 'context'])
@pytest.mark.parametrize('alias', ['same', 'relative', 'symlink'])
def test_output_cannot_alias_input_and_input_bytes_survive(tmp_path, world_file, command, alias):
    original = world_file.read_bytes()
    if alias == 'same':
        output = world_file
    elif alias == 'relative':
        (tmp_path / 'subdir').mkdir()
        output = Path('subdir') / '..' / world_file.name
    else:
        output = tmp_path / 'alias.json'
        try:
            output.symlink_to(world_file)
        except OSError as error:
            pytest.skip('This host does not permit symlinks: ' + str(error))
    arguments = context_args(world_file) if command == 'context' else ['merge', world_file]
    result = cli(tmp_path, *arguments, '--output', output)
    assert result.returncode == 3
    assert result.stdout == ''
    assert result.stderr
    assert world_file.read_bytes() == original
    if alias == 'symlink':
        assert output.is_symlink()
