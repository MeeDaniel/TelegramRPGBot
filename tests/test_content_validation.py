from copy import deepcopy
from dataclasses import replace
import json

import pytest

from content_helpers import RARITIES, SECTIONS, six_section_payload


def test_boolean_is_not_schema_version():
    from rpg_content import ContentError, parse

    with pytest.raises(ContentError):
        parse('{"schema_version":true}')


INVALID_FIELDS = [
    (('schema_version',), value) for value in (0, 2, 1.0, '1', None, True)
] + [
    (('canon',), None), (('canon',), 4),
    (('items',), {}), (('npcs',), None),
    (('items', 0, 'id'), ''), (('items', 0, 'id'), 'Bad'),
    (('items', 0, 'id'), 'a__b'), (('items', 0, 'id'), 'a_'),
    (('items', 0, 'name'), '  '), (('items', 0, 'name'), None),
    (('items', 0, 'description'), None), (('items', 0, 'kind'), 'wand'),
    (('items', 0, 'rarity'), 'ultra'), (('items', 0, 'rarity'), None),
    (('items', 0, 'bonus'), None), (('items', 0, 'bonus', 'defense'), True),
    (('items', 0, 'bonus', 'defense'), 1.5), (('items', 0, 'bonus', 'defense'), '1'),
    (('items', 0, 'attack_type'), 'beam'), (('items', 0, 'attack_type'), None),
    (('items', 0, 'support_heal'), 1), (('items', 0, 'support_heal'), -1),
    (('items', 0, 'support_heal'), True),
    (('items', 1, 'guard_multiplier'), 0), (('items', 1, 'guard_multiplier'), -0.1),
    (('items', 1, 'guard_multiplier'), True), (('items', 1, 'guard_multiplier'), '2'),
    (('items', 1, 'guard_multiplier'), float('inf')),
    (('items', 1, 'guard_multiplier'), float('nan')),
    (('items', 3, 'duration'), 0), (('items', 3, 'duration'), True),
    (('items', 3, 'cooldown'), -1), (('items', 3, 'cooldown'), 1.0),
    (('items', 3, 'effect_bonus', 'defense'), False),
    (('items', 4, 'heal_amount'), -1), (('items', 4, 'heal_amount'), False),
    (('items', 4, 'cooldown'), None),
    (('monsters', 0, 'is_boss'), 1), (('monsters', 0, 'loadouts'), {}),
    (('monsters', 0, 'loadouts', 'common'), None),
    (('monsters', 0, 'loadouts', 'common', 'potion_count'), -1),
    (('monsters', 0, 'loadouts', 'common', 'potion_count'), True),
    (('monsters', 0, 'loadouts', 'common', 'weapon'), 'sword'),
    (('monsters', 0, 'loadouts', 'common', 'weapon'), 'monsters:wolf'),
    (('monsters', 0, 'loot_table'), None),
    (('monsters', 0, 'loot_table'), 'items:sword'),
    (('locations', 0, 'mode'), 'peaceful'),
    (('locations', 0, 'spawns'), []), (('locations', 0, 'rarity_weights'), {}),
    (('locations', 0, 'spawns', 0, 'weight'), 0),
    (('locations', 0, 'spawns', 0, 'weight'), -1),
    (('locations', 0, 'spawns', 0, 'weight'), False),
    (('locations', 0, 'spawns', 0, 'weight'), float('-inf')),
    (('locations', 0, 'spawns', 0, 'monster'), 'items:sword'),
    (('locations', 0, 'rarity_weights', 'common'), -1),
    (('locations', 0, 'rarity_weights', 'common'), False),
    (('locations', 0, 'rarity_weights', 'common'), float('nan')),
    (('loot_tables', 0, 'entries'), None),
    (('loot_tables', 0, 'entries', 0, 'item'), 'npcs:mira'),
    (('loot_tables', 0, 'entries', 0, 'chance'), -0.01),
    (('loot_tables', 0, 'entries', 0, 'chance'), 1.01),
    (('loot_tables', 0, 'entries', 0, 'chance'), True),
    (('loot_tables', 0, 'entries', 0, 'chance'), float('inf')),
    (('loot_tables', 0, 'entries', 0, 'min_quantity'), 0),
    (('loot_tables', 0, 'entries', 0, 'min_quantity'), True),
    (('loot_tables', 0, 'entries', 0, 'max_quantity'), 1.0),
    (('loot_tables', 0, 'entries', 0, 'max_quantity'), 0),
    (('loot_tables', 0, 'entries', 0, 'min_quantity'), 3),
    (('npcs', 0, 'role'), ''), (('npcs', 0, 'role'), None),
    (('npcs', 0, 'location'), 'npcs:guard'),
    (('npcs', 0, 'lines'), 'hello'), (('npcs', 0, 'lines'), [None]),
    (('npcs', 0, 'lines'), [' ']), (('npcs', 0, 'refs'), [True]),
    (('story_seeds', 0, 'premise'), ' '), (('story_seeds', 0, 'premise'), None),
    (('story_seeds', 0, 'hooks'), ['']), (('story_seeds', 0, 'refs'), None),
]


