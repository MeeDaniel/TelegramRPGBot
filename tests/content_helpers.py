"""Literal independent worlds and legacy characterization utilities for tests."""

from dataclasses import fields, is_dataclass
from enum import Enum

RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic')
SECTIONS = ('items', 'monsters', 'locations', 'loot_tables', 'npcs', 'story_seeds')


def six_section_payload():
    return {
        'schema_version': 1,
        'canon': 'Мост у леса.',
        'items': [
            {'id': 'sword', 'name': 'Меч', 'kind': 'weapon', 'bonus': {'melee_damage': 7}},
            {'id': 'armor', 'name': 'Броня', 'kind': 'armor'},
            {'id': 'ring', 'name': 'Кольцо', 'kind': 'accessory', 'bonus': {'defense': -2}},
            {'id': 'power', 'name': 'Дар', 'kind': 'superpower', 'effect_bonus': {'magic_damage': 5}},
            {'id': 'potion', 'name': 'Зелье', 'kind': 'potion'},
        ],
        'monsters': [{
            'id': 'wolf', 'name': 'Волк', 'loot_table': 'loot_tables:drops',
            'loadouts': {rarity: {
                'weapon': 'items:sword', 'armor': 'items:armor',
                'accessory1': 'items:ring', 'accessory2': 'items:ring',
                'superpower': 'items:power', 'potion': 'items:potion', 'potion_count': 2,
            } for rarity in RARITIES},
        }],
        'locations': [
            {'id': 'forest', 'name': 'Лес', 'mode': 'encounter',
             'spawns': [{'monster': 'monsters:wolf', 'weight': 2}],
             'rarity_weights': dict(zip(RARITIES, [60, 25, 10, 4, 0.9, 0.1]))},
            {'id': 'bridge', 'name': 'Мост', 'mode': 'narrative'},
            {'id': 'empty', 'name': 'Пустырь', 'mode': 'narrative'},
        ],
        'loot_tables': [{'id': 'drops', 'name': 'Добыча', 'entries': [
            {'item': 'items:potion', 'chance': 0.5, 'min_quantity': 1, 'max_quantity': 2},
        ]}],
        'npcs': [
            {'id': 'mira', 'name': 'Мира', 'role': 'Картограф', 'location': 'locations:bridge',
             'lines': ['След исчез.'], 'refs': ['story_seeds:trail']},
            {'id': 'wanderer', 'name': 'Странник', 'role': 'Путник'},
            {'id': 'guard', 'name': 'Страж', 'role': 'Охрана', 'location': 'locations:bridge'},
        ],
        'story_seeds': [{'id': 'trail', 'name': 'След', 'premise': 'Найти тропу.',
                         'hooks': ['Спросить Миру.'], 'refs': ['npcs:mira']}],
    }


def normalize_legacy(value):
    """Preserve domain subtypes, every field, numeric values/types and order."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {'type': type(value).__name__, **{
            field.name: normalize_legacy(getattr(value, field.name)) for field in fields(value)
        }}
    if isinstance(value, dict):
        return {normalize_legacy(key): normalize_legacy(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalize_legacy(item) for item in value]
    return value


def legacy_traces(catalog, seed):
    from random import Random
    from core import Rarity
    from core.world import EncounterGenerator, LootGenerator

    rng = Random(seed)
    encounters = EncounterGenerator(catalog, rng)
    loot = LootGenerator(catalog, rng)
    trace = []
    for _ in range(5):
        spawn = encounters.generate('forgotten_forest')
        trace.append({
            'monster': spawn.definition.id, 'rarity': spawn.rarity.value,
            'loot': normalize_legacy(loot.roll(spawn.definition.id, spawn.rarity)),
        })
    exhaustive_loot = LootGenerator(catalog, Random(seed))
    return {'encounters_with_shared_rng_loot': trace, 'all_monster_rarity_loot': [
        {'monster': monster, 'rarity': rarity.value,
         'rolls': [normalize_legacy(exhaustive_loot.roll(monster, rarity)) for _ in range(2)]}
        for monster in catalog.monsters for rarity in Rarity
    ]}
