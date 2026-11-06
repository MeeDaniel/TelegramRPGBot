from decimal import Decimal
from random import Random
from uuid import uuid4

import pytest

from main import create_content, create_player
from core import (
    Accessory, Armor, Attack, AttackMode, AttackType, Battle,
    BattleEngine, BattleParticipant, BattleStatus, Catalog, Character,
    CombatCalculator, Controller, DrinkPotion, Equipment, GameService,
    Guard, InvalidAction, LootEntry, LootTable, Potion, Rarity,
    StatBonus, Superpower, UseSuperpower, Weapon,
)


def combatant(name, team, *, weapon=None, armor=None, accessory1=None,
              superpower=None, potion=None, potions=0, hp=100):
    return BattleParticipant(
        uuid4(), name, team, Controller.HUMAN,
        Equipment(weapon=weapon, armor=armor, accessory1=accessory1,
                  superpower=superpower, potion=potion),
        hp, potions_left=potions,
    )


def mkbattle(*combatants):
    return Battle({p.id: p for p in combatants}, 'A', 'B')


def sword(bonus):
    return Weapon(id=f'sword_{bonus}', name='Меч',
                  attack_type=AttackType.MELEE,
                  bonus=StatBonus(melee_damage=bonus))


def test_base_stats_and_equipment_bonus():
    p = combatant('hero', 'A', weapon=sword(15),
                  armor=Armor(id='a', name='armor', bonus=StatBonus(max_health=40, defense=10)),
                  accessory1=Accessory(id='r', name='ring', bonus=StatBonus(melee_damage=5)))
    assert p.stats(1).melee_damage == 21
    assert p.stats(1).max_health == 140
    assert p.stats(1).defense == 10
    assert p.stats(1).magic_damage == 1


def test_rounding_half_up_and_zero_damage():
    hero = combatant('hero', 'A', armor=Armor(id='armor', name='armor', bonus=StatBonus(defense=100)))
    assert CombatCalculator.damage(5, hero, False, 1) == 3  # 2.5 -> 3
    assert CombatCalculator.damage(1, hero, False, 1) == 1  # 0.5 -> 1
    heavily_armored = combatant('tank', 'A', armor=Armor(id='plate', name='plate', bonus=StatBonus(defense=1000)))
    assert CombatCalculator.damage(1, heavily_armored, False, 1) == 0


def test_simultaneous_double_ko_results_in_draw():
    a = combatant('a', 'A', weapon=sword(20), hp=10)
    b = combatant('b', 'B', weapon=sword(20), hp=10)
    battle = mkbattle(a, b)
    engine = BattleEngine()
    engine.submit_action(battle, a.id, Attack(b.id))
    events = engine.submit_action(battle, b.id, Attack(a.id))
    assert a.current_hp == b.current_hp == 0
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team is None
    assert any(x.kind == 'finished' for x in events)


def test_simultaneous_healing_and_damage_aggregate_before_clamp():
    hero = combatant('hero', 'A', hp=90)
    healer = combatant('healer', 'A', weapon=Weapon(
        id='support', name='support', attack_type=AttackType.SUPPORT, support_heal=50))
    enemy = combatant('enemy', 'B', weapon=sword(59))  # attack 60
    battle = mkbattle(hero, healer, enemy)
    engine = BattleEngine()
    engine.submit_action(battle, hero.id, Guard())
    engine.submit_action(battle, healer.id, Attack(hero.id))
    engine.submit_action(battle, enemy.id, Attack(hero.id))
    assert hero.current_hp == 80


def test_guard_applies_to_all_incoming_attacks():
    hero = combatant('hero', 'A', hp=100,
                     armor=Armor(id='a', name='a', bonus=StatBonus(defense=20), guard_multiplier=2),
                     accessory1=Accessory(id='b', name='b', bonus=StatBonus(defense=15)))
    e1 = combatant('enemy1', 'B', weapon=sword(29))
    e2 = combatant('enemy2', 'B', weapon=sword(29))
    battle = mkbattle(hero, e1, e2)
    engine = BattleEngine()
    engine.submit_action(battle, hero.id, Guard())
    engine.submit_action(battle, e1.id, Attack(hero.id))
    engine.submit_action(battle, e2.id, Attack(hero.id))
    # Guard rating 70, each hit 30 * 100/170 = 17.647 -> 18.
    assert hero.current_hp == 64


