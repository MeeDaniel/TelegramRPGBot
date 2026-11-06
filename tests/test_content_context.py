"""Public context contracts, independent of the prompt's presentation layout."""

import json
from importlib import resources

import pytest


SECTIONS = ('items', 'monsters', 'locations', 'loot_tables', 'npcs', 'story_seeds')
RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic')


def context_payload():
    """Distinct markers expose accidental full-world or recursive disclosure."""
    return {
        'schema_version': 1,
        'canon': 'Луна над мостом — авторский канон 🌓.',
        'items': [{'id': 'hidden_blade', 'name': 'Клинок дозорного', 'kind': 'weapon',
                   'description': 'SECRET_ITEM_DESCRIPTION', 'bonus': {'melee_damage': 937}},
                  {'id': 'unselected_item', 'name': 'Лишний предмет', 'kind': 'accessory'}],
        'monsters': [{'id': 'hidden_beast', 'name': 'Зверь дозорного',
                      'description': 'SECRET_MONSTER_DESCRIPTION',
                      'loot_table': 'loot_tables:hidden_drops',
                      'loadouts': {rarity: {'weapon': 'items:hidden_blade'}
                                   for rarity in RARITIES}}],
        'locations': [{'id': 'bridge', 'name': 'Старый мост', 'mode': 'narrative',
                       'description': 'Мост над тихой рекой.'},
                      {'id': 'watch_forest', 'name': 'Дозорный лес', 'mode': 'encounter',
                       'description': 'Лес под луной.',
                       'spawns': [{'monster': 'monsters:hidden_beast', 'weight': 13}],
                       'rarity_weights': dict(zip(RARITIES, [1, 2, 3, 4, 5, 6]))},
                      {'id': 'unselected_location', 'name': 'Лишняя локация',
                       'mode': 'narrative'}],
        'loot_tables': [{'id': 'hidden_drops', 'name': 'Добыча дозорного',
                         'description': 'SECRET_LOOT_DESCRIPTION',
                         'entries': [{'item': 'items:hidden_blade', 'chance': 0.25}]}],
        'npcs': [{'id': 'mira', 'name': 'Мира', 'role': 'Картограф',
                  'description': 'Чертит карты при луне.', 'lines': ['Река помнит дорогу.'],
                  'location': 'locations:bridge', 'refs': ['story_seeds:first_hop']},
                 {'id': 'unselected_npc', 'name': 'Лишний собеседник', 'role': 'Прохожий',
                  'refs': ['story_seeds:first_hop']}],
        'story_seeds': [
            {'id': 'first_hop', 'name': 'Первая зацепка', 'premise': 'SECRET_FIRST_PREMISE',
             'hooks': ['SECRET_FIRST_HOOK'], 'refs': ['story_seeds:second_hop']},
            {'id': 'second_hop', 'name': 'Вторая зацепка', 'premise': 'SECRET_SECOND_PREMISE',
             'refs': ['npcs:unselected_npc']},
            {'id': 'indexed_seed', 'name': 'Индексированная зацепка',
             'premise': 'SECRET_INDEX_PREMISE', 'refs': ['story_seeds:second_hop']},
        ],
    }


@pytest.fixture
def world():
    from rpg_content import parse, validate

    return validate(parse(json.dumps(context_payload(), ensure_ascii=False)))


def build(world, **overrides):
    from rpg_content import build_context

    options = {'section': 'npcs', 'task': 'Добавь хранителя моста 🗺.', 'max_chars': 100_000}
    options.update(overrides)
    return build_context(world, **options)


def test_task_canon_and_selected_npc_details_are_available(world):
    from rpg_content import ContentRef

    text = build(world, refs=(ContentRef('npcs', 'mira'),))
    for marker in ('Добавь хранителя моста 🗺.', world.canon, 'mira', 'Картограф',
                   'Чертит карты при луне.', 'Река помнит дорогу.', 'bridge', 'first_hop'):
        assert marker in text
    for marker in ('unselected_npc', 'unselected_location', 'unselected_item',
                   'indexed_seed', 'second_hop', 'SECRET_FIRST_PREMISE', 'SECRET_FIRST_HOOK'):
        assert marker not in text


