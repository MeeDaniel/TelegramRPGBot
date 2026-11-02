from random import Random
from uuid import uuid4

import pytest

from core import (
    Attack, Battle, BattleEngine, BattleParticipant, BattleStatus,
    Character, Controller, DrinkPotion, Equipment, GameService, Guard,
    LootTable, Potion, StatBonus, Superpower, UseSuperpower, Weapon,
)
from main import create_content, create_player


def player_game():
    catalog = create_content()
    for table_id in catalog.loot_tables:
        catalog.loot_tables[table_id] = LootTable(table_id, ())
    game = GameService(catalog, rng=Random(2))
    return game, create_player(game, False)


def encounter(game, character):
    battle = game.create_pve(character.id, 'forgotten_forest')
    hero = next(p for p in battle.participants.values()
                if p.character_id == character.id)
    enemy = next(p for p in battle.participants.values()
                 if p.character_id is None)
    return battle, hero, enemy


def slot_values(character):
    return tuple(getattr(character.slots, name) for name in (
        'weapon', 'armor', 'accessory1', 'accessory2', 'superpower', 'potion_id',
    ))


def test_starting_potions_cannot_be_spent_outside_active_battle():
    game, character = player_game()
    battle, hero, _ = encounter(game, character)
    inventory = character.inventory
    assert inventory.consumables['healing_potion'] == 3
    assert hero.potions_left == 3
    pending_actions = dict(battle.actions)

    with pytest.raises(ValueError):
        inventory.consume('healing_potion')

    assert inventory.consumables['healing_potion'] == 3
    assert hero.potions_left == 3
    assert hero.current_hp == 160
    assert battle.round_number == 1
    assert battle.actions == pending_actions


def test_added_unreserved_potions_can_be_spent_without_breaking_battle_use():
    game, character = player_game()
    battle, hero, enemy = encounter(game, character)
    inventory = character.inventory
    inventory.add_consumable('healing_potion', 2)
    inventory.consume('healing_potion', 2)

    with pytest.raises(ValueError):
        inventory.consume('healing_potion')

    battle.actions[enemy.id] = Guard()
    events = game.submit_action(battle.id, hero.id, DrinkPotion())
    assert sum(event.kind == 'potion_used' for event in events) == 1
    assert inventory.consumables['healing_potion'] == 2
    assert hero.potions_left == 2
    assert battle.round_number == 2

    battle.actions[enemy.id] = Guard()
    game.submit_action(battle.id, hero.id, Guard())
    assert inventory.consumables['healing_potion'] == 2
    assert hero.potions_left == 2


def test_replaying_potion_events_does_not_charge_inventory_again():
    game, character = player_game()
    battle, hero, enemy = encounter(game, character)
    battle.actions[enemy.id] = Guard()
    events = game.submit_action(battle.id, hero.id, DrinkPotion())
    assert character.inventory.consumables['healing_potion'] == 2
    assert hero.potions_left == 2

    game._process_events(battle, events)

    assert character.inventory.consumables['healing_potion'] == 2
    assert hero.potions_left == 2


def test_potion_is_spent_once_and_unused_stock_released_when_drinker_dies():
    game, character = player_game()
    battle, hero, enemy = encounter(game, character)
    hero.current_hp = 1
    enemy.equipment = Equipment(weapon=Weapon(
        id='fatal_sword', name='Fatal sword',
        bonus=StatBonus(melee_damage=999),
    ))
    battle.actions[enemy.id] = Attack(hero.id)

    events = game.submit_action(battle.id, hero.id, DrinkPotion())

    assert sum(event.kind == 'potion_used' for event in events) == 1
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team == battle.enemy_team
    assert hero.current_hp == 0
    assert hero.potions_left == 2
    assert character.inventory.consumables['healing_potion'] == 2
    character.inventory.consume('healing_potion', 2)
    assert character.inventory.consumables['healing_potion'] == 0


def test_consumable_totals_cannot_be_rewritten_to_defeat_reservation():
    game, character = player_game()
    _, hero, _ = encounter(game, character)
    with pytest.raises(TypeError):
        character.inventory.consumables['healing_potion'] = 0
    assert character.inventory.consumables['healing_potion'] == 3
    assert hero.potions_left == 3


@pytest.mark.parametrize('outcome', ['win', 'loss', 'draw', 'cancel', 'leave'])
def test_unused_potions_are_released_when_character_exits_battle(outcome):
    game, character = player_game()
    battle, hero, enemy = encounter(game, character)
    if outcome == 'cancel':
        game.cancel(battle.id, hero.id)
        assert battle.status == BattleStatus.CANCELLED
    elif outcome == 'leave':
        game.leave(battle.id, hero.id)
        assert not hero.active
        assert battle.status == BattleStatus.FINISHED
    else:
        if outcome in ('loss', 'draw'):
            hero.current_hp = 1
        if outcome in ('win', 'draw'):
            enemy.current_hp = 1
        battle.actions[enemy.id] = Attack(hero.id)
        action = Guard() if outcome == 'loss' else Attack(enemy.id)
        game.submit_action(battle.id, hero.id, action)
        assert battle.status == BattleStatus.FINISHED
        assert battle.winner_team == {
            'win': battle.player_team, 'loss': battle.enemy_team, 'draw': None,
        }[outcome]

    assert character.inventory.consumables['healing_potion'] == 3
    character.inventory.consume('healing_potion', 3)
    assert character.inventory.consumables['healing_potion'] == 0


