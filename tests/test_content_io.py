import json
import os
from pathlib import Path

import pytest

from content_helpers import SECTIONS, six_section_payload


def test_load_reads_explicit_utf8_file(tmp_path):
    from rpg_content import load

    path = tmp_path / 'мир.json'
    path.write_text('{"schema_version":1,"canon":"Лес"}', encoding='utf-8')
    assert load(path).canon == 'Лес'


def test_serialize_roundtrip_keeps_typed_refs_values_order_and_kind_fields(tmp_path):
    from rpg_content import ContentRef, load, parse, validate
    from rpg_content.io import serialize, write_atomic

    original = validate(parse(json.dumps(six_section_payload())))
    text = serialize(original)
    assert text == serialize(original)
    assert 'Мост' in text
    payload = json.loads(text)
    assert payload['npcs'][0]['location'] == 'locations:bridge'
    assert payload['monsters'][0]['loadouts']['common']['weapon'] == 'items:sword'
    assert 'guard_multiplier' not in payload['items'][0]
    assert 'duration' not in payload['items'][4]
    assert 'attack_type' not in payload['items'][1]
    path = tmp_path / 'world.json'
    write_atomic(path, text)
    restored = load(path)
    assert restored.schema_version == 1 and restored.canon == original.canon
    for section in SECTIONS:
        assert tuple(getattr(restored, section)) == tuple(getattr(original, section))
        assert dict(getattr(restored, section)) == dict(getattr(original, section))
    assert restored.npcs['mira'].location == ContentRef('locations', 'bridge')
    assert serialize(restored) == text


@pytest.mark.parametrize('failure', ['missing', 'invalid_utf8', 'directory'])
def test_load_wraps_filesystem_and_decode_errors_with_source(tmp_path, failure):
    from rpg_content import ContentError, load

    path = tmp_path / 'bad.json'
    if failure == 'invalid_utf8':
        path.write_bytes(b'\xff\xfe\xff')
    elif failure == 'directory':
        path.mkdir()
    with pytest.raises(ContentError) as caught:
        load(str(path))
    assert caught.value.source == str(path)
    assert caught.value.path and caught.value.code


def test_load_diagnostics_retain_explicit_file_path_for_data_and_graph_errors(tmp_path):
    from rpg_content import ContentError, load

    path = tmp_path / 'broken.json'
    for text in ['{bad', '{"schema_version":1,"npcs":[{"id":"mira","name":"Мира",'
                            '"role":"Картограф","location":"locations:missing"}]}']:
        path.write_text(text, encoding='utf-8')
        with pytest.raises(ContentError) as caught:
            load(path)
        assert caught.value.source == str(path)
        assert caught.value.path and caught.value.code


def test_atomic_write_replaces_existing_file_and_leaves_no_temporary_siblings(tmp_path):
    from rpg_content.io import write_atomic

    path = tmp_path / 'world.json'
    path.write_text('previous', encoding='utf-8')
    write_atomic(str(path), 'Лес\nМост\n')
    assert path.read_bytes() == 'Лес\nМост\n'.encode('utf-8')
    assert list(tmp_path.iterdir()) == [path]


def test_replace_failure_keeps_old_output_and_cleans_temporary_file(tmp_path, monkeypatch):
    from rpg_content import ContentError
    from rpg_content.io import write_atomic

    path = tmp_path / 'world.json'
    path.write_bytes(b'old output')

    def fail_replace(source, destination, *args, **kwargs):
        # Inspect real staged data at the actual filesystem boundary.
        assert Path(source).parent == path.parent
        assert Path(destination) == path
        assert Path(source).read_text(encoding='utf-8') == 'новый мир'
        assert path.read_bytes() == b'old output'
        raise OSError('replace denied')

    monkeypatch.setattr(os, 'replace', fail_replace)
    with pytest.raises(ContentError) as caught:
        write_atomic(path, 'новый мир')
    assert caught.value.source == str(path)
    assert caught.value.path and caught.value.code
    assert path.read_bytes() == b'old output'
    assert list(tmp_path.iterdir()) == [path]


def test_write_failure_before_replace_keeps_existing_output(tmp_path, monkeypatch):
    from rpg_content import ContentError
    from rpg_content.io import write_atomic

    path = tmp_path / 'world.json'
    path.write_bytes(b'old output')

    def fail_sync(*args, **kwargs):
        raise OSError('disk sync failed')

    monkeypatch.setattr(os, 'fsync', fail_sync)
    with pytest.raises(ContentError) as caught:
        write_atomic(path, 'new output')
    assert caught.value.source == str(path)
    assert caught.value.code and caught.value.path
    assert path.read_bytes() == b'old output'
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_write_reports_missing_parent_without_creating_it(tmp_path):
    from rpg_content import ContentError
    from rpg_content.io import write_atomic

    path = tmp_path / 'missing' / 'world.json'
    with pytest.raises(ContentError) as caught:
        write_atomic(path, 'new output')
    assert caught.value.source == str(path)
    assert caught.value.code and caught.value.path
    assert not path.parent.exists()


def test_io_success_and_failures_do_not_print(tmp_path, capsys):
    from rpg_content import ContentError, load
    from rpg_content.io import serialize, write_atomic

    path = tmp_path / 'world.json'
    path.write_text('{"schema_version":1}', encoding='utf-8')
    write_atomic(path, serialize(load(path)))
    with pytest.raises(ContentError):
        load(tmp_path / 'missing.json')
    assert capsys.readouterr() == ('', '')
