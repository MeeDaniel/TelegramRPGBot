"""Run directly: python main.py [--seed 42] [--support]"""

from __future__ import annotations

import argparse
from random import Random

from core import (
    Accessory, Armor, Attack, AttackMode, AttackType, BattleStatus,
    Catalog, Character, DrinkPotion, EquipmentSpec, GameService,
    Guard, InvalidAction, LocationDefinition, LootEntry, LootTable,
    MonsterDefinition, Potion, Rarity, SpawnEntry, StatBonus,
    Superpower, UseSuperpower, Weapon,
)


def create_content() -> Catalog:
    """Demo content created in Python, with no external database or framework."""
    catalog = Catalog()

    def add(item):
        catalog.items[item.id] = item

    # The playable character's items.
    add(Weapon(id='steel_sword', name='Стальной меч',
               attack_type=AttackType.MELEE, bonus=StatBonus(melee_damage=24)))
    add(Weapon(id='healing_staff', name='Посох целителя',
               attack_type=AttackType.SUPPORT, support_heal=30,
               bonus=StatBonus(melee_damage=9, magic_damage=5)))
    add(Armor(id='travel_armor', name='Броня странника',
              bonus=StatBonus(defense=18, max_health=35), guard_multiplier=2.0))
    add(Accessory(id='power_ring', name='Кольцо силы',
                  bonus=StatBonus(melee_damage=6, defense=5)))
    add(Accessory(id='life_charm', name='Амулет здоровья',
                  bonus=StatBonus(max_health=25, melee_damage=3)))
    add(Superpower(id='battle_rage', name='Боевой азарт',
                   effect_bonus=StatBonus(melee_damage=12, magic_damage=12,
                                          ranged_damage=12), duration=2, cooldown=3))
    add(Potion(id='healing_potion', name='Зелье лечения', heal_amount=50, cooldown=3))

    add(Weapon(id='forest_blade', name='Лесной клинок',
               attack_type=AttackType.MELEE, rarity=Rarity.RARE,
               bonus=StatBonus(melee_damage=29)))
    add(Accessory(id='forest_amulet', name='Амулет чащи',
                  rarity=Rarity.RARE,
                  bonus=StatBonus(max_health=20, defense=8)))

    # Every monster type has equipment for EVERY rarity, with no base-stat overrides.
    templates = [
        ('slime', 'Слизень', 10, 0, 0),
        ('wolf', 'Лесной волк', 14, 4, 15),
        ('skeleton', 'Скелет', 17, 8, 25),
        ('ancient_ent', 'Древний энт', 23, 14, 100),
    ]
    for monster_id, name, attack_base, armor_base, hp_base in templates:
        loadouts = {}
        for tier, rarity in enumerate(Rarity):
            weapon_id = f'{monster_id}_weapon_{tier}'
            armor_id = f'{monster_id}_armor_{tier}'
            add(Weapon(id=weapon_id, name=f'Оружие: {name} ({rarity.label})',
                       rarity=rarity, attack_type=AttackType.MELEE,
                       bonus=StatBonus(melee_damage=attack_base + tier * 8)))
            add(Armor(id=armor_id, name=f'Защита: {name} ({rarity.label})',
                      rarity=rarity,
                      bonus=StatBonus(defense=armor_base + tier * 7,
                                      max_health=hp_base + tier * 38),
                      guard_multiplier=1.7 + tier * 0.1))
            loadouts[rarity] = EquipmentSpec(
                weapon=weapon_id, armor=armor_id,
                superpower='battle_rage' if tier >= 3 else None,
                potion='healing_potion' if tier >= 4 else None,
                potion_count=1 if tier >= 4 else 0,
            )
        catalog.monsters[monster_id] = MonsterDefinition(
            id=monster_id, name=name, loadouts=loadouts,
            loot_table_id=f'{monster_id}_loot',
            is_boss=(monster_id == 'ancient_ent'),
        )

    catalog.loot_tables.update({
        'slime_loot': LootTable('slime_loot', (
            LootEntry('healing_potion', chance=.45, max_quantity=2),
            LootEntry('forest_amulet', chance=.08),
        )),
        'wolf_loot': LootTable('wolf_loot', (
            LootEntry('healing_potion', chance=.55),
            LootEntry('forest_blade', chance=.10),
        )),
        'skeleton_loot': LootTable('skeleton_loot', (
            LootEntry('healing_potion', chance=.65, max_quantity=2),
            LootEntry('forest_blade', chance=.18),
        )),
        'ancient_ent_loot': LootTable('ancient_ent_loot', (
            LootEntry('healing_potion', chance=1.0, min_quantity=2, max_quantity=3),
            LootEntry('forest_blade', chance=.75),
            LootEntry('forest_amulet', chance=.75),
        )),
    })
    catalog.locations['forgotten_forest'] = LocationDefinition(
        id='forgotten_forest', name='Забытый лес',
        spawns=(SpawnEntry('slime', 48), SpawnEntry('wolf', 32),
                SpawnEntry('skeleton', 17), SpawnEntry('ancient_ent', 3)),
        rarity_weights={
            Rarity.COMMON: 57, Rarity.UNCOMMON: 25, Rarity.RARE: 11,
            Rarity.EPIC: 5, Rarity.LEGENDARY: 1.7, Rarity.MYTHIC: .3,
        },
    )
    return catalog


def create_player(game: GameService, support: bool) -> Character:
    character = Character(name='Герой')
    game.register_character(character)
    for slot, definition_id in (
        ('weapon', 'healing_staff' if support else 'steel_sword'),
        ('armor', 'travel_armor'), ('accessory1', 'power_ring'),
        ('accessory2', 'life_charm'), ('superpower', 'battle_rage'),
    ):
        item_id = character.inventory.add_item(definition_id)
        game.equip(character.id, slot, item_id)
    character.inventory.add_consumable('healing_potion', 3)
    game.equip(character.id, 'potion_id', 'healing_potion')
    return character