@pytest.mark.parametrize('mutation', ['slot_assignment', 'slots_replacement'])
def test_character_equipment_view_cannot_bypass_duplicate_instance_validation(mutation):
    game, character = player_game()
    original_slots = slot_values(character)
    with pytest.raises(AttributeError):
        if mutation == 'slot_assignment':
            character.slots.accessory2 = character.slots.accessory1
        else:
            character.slots = Character(name='other').slots

    assert slot_values(character) == original_slots
    _, hero, _ = encounter(game, character)
    assert hero.stats(1).melee_damage == 34
    assert hero.stats(1).max_health == 160


@pytest.mark.parametrize('invalid_equip', ['duplicate', 'wrong_type', 'unowned', 'active_battle'])
def test_invalid_equipment_changes_preserve_all_slots(invalid_equip):
    game, character = player_game()
    if invalid_equip == 'active_battle':
        encounter(game, character)
    original_slots = slot_values(character)
    slot, item_id = {
        'duplicate': ('accessory2', character.slots.accessory1),
        'wrong_type': ('armor', character.slots.weapon),
        'unowned': ('weapon', uuid4()),
        'active_battle': ('weapon', None),
    }[invalid_equip]
    with pytest.raises(ValueError):
        game.equip(character.id, slot, item_id)
    assert slot_values(character) == original_slots


def test_service_can_unequip_and_equip_distinct_instances_of_same_accessory():
    game, character = player_game()
    game.equip(character.id, 'accessory2', None)
    assert character.slots.accessory2 is None
    second_ring = character.inventory.add_item('power_ring')
    game.equip(character.id, 'accessory2', second_ring)
    assert character.slots.accessory2 == second_ring
    assert character.slots.accessory1 != second_ring
    _, hero, _ = encounter(game, character)
    assert hero.stats(1).melee_damage == 37
    assert hero.stats(1).max_health == 135


@pytest.mark.parametrize('potion_id', ['missing_potion', 'steel_sword', uuid4(), 42, []])
def test_invalid_potion_selection_raises_value_error_without_losing_previous_choice(potion_id):
    game, character = player_game()
    with pytest.raises(ValueError):
        game.equip(character.id, 'potion_id', potion_id)
    assert character.slots.potion_id == 'healing_potion'
    assert character.inventory.consumables['healing_potion'] == 3


def test_potion_can_be_unequipped_with_none():
    game, character = player_game()
    game.equip(character.id, 'potion_id', None)
    assert character.slots.potion_id is None
    _, hero, _ = encounter(game, character)
    assert hero.equipment.potion is None
    assert hero.potions_left == 0
    assert character.inventory.consumables['healing_potion'] == 3


@pytest.mark.parametrize(('healed_hp', 'expected_hp'), [(200, 100), (70, 70), (0, 0)])
def test_max_health_buff_expiration_clamps_hp_without_healing_or_resurrecting(healed_hp, expected_hp):
    boost = Superpower(id='health_boost', name='Health boost',
                       effect_bonus=StatBonus(max_health=100), duration=1)
    potion = Potion(id='heal', name='Heal', heal_amount=100)
    hero = BattleParticipant(uuid4(), 'hero', 'A', Controller.HUMAN,
                             Equipment(superpower=boost, potion=potion),
                             100, potions_left=1)
    ally = BattleParticipant(uuid4(), 'ally', 'A', Controller.HUMAN,
                             Equipment(), 100)
    enemy = BattleParticipant(uuid4(), 'enemy', 'B', Controller.HUMAN,
                              Equipment(), 100)
    battle = Battle({p.id: p for p in (hero, ally, enemy)}, 'A', 'B')
    engine = BattleEngine()
    engine.submit_action(battle, hero.id, UseSuperpower(hero.id))
    engine.submit_action(battle, ally.id, Guard())
    engine.submit_action(battle, enemy.id, Guard())
    assert battle.round_number == 2
    assert hero.stats(2).max_health == 200

    if healed_hp == 200:
        engine.submit_action(battle, hero.id, DrinkPotion())
    else:
        hero.current_hp = healed_hp
        if healed_hp:
            engine.submit_action(battle, hero.id, Guard())
    engine.submit_action(battle, ally.id, Guard())
    engine.submit_action(battle, enemy.id, Guard())

    assert battle.round_number == 3
    assert hero.stats(3).max_health == 100
    assert hero.current_hp == expected_hp
    assert hero.is_alive() == (expected_hp > 0)
