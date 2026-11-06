"""Run directly: python main.py [--seed 42] [--support]"""

from __future__ import annotations

import argparse
import sys
from random import Random

from pathlib import Path

from rpg_content import ContentWorld, load

from core import (
    Attack, AttackMode, AttackType, BattleStatus, Catalog, Character,
    DrinkPotion, GameService, Guard, InvalidAction, UseSuperpower,
)
from core.content_adapter import to_catalog


def create_content() -> Catalog:
    """Compatibility entry point returning a fresh projection of the demo world."""
    return to_catalog(load(Path(__file__).resolve().parent / 'content' / 'demo.json'))


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
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Консольное демо независимого RPG-движка')
    parser.add_argument('--seed', type=int, default=None,
                        help='Seed for reproducible encounters, AI and loot')
    parser.add_argument('--support', action='store_true',
                        help='Начать с оружием саппорта')
    args = parser.parse_args()
    world = load(Path(__file__).resolve().parent / 'content' / 'demo.json')
    game = GameService(to_catalog(world), rng=Random(args.seed))
    run_cli(world, game, args.support)


def run_cli(world: ContentWorld, game: GameService, support: bool) -> None:
    """Present the demo using the shared snapshot and application service."""
    player = create_player(game, support)
    location = world.locations['forgotten_forest']
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