def status_line(battle) -> None:
    print(f'\n{"=" * 58}\nХОД {battle.round_number}\n{"=" * 58}')
    for participant in battle.participants.values():
        stats = participant.stats(battle.round_number)
        state = 'ВЫБЫЛ' if not participant.is_alive() else f'{participant.current_hp}/{stats.max_health} HP'
        print(f'  {participant.name}: {state} | защита {stats.defense}')
        if participant.is_alive() and participant.controller.value == 'human':
            power = participant.equipment.superpower
            ptn = participant.equipment.potion
            print(f'    Зелья: {participant.potions_left}' + (
                f' (доступно с хода {participant.potion_ready_round})' if ptn else ''))
            print('    Суперсила: ' + (
                f'{power.name} (доступна с хода {participant.superpower_ready_round})'
                if power else 'нет'))
            if participant.effects:
                print('    Эффекты: ' + ', '.join(
                    f'{e.name} (до хода {e.ends_round})' for e in participant.effects
                ))


def choose_target(battle, actor, friendly: bool):
    options = [p for p in battle.living()
               if (p.team_id == actor.team_id) == friendly]
    if len(options) == 1:
        return options[0].id
    print('Цели:')
    for index, option in enumerate(options, 1):
        print(f'  {index}. {option.name} ({option.current_hp} HP)')
    while True:
        try:
            return options[int(input('Номер цели: ').strip()) - 1].id
        except (ValueError, IndexError):
            print('Неверная цель.')


def play(game: GameService, battle, character: Character) -> None:
    player = next(p for p in battle.participants.values() if p.character_id == character.id)
    print('\nНачинается бой! Монстр уже выбрал скрытое действие.')
    while battle.status == BattleStatus.WAITING:
        status_line(battle)
        print('\n[1] Атаковать  [2] Защититься  [3] Суперсила')
        print('[4] Зелье      [5] Покинуть бой  [6] Отмена боя')
        option = input('Ваш выбор: ').strip().lower()
        try:
            if option == '1':
                support_weapon = bool(player.equipment.weapon and
                                      player.equipment.weapon.attack_type == AttackType.SUPPORT)
                if support_weapon:
                    print('  [1] Базовая ближняя атака по врагу')
                    print('  [2] Лечение союзника посохом')
                    choice = input('Тип атаки: ').strip()
                    if choice not in ('1', '2'):
                        print('Неверный тип атаки.')
                        continue
                    friendly = choice == '2'
                    action = Attack(choose_target(battle, player, friendly),
                                    AttackMode.WEAPON if friendly else AttackMode.BASIC)
                else:
                    action = Attack(choose_target(battle, player, False))
                events = game.submit_action(battle.id, player.id, action)
            elif option == '2':
                events = game.submit_action(battle.id, player.id, Guard())
            elif option == '3':
                events = game.submit_action(
                    battle.id, player.id,
                    UseSuperpower(choose_target(battle, player, True)),
                )
            elif option == '4':
                events = game.submit_action(battle.id, player.id, DrinkPotion())
            elif option == '5':
                events = game.leave(battle.id, player.id)
            elif option == '6':
                events = game.cancel(battle.id, player.id)
            else:
                print('Выберите число от 1 до 6.')
                continue
        except InvalidAction as error:
            print(f'Нельзя выполнить действие: {error}')
            continue
        for event in events:
            print('  - ' + event.text)

    print(f'\n{"=" * 58}\nРЕЗУЛЬТАТ БОЯ\n{"=" * 58}')
    if battle.status == BattleStatus.CANCELLED:
        print('Бой отменён. Наград нет.')
    elif battle.winner_team == battle.player_team:
        print('ПОБЕДА!')
    elif battle.winner_team is None:
        print('НИЧЬЯ!')
    else:
        print('ПОРАЖЕНИЕ!')
    if battle.drops:
        print('\nДобыча:')
        for item_id, amount in battle.drops:
            print(f'  {game.catalog.items[item_id].name} ×{amount}')
    else:
        print('Добыча: нет')
    print(f'Остаток зелий: {character.inventory.consumables.get("healing_potion", 0)}')
    print('Игра завершена.')


def main() -> None:
    parser = argparse.ArgumentParser(description='Консольное демо независимого RPG-движка')
    parser.add_argument('--seed', type=int, default=None,
                        help='Seed for reproducible encounters, AI and loot')
    parser.add_argument('--support', action='store_true',
                        help='Начать с оружием саппорта')
    args = parser.parse_args()
    catalog = create_content()
    game = GameService(catalog, rng=Random(args.seed))
    player = create_player(game, args.support)
    location = catalog.locations['forgotten_forest']
    print('=== Консольная RPG ===')
    print(f'Игрок: {player.name} | Локация: {location.name}')
    print('Оружие:', game.character_equipment(player).weapon.name)
    print('Поиск случайного монстра...')
    battle = game.create_pve(player.id, location.id)
    mob = next(p for p in battle.participants.values() if p.character_id is None)
    print(f'Встречен: {mob.name}!')
    try:
        play(game, battle, player)
    except (KeyboardInterrupt, EOFError):
        if battle.status == BattleStatus.WAITING:
            events = game.leave(battle.id, next(p.id for p in battle.participants.values()
                                                if p.character_id == player.id))
            print('\nБой прерван. Наград нет.')
        print('Выход.')


if __name__ == '__main__':
    main()