def set_field(payload, path, value):
    parent = payload
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value


@pytest.mark.parametrize('path, value', INVALID_FIELDS)
def test_parser_rejects_invalid_types_enums_nulls_and_ranges(path, value):
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    set_field(payload, path, value)
    with pytest.raises(ContentError) as caught:
        parse(json.dumps(payload), source='invalid.json')
    assert caught.value.source == 'invalid.json'
    assert caught.value.path and caught.value.code


@pytest.mark.parametrize('section', SECTIONS)
@pytest.mark.parametrize('field', ['id', 'name'])
def test_every_section_requires_identity_fields(section, field):
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    del payload[section][0][field]
    with pytest.raises(ContentError) as caught:
        parse(json.dumps(payload), source='missing.json')
    assert caught.value.source == 'missing.json'
    assert section in caught.value.path
    assert field in str(caught.value)


@pytest.mark.parametrize('path', [
    ('schema_version',), ('items', 0, 'kind'), ('monsters', 0, 'loadouts'),
    ('monsters', 0, 'loot_table'), ('locations', 0, 'mode'),
    ('loot_tables', 0, 'entries'), ('loot_tables', 0, 'entries', 0, 'chance'),
    ('loot_tables', 0, 'entries', 0, 'item'), ('npcs', 0, 'role'),
    ('story_seeds', 0, 'premise'),
])
def test_required_fields_are_not_filled_by_defaults(path):
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    parent = payload
    for key in path[:-1]:
        parent = parent[key]
    del parent[path[-1]]
    with pytest.raises(ContentError):
        parse(json.dumps(payload))


@pytest.mark.parametrize('path', [(), ('items', 0), ('items', 0, 'bonus'),
    ('items', 3, 'effect_bonus'), ('monsters', 0), ('monsters', 0, 'loadouts'),
    ('monsters', 0, 'loadouts', 'common'), ('locations', 0),
    ('locations', 0, 'spawns', 0), ('locations', 0, 'rarity_weights'),
    ('loot_tables', 0), ('loot_tables', 0, 'entries', 0), ('npcs', 0), ('story_seeds', 0),
])
def test_unknown_fields_are_rejected_at_every_object_level(path):
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    target = payload
    for key in path:
        target = target[key]
    target['unexpected'] = 'secret'
    with pytest.raises(ContentError) as caught:
        parse(json.dumps(payload), source='extra.json')
    assert caught.value.source == 'extra.json'
    assert caught.value.path and caught.value.code
    if path:
        assert path[0] in caught.value.path