def test_potion_reusable_in_fourth_round():
    potion = Potion(id='heal', name='Potion', heal_amount=50, cooldown=3)
    hero = combatant('hero', 'A', potion=potion, potions=2)
    enemy = combatant('enemy', 'B')
    battle = mkbattle(hero, enemy)
    engine = BattleEngine()

    engine.submit_action(battle, hero.id, DrinkPotion())
    engine.submit_action(battle, enemy.id, Guard())
    assert battle.round_number == 2
    assert hero.potions_left == 1
    assert hero.potion_ready_round == 4
    for round_number in (2, 3):
        with pytest.raises(InvalidAction):
            engine.submit_action(battle, hero.id, DrinkPotion())
        engine.submit_action(battle, hero.id, Guard())
        engine.submit_action(battle, enemy.id, Guard())
        assert battle.round_number == round_number + 1
    engine.submit_action(battle, hero.id, DrinkPotion())
    engine.submit_action(battle, enemy.id, Guard())
    assert hero.potions_left == 0


def test_support_basic_attack_uses_melee_bonuses_from_all_gear():
    staff = Weapon(id='staff', name='staff', attack_type=AttackType.SUPPORT,
                   support_heal=25, bonus=StatBonus(melee_damage=9))
    accessory = Accessory(id='ring', name='ring', bonus=StatBonus(melee_damage=5))
    hero = combatant('support', 'A', weapon=staff, accessory1=accessory)
    enemy = combatant('enemy', 'B')
    battle = mkbattle(hero, enemy)
    engine = BattleEngine()
    with pytest.raises(InvalidAction):
        engine.submit_action(battle, hero.id, Attack(enemy.id, AttackMode.WEAPON))
    engine.submit_action(battle, hero.id, Attack(enemy.id, AttackMode.BASIC))
    engine.submit_action(battle, enemy.id, Guard())
    assert enemy.current_hp == 85  # 1 base + 9 staff + 5 accessory


def test_monster_normal_attack_cannot_target_ally():
    a = combatant('a', 'A', weapon=sword(10))
    ally = combatant('ally', 'A')
    b = combatant('b', 'B')
    engine = BattleEngine()
    with pytest.raises(InvalidAction):
        engine.submit_action(mkbattle(a, ally, b), a.id, Attack(ally.id))


def test_superpower_buffs_only_next_two_turns():
    boost = Superpower(id='boost', name='boost',
                       effect_bonus=StatBonus(melee_damage=10), duration=2, cooldown=3)
    hero = combatant('hero', 'A', superpower=boost)
    enemy = combatant('enemy', 'B')
    battle = mkbattle(hero, enemy)
    engine = BattleEngine()
    engine.submit_action(battle, hero.id, UseSuperpower(hero.id))
    engine.submit_action(battle, enemy.id, Guard())
    assert battle.round_number == 2
    assert hero.stats(2).melee_damage == 11
    assert hero.stats(3).melee_damage == 11
    engine.submit_action(battle, hero.id, Guard())
    engine.submit_action(battle, enemy.id, Guard())
    engine.submit_action(battle, hero.id, Guard())
    engine.submit_action(battle, enemy.id, Guard())
    assert battle.round_number == 4
    assert hero.stats(4).melee_damage == 1


def test_team_member_leaves_enemies_get_numerical_advantage():
    a1, a2 = combatant('a1', 'A'), combatant('a2', 'A')
    b1, b2 = combatant('b1', 'B'), combatant('b2', 'B')
    battle = mkbattle(a1, a2, b1, b2)
    BattleEngine().leave(battle, a2.id)
    assert battle.status == BattleStatus.WAITING
    assert len(battle.living()) == 3
    assert [p.name for p in battle.living() if p.team_id == 'A'] == ['a1']


