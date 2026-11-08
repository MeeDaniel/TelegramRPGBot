"""Real core fixture used by CLI acceptance tests."""

from dataclasses import replace
from pathlib import Path
from random import Random

from core import GameService
from core.world import EquipmentSpec
from main import create_content, create_player
from rpg_content import load
from rpg_cli import CharacterPreset, create_session





class Adventure:
    def __init__(self, *, default='sword', default_name='Герой', empty_locations=False):
        self.world = load(Path(__file__).resolve().parents[1] / 'content' / 'demo.json')
        catalog = create_content()
        # A harmless unarmed enemy makes action/cooldown scenarios reproducible.
        for key, monster in tuple(catalog.monsters.items()):
            catalog.monsters[key] = replace(
                monster, loadouts={rarity: EquipmentSpec() for rarity in monster.loadouts})
        if empty_locations:
            catalog.locations.clear()
        self.game = GameService(catalog, rng=Random(42))
        self.created = []

        def factory(support):
            def create(name):
                character = create_player(self.game, support)
                character.name = name
                self.created.append(character)
                return character
            return create

        self.presets = (
            CharacterPreset('sword', 'Клинок', factory(False)),
            CharacterPreset('staff', 'Посох', factory(True)),
        )
        self.session = create_session(self.world, self.game, self.presets, default, default_name)

    @property
    def character(self):
        return self.created[0]

    def home(self):
        return self.session.select('home')

    def battle(self):
        self.session.select('locations')
        location_id = next(iter(self.game.catalog.locations))
        self.session.select(f'location:{location_id}')
        battle = list(self.game.store.battles.values())[-1]
        hero = next(p for p in battle.participants.values() if p.character_id is not None)
        enemy = next(p for p in battle.participants.values() if p.character_id is None)
        return battle, hero, enemy
