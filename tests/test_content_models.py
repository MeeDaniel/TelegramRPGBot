"""Public snapshot contracts; imports stay in tests to preserve useful RED runs."""

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from content_helpers import RARITIES, SECTIONS, six_section_payload


def test_public_world_resolves_npc_with_nullable_location():
    from rpg_content import ContentRef, parse, validate

    world = validate(parse('{"schema_version":1,"npcs":[{"id":"mira","name":"Мира","role":"Картограф"}]}'))
    assert world.resolve(ContentRef.parse('npcs:mira')) is world.npcs['mira']
    assert world.npcs['mira'].location is None


def test_all_six_sections_resolve_and_npc_queries_preserve_order():
    from rpg_content import ContentRef, parse, validate

    world = validate(parse(json.dumps(six_section_payload())))
    for section in SECTIONS:
        assert getattr(world, section)
        for identifier, definition in getattr(world, section).items():
            assert world.resolve(ContentRef(section, identifier)) is definition
    assert tuple(world.locations) == ('forest', 'bridge', 'empty')
    assert tuple(npc.id for npc in world.npcs_at('bridge')) == ('mira', 'guard')
    assert world.npcs_at('empty') == ()
    assert world.npcs['wanderer'].location is None
    assert isinstance(world.npcs['mira'].location, ContentRef)
    assert world.story_seeds['trail'].refs == (ContentRef('npcs', 'mira'),)


def test_mapping_missing_key_and_domain_query_errors_are_distinct():
    from rpg_content import ContentError, ContentRef, UnknownContentReference, parse, validate

    world = validate(parse(json.dumps(six_section_payload())))
    with pytest.raises(KeyError):
        world.npcs['missing']
    for action, section in [(lambda: world.resolve(ContentRef('npcs', 'missing')), 'npcs'),
                            (lambda: world.npcs_at('missing'), 'locations')]:
        with pytest.raises(UnknownContentReference) as caught:
            action()
        assert isinstance(caught.value, ContentError)
        assert (caught.value.section, caught.value.id) == (section, 'missing')
        assert caught.value.source == '<memory>'
        assert caught.value.path and caught.value.code


@pytest.mark.parametrize('text', ['npcs:mira', 'items:sword', 'story_seeds:trail_2'])
def test_content_ref_value_object_roundtrip(text):
    from rpg_content import ContentRef

    section, identifier = text.split(':')
    assert ContentRef.parse(text) == ContentRef(section, identifier)
    assert hash(ContentRef.parse(text)) == hash(ContentRef(section, identifier))


@pytest.mark.parametrize('text', ['', 'npcs', 'npcs:', ':mira', 'npc:mira', 'npcs:a:b',
                                  'npcs:Mira', 'npcs:_mira', 'npcs:mira__a', 'npcs:mira_',
                                  ' npcs:mira', 'npcs:миpa', None, 1, True])
def test_content_ref_rejects_malformed_values(text):
    from rpg_content import ContentError, ContentRef

    with pytest.raises(ContentError):
        ContentRef.parse(text)


@pytest.mark.parametrize('section, identifier', [('npc', 'mira'), ('npcs', 'Bad'),
                                                 ('npcs', True), (None, 'mira')])
def test_content_ref_direct_constructor_checks_local_rules(section, identifier):
    from rpg_content import ContentError, ContentRef

    with pytest.raises(ContentError):
        ContentRef(section, identifier)


def test_item_defaults_are_kind_specific_and_negative_bonuses_are_valid():
    from rpg_content import parse, validate

    world = validate(parse(json.dumps(six_section_payload())))
    assert dict(world.items['sword'].bonus) == {
        'melee_damage': 7, 'magic_damage': 0, 'ranged_damage': 0, 'max_health': 0, 'defense': 0,
    }
    assert world.items['sword'].attack_type == 'melee'
    assert world.items['sword'].support_heal == 0
    assert world.items['armor'].guard_multiplier == 2.0
    assert world.items['ring'].bonus['defense'] == -2
    assert (world.items['power'].duration, world.items['power'].cooldown) == (2, 3)
    assert (world.items['potion'].heal_amount, world.items['potion'].cooldown) == (50, 3)
    assert tuple(world.monsters['wolf'].loadouts) == RARITIES