@pytest.mark.parametrize('raw', [
    '{"schema_version":1,"schema_version":1}',
    '{"schema_version":1,"npcs":[{"id":"a","id":"b","name":"A","role":"R"}]}',
    '{"schema_version":1,"items":[{"id":"a","name":"A","kind":"weapon","bonus":{"defense":1,"defense":2}}]}',
    '{"schema_version":1,"canon":NaN}', '{"schema_version":1,"canon":Infinity}',
    '{"schema_version":1,"canon":-Infinity}', '[]', 'null', '{',
])
def test_strict_json_rejects_duplicate_keys_nonfinite_constants_and_invalid_documents(raw):
    from rpg_content import ContentError, parse

    with pytest.raises(ContentError) as caught:
        parse(raw, source='strict.json')
    assert caught.value.source == 'strict.json'
    assert caught.value.path and caught.value.code


@pytest.mark.parametrize('section', SECTIONS)
def test_identical_duplicate_ids_are_rejected_in_every_section(section):
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    payload[section].append(deepcopy(payload[section][0]))
    with pytest.raises(ContentError):
        parse(json.dumps(payload))


@pytest.mark.parametrize('path', [('locations', 0, 'spawns'), ('loot_tables', 0, 'entries'),
                                  ('npcs', 0, 'refs'), ('story_seeds', 0, 'refs')])
def test_duplicate_spawn_loot_and_narrative_refs_are_rejected(path):
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    target = payload
    for key in path:
        target = target[key]
    target.append(deepcopy(target[0]))
    with pytest.raises(ContentError):
        parse(json.dumps(payload))


@pytest.mark.parametrize('section, key', [('monsters', 'loadouts'), ('locations', 'rarity_weights')])
@pytest.mark.parametrize('rarity', RARITIES)
def test_each_of_six_rarity_entries_is_required(section, key, rarity):
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    del payload[section][0][key][rarity]
    with pytest.raises(ContentError):
        parse(json.dumps(payload))


@pytest.mark.parametrize('kind, field, value', [
    ('weapon', 'guard_multiplier', 2), ('weapon', 'effect_bonus', {}),
    ('armor', 'attack_type', 'melee'), ('accessory', 'cooldown', 0),
    ('superpower', 'heal_amount', 50), ('potion', 'duration', 2),
])
def test_item_kind_does_not_accept_other_kinds_fields(kind, field, value):
    from rpg_content import ContentError, parse

    with pytest.raises(ContentError):
        parse(json.dumps({'schema_version': 1, 'items': [
            {'id': 'x', 'name': 'X', 'kind': kind, field: value},
        ]}))


def test_narrative_mode_rejects_encounter_mechanics_and_all_zero_weights():
    from rpg_content import ContentError, parse

    payload = six_section_payload()
    payload['locations'][0]['mode'] = 'narrative'
    with pytest.raises(ContentError):
        parse(json.dumps(payload))
    payload['locations'][0]['mode'] = 'encounter'
    payload['locations'][0]['rarity_weights'] = dict.fromkeys(RARITIES, 0)
    with pytest.raises(ContentError):
        parse(json.dumps(payload))


@pytest.mark.parametrize('slot, wrong', [('weapon', 'armor'), ('armor', 'sword'),
    ('accessory1', 'sword'), ('accessory2', 'power'), ('superpower', 'potion'), ('potion', 'ring')])
def test_world_rejects_existing_item_of_wrong_loadout_kind(slot, wrong):
    from rpg_content import ContentError, parse, validate

    payload = six_section_payload()
    payload['monsters'][0]['loadouts']['common'][slot] = f'items:{wrong}'
    document = parse(json.dumps(payload), source='slot.json')
    with pytest.raises(ContentError) as caught:
        validate(document)
    assert caught.value.source == 'slot.json'
    assert 'loadouts' in caught.value.path and slot in caught.value.path


def test_direct_world_also_rejects_existing_item_of_wrong_loadout_kind():
    from rpg_content import ContentError, ContentRef, parse, validate

    world = validate(parse(json.dumps(six_section_payload())))
    loadouts = dict(world.monsters['wolf'].loadouts)
    loadouts['common'] = replace(loadouts['common'], weapon=ContentRef('items', 'armor'))
    monster = replace(world.monsters['wolf'], loadouts=loadouts)
    with pytest.raises(ContentError):
        replace(world, monsters={'wolf': monster})