def test_explicit_second_selection_reveals_details_without_recursive_expansion(world):
    from rpg_content import ContentRef

    text = build(world, refs=(ContentRef('npcs', 'mira'), ContentRef('story_seeds', 'first_hop')))
    assert 'SECRET_FIRST_PREMISE' in text
    assert 'SECRET_FIRST_HOOK' in text
    assert 'second_hop' in text
    assert 'SECRET_SECOND_PREMISE' not in text


def test_repeated_direct_target_is_summarized_once(world):
    from rpg_content import ContentRef, parse, validate

    payload = context_payload()
    payload['npcs'].append({'id': 'guard', 'name': 'Страж', 'role': 'Охрана',
                            'location': 'locations:bridge', 'refs': ['story_seeds:first_hop']})
    shared = validate(parse(json.dumps(payload, ensure_ascii=False)))
    text = build(shared, refs=(ContentRef('npcs', 'mira'), ContentRef('npcs', 'guard')))
    assert text.count('Первая зацепка') == 1
    assert text.count('Старый мост') == 1
    assert 'second_hop' not in text


def test_index_grants_reference_scope_without_revealing_record_details(world):
    from rpg_content import ContentRef

    empty = build(world)
    scoped = build(world, index_refs=(ContentRef('story_seeds', 'indexed_seed'),))
    assert 'indexed_seed' not in empty
    assert 'indexed_seed' in scoped
    assert 'Индексированная зацепка' in scoped
    assert 'SECRET_INDEX_PREMISE' not in scoped
    assert 'second_hop' not in scoped
    assert 'unselected_npc' not in scoped
    assert 'unselected_location' not in scoped


@pytest.mark.parametrize('section', ['npcs', 'story_seeds'])
def test_narrative_location_profile_never_exposes_encounter_or_loadout_data(world, section):
    from rpg_content import ContentRef

    text = build(world, section=section, refs=(ContentRef('locations', 'watch_forest'),))
    assert 'watch_forest' in text
    assert 'Лес под луной.' in text
    for hidden in ('hidden_beast', 'hidden_blade', 'hidden_drops', 'SECRET_MONSTER_DESCRIPTION',
                   'SECRET_ITEM_DESCRIPTION', 'SECRET_LOOT_DESCRIPTION', 'loadouts',
                   'rarity_weights', 'spawns'):
        assert hidden not in text


def test_mechanical_location_keeps_spawns_but_only_summarizes_direct_monster(world):
    from rpg_content import ContentRef

    text = build(world, section='locations', refs=(ContentRef('locations', 'watch_forest'),))
    for visible in ('watch_forest', 'hidden_beast', 'Зверь дозорного', 'spawns', 'rarity_weights'):
        assert visible in text
    for hidden in ('hidden_drops', 'hidden_blade', 'SECRET_MONSTER_DESCRIPTION', 'loadouts'):
        assert hidden not in text


def test_mechanical_monster_keeps_loadout_and_summarizes_direct_targets(world):
    from rpg_content import ContentRef

    text = build(world, section='monsters', refs=(ContentRef('monsters', 'hidden_beast'),))
    for visible in ('hidden_beast', 'SECRET_MONSTER_DESCRIPTION', 'loadouts', 'hidden_blade',
                    'Клинок дозорного', 'hidden_drops', 'Добыча дозорного'):
        assert visible in text
    assert 'SECRET_ITEM_DESCRIPTION' not in text
    assert 'SECRET_LOOT_DESCRIPTION' not in text
    assert '937' not in text


