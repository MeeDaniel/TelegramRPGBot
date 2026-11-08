"""Run directly: python main.py [--seed 42] [--support]"""

from __future__ import annotations

import argparse
import sys
from random import Random

from pathlib import Path

from rpg_content import ContentWorld, load

from core import (
    Catalog, Character, GameService,
)
from core.content_adapter import to_catalog


def create_content() -> Catalog:
    """Compatibility entry point returning a fresh projection of the demo world."""
    return to_catalog(load(Path(__file__).resolve().parent / 'content' / 'demo.json'))


def create_player(game: GameService, support: bool, name: str = 'Герой') -> Character:
    character = Character(name=name)
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


def main() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
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
    """Supply demo presets to the independently installable interface."""
    from rpg_cli import CharacterPreset, run_cli as run_interface

    presets = (
        CharacterPreset('sword', 'Меч', lambda name: create_player(game, False, name)),
        CharacterPreset('staff', 'Посох поддержки', lambda name: create_player(game, True, name)),
    )
    run_interface(world, game, presets, 'staff' if support else 'sword')


if __name__ == '__main__':
    main()