def test_solo_leave_results_in_opponent_victory():
    hero, enemy = combatant('hero', 'A'), combatant('enemy', 'B')
    battle = mkbattle(hero, enemy)
    BattleEngine().leave(battle, hero.id)
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team == 'B'
    assert battle.finish_reason == 'surrender'


def test_cancel_solo_pve_requires_only_human_vote():
    hero = combatant('hero', 'A')
    mob = combatant('enemy', 'B')
    mob.controller = Controller.AI
    battle = mkbattle(hero, mob)
    BattleEngine().request_cancel(battle, hero.id)
    assert battle.status == BattleStatus.CANCELLED


def test_all_rarities_available_for_every_monster():
    catalog = create_content()
    for monster in catalog.monsters.values():
        assert set(monster.loadouts) == set(Rarity)
        for rarity in Rarity:
            assert catalog.equip(monster.loadouts[rarity]).weapon is not None


def test_rewards_independent_of_monster_equipment_and_not_duplicated():
    catalog = create_content()
    # Guaranteed drop, even if monster never wore this item.
    for monster in catalog.monsters.values():
        catalog.loot_tables[monster.loot_table_id] = LootTable(
            id=monster.loot_table_id,
            entries=(LootEntry('forest_amulet', 1.0), LootEntry('healing_potion', 1.0)),
        )
    game = GameService(catalog, rng=Random(3))
    character = create_player(game, False)
    battle = game.create_pve(character.id, 'forgotten_forest')
    hero = next(p for p in battle.participants.values() if p.character_id is not None)
    enemy = next(p for p in battle.participants.values() if p.character_id is None)
    enemy.current_hp = 1
    events = game.submit_action(battle.id, hero.id, Attack(enemy.id))
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team == battle.player_team
    assert sum(x.definition_id == 'forest_amulet' for x in character.inventory.items.values()) == 1
    assert character.inventory.consumables['healing_potion'] == 4
    game._process_events(battle, events)
    assert sum(x.definition_id == 'forest_amulet' for x in character.inventory.items.values()) == 1
    assert character.inventory.consumables['healing_potion'] == 4


def test_equip_locked_during_battle():
    game = GameService(create_content(), rng=Random(1))
    hero = create_player(game, False)
    game.create_pve(hero.id, 'forgotten_forest')
    with pytest.raises(ValueError, match='active battle'):
        game.equip(hero.id, 'weapon', None)


def test_potion_usage_is_persisted_in_inventory():
    game = GameService(create_content(), rng=Random(2))
    hero = create_player(game, False)
    battle = game.create_pve(hero.id, 'forgotten_forest')
    participant = next(p for p in battle.participants.values() if p.character_id == hero.id)
    game.submit_action(battle.id, participant.id, DrinkPotion())
    assert hero.inventory.consumables['healing_potion'] == 2
    assert participant.potions_left == 2


def test_new_encounter_starts_at_full_health():
    game = GameService(create_content(), rng=Random(2))
    hero = create_player(game, False)
    first = game.create_pve(hero.id, 'forgotten_forest')
    p = next(x for x in first.participants.values() if x.character_id == hero.id)
    p.current_hp = 4
    game.leave(first.id, p.id)
    second = game.create_pve(hero.id, 'forgotten_forest')
    p2 = next(x for x in second.participants.values() if x.character_id == hero.id)
    assert p2.current_hp == p2.stats(1).max_health


def test_cli_smoke_run_and_cancel():
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / 'main.py'), '--seed', '42'],
        input='1\n' * 30, text=True, encoding='utf-8', capture_output=True, cwd=root, timeout=15,
    )
    assert result.returncode == 0
    assert 'ПОБЕДА!' in result.stdout
    assert 'Игра завершена.' in result.stdout
    cancel = subprocess.run(
        [sys.executable, str(root / 'main.py'), '--seed', '42'],
        input='6\n', text=True, encoding='utf-8', capture_output=True, cwd=root, timeout=15,
    )
    assert cancel.returncode == 0
    assert 'Бой отменён.' in cancel.stdout