@pytest.mark.parametrize('construction', ['direct', 'replace'])
@pytest.mark.parametrize('kind, field, default', [
    ('weapon', 'attack_type', 'melee'),
    ('weapon', 'support_heal', 0),
    ('armor', 'guard_multiplier', 2.0),
    ('superpower', 'effect_bonus', {
        'melee_damage': 0, 'magic_damage': 0, 'ranged_damage': 0,
        'max_health': 0, 'defense': 0,
    }),
    ('superpower', 'duration', 2),
    ('superpower', 'cooldown', 3),
    ('potion', 'heal_amount', 50),
    ('potion', 'cooldown', 3),
])
def test_item_constructor_rejects_explicit_null_but_defaults_omitted_fields(
        construction, kind, field, default):
    from rpg_content import ContentError, ItemDefinition

    omitted = ItemDefinition(id='item', name='Предмет', kind=kind)
    assert getattr(omitted, field) == default
    assert getattr(replace(omitted), field) == default

    with pytest.raises(ContentError):
        if construction == 'direct':
            ItemDefinition(id='item', name='Предмет', kind=kind, **{field: None})
        else:
            replace(omitted, **{field: None})


def test_direct_location_nested_error_text_contains_its_current_path():
    from rpg_content import ContentError, ContentRef, LocationDefinition

    with pytest.raises(ContentError) as caught:
        LocationDefinition(
            id='forest', name='Лес', mode='encounter',
            spawns=[{'monster': ContentRef('monsters', 'x'), 'weight': -1}],
            rarity_weights={rarity: 1 for rarity in RARITIES},
        )

    error = caught.value
    assert error.path.endswith('.spawns[0].weight')
    assert error.path in str(error)


def test_direct_constructors_detach_caller_owned_collections_recursively():
    from rpg_content import ContentRef, ContentWorld, LocationDefinition, NpcDefinition, parse, validate

    parsed = validate(parse(json.dumps(six_section_payload())))
    weights = dict(parsed.locations['forest'].rarity_weights)
    spawns = list(parsed.locations['forest'].spawns)
    forest = LocationDefinition(id='forest', name='Лес', mode='encounter',
                                spawns=spawns, rarity_weights=weights)
    lines = ['Старая реплика']
    refs = [ContentRef('locations', 'forest')]
    npc = NpcDefinition(id='mira', name='Мира', role='Картограф', lines=lines, refs=refs)
    bonus = {'defense': 8}
    item = replace(parsed.items['ring'], bonus=bonus)
    effects = {'magic_damage': 6}
    power = replace(parsed.items['power'], effect_bonus=effects)
    loadouts = dict(parsed.monsters['wolf'].loadouts)
    monster = replace(parsed.monsters['wolf'], loadouts=loadouts)
    entries = list(parsed.loot_tables['drops'].entries)
    loot = replace(parsed.loot_tables['drops'], entries=entries)
    hooks = ['Первый крючок']
    seed_refs = [ContentRef('npcs', 'mira')]
    story = replace(parsed.story_seeds['trail'], hooks=hooks, refs=seed_refs)
    items = dict(parsed.items)
    items.update(ring=item, power=power)
    npcs = {'mira': npc}
    world = ContentWorld(items=items, monsters={'wolf': monster},
                         locations={'forest': forest}, loot_tables={'drops': loot},
                         npcs=npcs, story_seeds={'trail': story})
    document = replace(parse(json.dumps(six_section_payload())), npcs=npcs)
    weights['common'] = 999
    spawns.clear()
    lines.append('Поздняя реплика')
    refs.clear()
    bonus['defense'] = 900
    effects['magic_damage'] = 900
    loadouts.clear()
    entries.clear()
    hooks.clear()
    seed_refs.clear()
    items.clear()
    npcs.clear()
    assert forest.rarity_weights['common'] == 60
    assert len(forest.spawns) == 1
    assert npc.lines == ('Старая реплика',)
    assert npc.refs == (ContentRef('locations', 'forest'),)
    assert item.bonus['defense'] == 8
    assert power.effect_bonus['magic_damage'] == 6
    assert tuple(monster.loadouts) == RARITIES
    assert len(loot.entries) == 1
    assert story.hooks == ('Первый крючок',)
    assert story.refs == (ContentRef('npcs', 'mira'),)
    assert tuple(world.items) == ('sword', 'armor', 'ring', 'power', 'potion')
    assert tuple(world.npcs) == ('mira',)
    assert tuple(document.npcs) == ('mira',)