def test_selected_item_exposes_mechanical_bonus(world):
    from rpg_content import ContentRef

    text = build(world, section='items', refs=(ContentRef('items', 'hidden_blade'),))
    for visible in ('hidden_blade', 'SECRET_ITEM_DESCRIPTION', 'melee_damage', '937'):
        assert visible in text
    assert 'unselected_item' not in text


def test_selected_loot_keeps_entries_without_expanding_item_mechanics(world):
    from rpg_content import ContentRef

    text = build(world, section='loot_tables', refs=(ContentRef('loot_tables', 'hidden_drops'),))
    for visible in ('hidden_drops', 'SECRET_LOOT_DESCRIPTION', 'entries', '0.25',
                    'hidden_blade', 'Клинок дозорного'):
        assert visible in text
    assert 'SECRET_ITEM_DESCRIPTION' not in text
    assert '937' not in text


def test_selected_story_keeps_hooks_and_stops_at_direct_target(world):
    from rpg_content import ContentRef

    text = build(world, section='story_seeds', refs=(ContentRef('story_seeds', 'first_hop'),))
    for visible in ('first_hop', 'SECRET_FIRST_PREMISE', 'SECRET_FIRST_HOOK',
                    'second_hop', 'Вторая зацепка'):
        assert visible in text
    assert 'SECRET_SECOND_PREMISE' not in text
    assert 'unselected_npc' not in text


@pytest.mark.parametrize('section', SECTIONS)
def test_only_selected_rule_and_example_are_bundled_into_context(world, section):
    from rpg_content import parse

    root = resources.files('rpg_content').joinpath('resources')
    common = root.joinpath('common.md').read_text(encoding='utf-8').strip()
    rule = root.joinpath(section + '.md').read_text(encoding='utf-8').strip()
    example = root.joinpath('examples', section + '.json').read_text(encoding='utf-8').strip()
    assert common and rule and example
    document = parse(example, source='bundled:' + section)
    assert getattr(document, section)
    assert all(not getattr(document, other) for other in SECTIONS if other != section)
    text = build(world, section=section)
    assert common in text
    assert rule in text
    assert example in text
    for other in SECTIONS:
        if other != section:
            other_rule = root.joinpath(other + '.md').read_text(encoding='utf-8').strip()
            assert other_rule not in text


def test_unicode_budget_accepts_exact_length_and_rejects_one_character_less(world):
    from rpg_content import ContextBudgetExceeded

    full = build(world)
    assert len(full.encode('utf-8')) > len(full)
    assert build(world, max_chars=len(full)) == full
    with pytest.raises(ContextBudgetExceeded) as raised:
        build(world, max_chars=len(full) - 1)
    assert raised.value.actual_chars == len(full)
    assert raised.value.max_chars == len(full) - 1


@pytest.mark.parametrize('options', [
    {'section': ''}, {'section': 'quests'}, {'section': None},
    {'task': ''}, {'task': ' \t\n'}, {'task': None}, {'task': True},
    {'max_chars': True}, {'max_chars': False}, {'max_chars': 0}, {'max_chars': -1},
    {'max_chars': 4.5}, {'max_chars': '1000'},
])
def test_invalid_public_context_arguments_raise_domain_error(world, options):
    from rpg_content import ContentError

    with pytest.raises(ContentError):
        build(world, **options)


@pytest.mark.parametrize('argument', ['refs', 'index_refs'])
def test_unknown_context_reference_preserves_domain_identity(world, argument):
    from rpg_content import ContentRef, UnknownContentReference

    with pytest.raises(UnknownContentReference) as raised:
        build(world, **{argument: (ContentRef('npcs', 'missing_npc'),)})
    assert raised.value.section == 'npcs'
    assert raised.value.id == 'missing_npc'


def test_library_context_success_and_failures_are_silent(world, capsys):
    from rpg_content import ContentError

    build(world)
    with pytest.raises(ContentError):
        build(world, max_chars=1)
    with pytest.raises(ContentError):
        build(world, task='')
    captured = capsys.readouterr()
    assert captured.out == captured.err == ''
