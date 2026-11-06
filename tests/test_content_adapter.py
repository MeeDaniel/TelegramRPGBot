"""The combat catalog is an independent projection of validated content."""

import json
from copy import deepcopy
from random import Random

import pytest

from content_helpers import RARITIES, six_section_payload
from core import Accessory, Armor, AttackType, Potion, Rarity, Superpower, Weapon
from core.world import EncounterGenerator
from rpg_content import ContentRef, parse, validate


@pytest.fixture
def world():
    payload = six_section_payload()
    payload['items'][0].update(rarity='rare', attack_type='support', support_heal=19)
    payload['items'][1].update(guard_multiplier=1.75, bonus={'max_health': 31})
    payload['items'][3].update(duration=4, cooldown=6)
    payload['items'][4].update(heal_amount=37, cooldown=5)
    payload['monsters'][0]['is_boss'] = True
    return validate(parse(json.dumps(payload)))


def test_adapter_projects_all_item_kinds_and_mechanical_fields(world):
    from core.content_adapter import to_catalog

    catalog = to_catalog(world)
    sword, armor, ring, power, potion = catalog.items.values()
    assert isinstance(sword, Weapon)
    assert (sword.id, sword.name, sword.rarity, sword.attack_type, sword.support_heal) == (
        'sword', 'Меч', Rarity.RARE, AttackType.SUPPORT, 19)
    assert sword.bonus.melee_damage == 7
    assert isinstance(armor, Armor)
    assert (armor.guard_multiplier, armor.bonus.max_health) == (1.75, 31)
    assert isinstance(ring, Accessory) and ring.bonus.defense == -2
    assert isinstance(power, Superpower)
    assert (power.effect_bonus.magic_damage, power.duration, power.cooldown) == (5, 4, 6)
    assert isinstance(potion, Potion)
    assert (potion.heal_amount, potion.cooldown) == (37, 5)


def test_adapter_projects_ordered_loadouts_loot_and_encounter_locations(world):
    from core.content_adapter import to_catalog

    catalog = to_catalog(world)
    assert tuple(catalog.locations) == ('forest',)
    assert tuple(world.locations) == ('forest', 'bridge', 'empty')
    assert tuple(world.npcs) == ('mira', 'wanderer', 'guard')
    assert world.resolve(ContentRef('story_seeds', 'trail')).premise == 'Найти тропу.'
    monster = catalog.monsters['wolf']
    assert (monster.id, monster.name, monster.loot_table_id, monster.is_boss) == (
        'wolf', 'Волк', 'drops', True)
    assert tuple(r.value for r in monster.loadouts) == RARITIES
    for loadout in monster.loadouts.values():
        assert (loadout.weapon, loadout.armor, loadout.accessory1, loadout.accessory2,
                loadout.superpower, loadout.potion, loadout.potion_count) == (
                    'sword', 'armor', 'ring', 'ring', 'power', 'potion', 2)
        assert catalog.equip(loadout).weapon is catalog.items['sword']
    location = catalog.locations['forest']
    assert (location.id, location.name) == ('forest', 'Лес')
    assert [(spawn.monster_id, spawn.weight) for spawn in location.spawns] == [('wolf', 2)]
    assert tuple((r.value, w) for r, w in location.rarity_weights.items()) == tuple(
        zip(RARITIES, (60, 25, 10, 4, .9, .1)))
    table = catalog.loot_tables['drops']
    assert table.id == 'drops'
    assert [(entry.item_id, entry.chance, entry.min_quantity, entry.max_quantity)
            for entry in table.entries] == [('potion', .5, 1, 2)]


def test_adapter_mutable_catalogs_never_share_world_or_each_other(world):
    from core.content_adapter import to_catalog

    first, second = to_catalog(world), to_catalog(world)
    for section in ('items', 'monsters', 'locations', 'loot_tables'):
        assert getattr(first, section) is not getattr(second, section)
    first.monsters['wolf'].loadouts.clear()
    first.locations['forest'].rarity_weights.clear()
    first.items.clear()
    first.loot_tables.clear()
    assert tuple(second.items) == ('sword', 'armor', 'ring', 'power', 'potion')
    assert len(second.monsters['wolf'].loadouts) == len(world.monsters['wolf'].loadouts) == 6
    assert len(second.locations['forest'].rarity_weights) == len(world.locations['forest'].rarity_weights) == 6
    assert tuple(second.loot_tables) == tuple(world.loot_tables) == ('drops',)
    assert second.items['sword'] is not world.items['sword']


@pytest.mark.parametrize('weight', [1e308, 10**400], ids=['float', 'large-integer'])
def test_adapter_generates_encounters_with_overflowing_rarity_weight_total(weight):
    from core.content_adapter import to_catalog

    payload = six_section_payload()
    payload['locations'][0]['rarity_weights'] = dict.fromkeys(RARITIES, weight)
    world = validate(parse(json.dumps(payload)))
    generator = EncounterGenerator(to_catalog(world), Random(42))

    for _ in range(20):
        encounter = generator.generate('forest')
        assert encounter.definition.id == 'wolf'
        assert encounter.rarity.value in RARITIES

    assert dict(world.locations['forest'].rarity_weights) == dict.fromkeys(RARITIES, weight)
    assert tuple(spawn.weight for spawn in world.locations['forest'].spawns) == (2,)


@pytest.mark.parametrize('weights', [(1e308, 1e308), (10**400, 10**400), (10**400, 1.0)],
                         ids=['float', 'large-integer', 'mixed-integer-float'])
def test_adapter_generates_encounters_with_overflowing_spawn_weight_total(weights):
    from core.content_adapter import to_catalog

    payload = six_section_payload()
    second_monster = deepcopy(payload['monsters'][0])
    second_monster['id'] = 'second_wolf'
    payload['monsters'].append(second_monster)
    payload['locations'][0]['spawns'] = [
        {'monster': 'monsters:wolf', 'weight': weights[0]},
        {'monster': 'monsters:second_wolf', 'weight': weights[1]},
    ]
    world = validate(parse(json.dumps(payload)))
    generator = EncounterGenerator(to_catalog(world), Random(42))

    for _ in range(20):
        encounter = generator.generate('forest')
        assert encounter.definition.id in ('wolf', 'second_wolf')
        assert encounter.rarity.value in RARITIES

    assert tuple(spawn.weight for spawn in world.locations['forest'].spawns) == weights
    assert dict(world.locations['forest'].rarity_weights) == dict(
        zip(RARITIES, (60, 25, 10, 4, .9, .1)))