def test_potion_count_requires_potion_but_zero_with_nullable_slots_is_valid():
    from rpg_content import ContentError, parse, validate

    payload = six_section_payload()
    payload['monsters'][0]['loadouts']['common'] = {'potion_count': 1}
    with pytest.raises(ContentError):
        parse(json.dumps(payload))
    payload['monsters'][0]['loadouts']['common'] = {}
    world = validate(parse(json.dumps(payload)))
    loadout = world.monsters['wolf'].loadouts['common']
    assert loadout.potion is None and loadout.potion_count == 0
    assert loadout.weapon is None and loadout.armor is None


def test_valid_boundary_values_and_same_id_across_sections():
    from rpg_content import parse, validate

    payload = six_section_payload()
    payload['items'][0].update(attack_type='support', support_heal=1)
    payload['items'][3].update(duration=1, cooldown=0)
    payload['items'][4].update(heal_amount=0, cooldown=0)
    payload['loot_tables'][0]['entries'] = [
        {'item': 'items:sword', 'chance': 0}, {'item': 'items:potion', 'chance': 1},
    ]
    payload['locations'][0]['rarity_weights'] = dict.fromkeys(RARITIES, 0)
    payload['locations'][0]['rarity_weights']['mythic'] = 1
    payload['npcs'].append({'id': 'sword', 'name': 'Меч', 'role': 'Имя'})
    world = validate(parse(json.dumps(payload)))
    assert world.items['sword'].support_heal == 1
    assert world.npcs['sword'].role == 'Имя'
    assert [entry.chance for entry in world.loot_tables['drops'].entries] == [0, 1]


def test_parse_defers_dangling_refs_and_validate_reports_original_source():
    from rpg_content import ContentError, UnknownContentReference, parse, validate

    document = parse('{"schema_version":1,"npcs":[{"id":"mira","name":"Мира",'
                     '"role":"Картограф","location":"locations:bridge"}]}', source='addition.json')
    assert document.npcs['mira'].location.id == 'bridge'
    with pytest.raises(UnknownContentReference) as caught:
        validate(document)
    assert isinstance(caught.value, ContentError)
    assert (caught.value.section, caught.value.id) == ('locations', 'bridge')
    assert caught.value.source == 'addition.json'
    assert 'npcs' in caught.value.path and 'location' in caught.value.path
    assert caught.value.code


@pytest.mark.parametrize('path, ref', [
    (('monsters', 0, 'loot_table'), 'loot_tables:missing'),
    (('monsters', 0, 'loadouts', 'mythic', 'armor'), 'items:missing'),
    (('locations', 0, 'spawns', 0, 'monster'), 'monsters:missing'),
    (('loot_tables', 0, 'entries', 0, 'item'), 'items:missing'),
    (('npcs', 0, 'refs', 0), 'story_seeds:missing'),
    (('story_seeds', 0, 'refs', 0), 'npcs:missing'),
])
def test_full_graph_checks_every_reference_category(path, ref):
    from rpg_content import UnknownContentReference, parse, validate

    payload = six_section_payload()
    set_field(payload, path, ref)
    with pytest.raises(UnknownContentReference) as caught:
        validate(parse(json.dumps(payload), source='graph.json'))
    assert caught.value.source == 'graph.json'
    assert (caught.value.section, caught.value.id) == tuple(ref.split(':'))
    assert caught.value.path and caught.value.code


def test_merge_resolves_cross_document_cycles_and_preserves_input_order():
    from rpg_content import ContentRef, merge, parse

    first = parse('{"schema_version":1,"canon":"Лес","npcs":[{"id":"a","name":"A",'
                  '"role":"R","refs":["story_seeds:s"]}]}', source='first.json')
    second = parse('{"schema_version":1,"story_seeds":[{"id":"s","name":"S",'
                   '"premise":"P","refs":["npcs:a"]}],"npcs":[{"id":"b","name":"B","role":"R"}]}')
    world = merge(iter((first, second)))
    assert tuple(world.npcs) == ('a', 'b')
    assert world.canon == 'Лес'
    assert world.resolve(ContentRef('story_seeds', 's')).refs == (ContentRef('npcs', 'a'),)
    assert tuple(first.npcs) == ('a',) and not first.story_seeds
    assert tuple(second.npcs) == ('b',) and second.canon == ''