def test_snapshot_exposes_no_writable_nested_collections():
    from rpg_content import parse, validate

    document = parse(json.dumps(six_section_payload()))
    world = validate(document)
    mappings = [getattr(owner, section) for owner in (document, world) for section in SECTIONS]
    mappings += [world.items['sword'].bonus, world.items['power'].effect_bonus,
                 world.monsters['wolf'].loadouts, world.locations['forest'].rarity_weights]
    for mapping in mappings:
        with pytest.raises(TypeError):
            mapping['intruder'] = None
    for owner, attr in [(world.npcs['mira'], 'lines'), (world.npcs['mira'], 'refs'),
                        (world.story_seeds['trail'], 'hooks'),
                        (world.story_seeds['trail'], 'refs'),
                        (world.locations['forest'], 'spawns'), (world.loot_tables['drops'], 'entries')]:
        assert isinstance(getattr(owner, attr), tuple)
    frozen_objects = [world, document, world.npcs['mira'], world.npcs['mira'].location,
                      world.monsters['wolf'].loadouts['common'],
                      world.locations['forest'].spawns[0], world.loot_tables['drops'].entries[0]]
    for obj in frozen_objects:
        attr = next(iter(obj.__dataclass_fields__))
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            setattr(obj, attr, None)


@pytest.mark.parametrize('section, identifier, changes', [
    ('items', 'sword', {'id': 'Bad'}), ('items', 'sword', {'support_heal': 1}),
    ('items', 'sword', {'bonus': {'defense': True}}),
    ('items', 'armor', {'guard_multiplier': 0}),
    ('items', 'power', {'duration': 0}), ('items', 'potion', {'cooldown': -1}),
    ('monsters', 'wolf', {'loadouts': {}}), ('monsters', 'wolf', {'is_boss': 1}),
    ('locations', 'forest', {'spawns': ()}), ('locations', 'forest', {'rarity_weights': {}}),
    ('npcs', 'mira', {'role': '  '}), ('npcs', 'mira', {'lines': ['']}),
    ('story_seeds', 'trail', {'premise': ''}), ('story_seeds', 'trail', {'hooks': ['']}),
])
def test_direct_definition_reconstruction_cannot_bypass_local_invariants(section, identifier, changes):
    from rpg_content import ContentError, parse, validate

    world = validate(parse(json.dumps(six_section_payload())))
    with pytest.raises(ContentError) as caught:
        replace(getattr(world, section)[identifier], **changes)
    assert caught.value.source == '<memory>'
    assert caught.value.path and caught.value.code


def test_nested_value_object_reconstruction_checks_ranges_and_refs():
    from rpg_content import ContentError, ContentRef, parse, validate

    world = validate(parse(json.dumps(six_section_payload())))
    cases = [
        (world.monsters['wolf'].loadouts['common'], {'potion': None, 'potion_count': 1}),
        (world.locations['forest'].spawns[0], {'weight': False}),
        (world.locations['forest'].spawns[0], {'monster': ContentRef('items', 'sword')}),
        (world.loot_tables['drops'].entries[0], {'chance': float('inf')}),
        (world.loot_tables['drops'].entries[0], {'min_quantity': 3, 'max_quantity': 2}),
    ]
    for obj, changes in cases:
        with pytest.raises(ContentError):
            replace(obj, **changes)


def test_direct_world_enforces_key_identity_and_graph():
    from rpg_content import ContentError, ContentRef, ContentWorld, NpcDefinition

    npc = NpcDefinition(id='mira', name='Мира', role='Картограф')
    with pytest.raises(ContentError):
        ContentWorld(npcs={'wrong_key': npc})
    dangling = replace(npc, location=ContentRef('locations', 'missing'))
    with pytest.raises(ContentError):
        ContentWorld(npcs={'mira': dangling})
    with pytest.raises(ContentError):
        ContentWorld(schema_version=True)


def test_empty_world_defaults_are_independent_and_read_only():
    from rpg_content import ContentWorld

    first, second = ContentWorld(), ContentWorld()
    assert first.schema_version == 1 and first.canon == ''
    for section in SECTIONS:
        assert dict(getattr(first, section)) == dict(getattr(second, section)) == {}
        with pytest.raises(TypeError):
            getattr(first, section)['new'] = None