def test_validate_with_base_adds_without_mutating_base_or_document():
    from rpg_content import parse, validate

    base = validate(parse('{"schema_version":1,"canon":"Лес","locations":['
                          '{"id":"bridge","name":"Мост","mode":"narrative"}]}'))
    addition = parse('{"schema_version":1,"npcs":[{"id":"mira","name":"Мира",'
                     '"role":"Картограф","location":"locations:bridge"}]}')
    world = validate(addition, base=base)
    assert tuple(world.locations) == ('bridge',) and tuple(world.npcs) == ('mira',)
    assert world.canon == 'Лес'
    assert not base.npcs and not addition.locations and addition.canon == ''
    assert world.npcs_at('bridge') == (world.npcs['mira'],)


@pytest.mark.parametrize('section', SECTIONS)
def test_merge_rejects_identical_duplicate_ids_and_leaves_documents_unchanged(section):
    from rpg_content import ContentError, merge, parse

    payload = six_section_payload()
    first = parse(json.dumps(payload), source='first.json')
    second = parse(json.dumps({'schema_version': 1, section: payload[section]}), source='second.json')
    before = tuple(getattr(first, section))
    with pytest.raises(ContentError) as caught:
        merge((first, second))
    assert caught.value.source == 'second.json'
    assert section in caught.value.path and caught.value.code
    assert tuple(getattr(first, section)) == before


def test_merge_rejects_conflicting_canon_and_validate_base_duplicate():
    from rpg_content import ContentError, merge, parse, validate

    first = parse('{"schema_version":1,"canon":"A","npcs":[{"id":"a","name":"A","role":"R"}]}')
    second = parse('{"schema_version":1,"canon":"B"}')
    with pytest.raises(ContentError):
        merge((first, second))
    base = validate(first)
    with pytest.raises(ContentError):
        validate(first, base=base)
    assert tuple(base.npcs) == ('a',)


def test_empty_merge_and_omitted_sections_create_empty_version_one_world():
    from rpg_content import merge, parse, validate

    for world in (merge(iter(())), validate(parse('{"schema_version":1}'))):
        assert world.schema_version == 1 and world.canon == ''
        assert all(not getattr(world, section) for section in SECTIONS)


def test_library_parse_validate_merge_and_queries_are_silent(capsys):
    from rpg_content import ContentError, ContentRef, merge, parse, validate

    world = validate(parse(json.dumps(six_section_payload())))
    world.resolve(ContentRef('npcs', 'mira'))
    world.npcs_at('bridge')
    merge(())
    with pytest.raises(ContentError):
        parse('{bad')
    assert capsys.readouterr() == ('', '')


def test_merge_dangling_reference_reports_defining_document_not_last_input():
    from rpg_content import UnknownContentReference, merge, parse

    first = parse('{"schema_version":1,"npcs":[{"id":"mira","name":"Мира",'
                  '"role":"Картограф","location":"locations:missing"}]}', source='first.json')
    last = parse('{"schema_version":1}', source='last.json')
    with pytest.raises(UnknownContentReference) as caught:
        merge((first, last))
    assert caught.value.source == 'first.json'
    assert 'npcs' in caught.value.path and 'location' in caught.value.path


def test_json_integer_digit_limit_is_wrapped_in_public_content_error():
    from rpg_content import ContentError, parse

    # CPython may reject this before field validation; no raw ValueError leaks.
    with pytest.raises(ContentError) as caught:
        parse('{"schema_version":' + '9' * 5000 + '}', source='huge.json')
    assert caught.value.source == 'huge.json'
    assert caught.value.path and caught.value.code
