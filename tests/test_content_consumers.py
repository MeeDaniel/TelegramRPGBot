"""Two small transports share content, but run commands on independent games."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
import json
from random import Random
from uuid import UUID

import pytest

from content_helpers import six_section_payload
from core import Attack, BattleStatus, Character, DrinkPotion, GameService, Guard, UseSuperpower
from rpg_content import ContentRef, UnknownContentReference, parse, validate


class ConsoleConsumer:
    def __init__(self, world, game):
        self.world, self.game = world, game

    def locations(self):
        return tuple(self.world.locations)

    def npcs(self):
        return tuple(self.world.npcs.values())

    def npcs_at(self, location):
        return self.world.npcs_at(location)

    def command(self, battle, actor, command, target=None):
        if command == 'guard':
            action = Guard()
        elif command == 'potion':
            action = DrinkPotion()
        elif command == 'power':
            action = UseSuperpower(actor)
        elif command == 'attack':
            action = Attack(target)
        else:
            raise ValueError(command)
        return self.game.submit_action(battle, actor, action)


class TelegramConsumer:
    """Test-only callback adapter; no SDK or transport IDs enter content."""

    def __init__(self, world, game):
        self.world, self.game = world, game

    def locations(self):
        return tuple(location.id for location in self.world.locations.values())

    def npcs(self):
        return tuple(self.world.npcs[npc_id] for npc_id in self.world.npcs)

    def npcs_at(self, location):
        return self.world.npcs_at(location)

    def callback(self, data):
        factories = {
            'guard': lambda: Guard(),
            'potion': lambda: DrinkPotion(),
            'power': lambda: UseSuperpower(data['actor']),
            'attack': lambda: Attack(data['target']),
        }
        return self.game.submit_action(data['battle'], data['actor'], factories[data['action']]())


@pytest.fixture
def world():
    payload = six_section_payload()
    payload['items'][0]['bonus'] = {'melee_damage': 150}
    payload['monsters'][0]['loadouts'] = {rarity: {} for rarity in payload['monsters'][0]['loadouts']}
    payload['loot_tables'][0]['entries'] = [
        {'item': 'items:potion', 'chance': 1, 'min_quantity': 2, 'max_quantity': 2},
        {'item': 'items:ring', 'chance': 1},
    ]
    return validate(parse(json.dumps(payload)))


def test_both_transports_read_every_location_and_unplaced_npc_from_shared_world(world):
    from core.content_adapter import to_catalog

    game = GameService(to_catalog(world), rng=Random(42))
    console, telegram = ConsoleConsumer(world, game), TelegramConsumer(world, game)
    assert console.world is telegram.world is world
    assert console.game is telegram.game is game
    assert console.locations() == telegram.locations() == ('forest', 'bridge', 'empty')
    assert [npc.id for npc in console.npcs()] == [npc.id for npc in telegram.npcs()] == ['mira', 'wanderer', 'guard']
    assert [npc.id for npc in console.npcs_at('bridge')] == ['mira', 'guard']
    assert console.npcs_at('bridge') == telegram.npcs_at('bridge')
    assert console.npcs_at('empty') == telegram.npcs_at('empty') == ()
    assert world.npcs['wanderer'].location is None
    assert world.resolve(ContentRef('npcs', 'mira')) is world.npcs['mira']
    for consumer in (console, telegram):
        with pytest.raises(UnknownContentReference) as error:
            consumer.npcs_at('absent')
        assert (error.value.section, error.value.id) == ('locations', 'absent')
        with pytest.raises(KeyError):
            consumer.world.npcs['absent']
        with pytest.raises(TypeError):
            consumer.world.locations['new'] = world.locations['bridge']
    assert not game.store.characters and not game.store.battles


def _new_game(world):
    from core.content_adapter import to_catalog

    game = GameService(to_catalog(world), rng=Random(42))
    character = Character(name='Герой')
    game.register_character(character)
    for slot, definition in (('weapon', 'sword'), ('armor', 'armor'), ('superpower', 'power')):
        instance = character.inventory.add_item(definition)
        game.equip(character.id, slot, instance)
    character.inventory.add_consumable('potion', 3)
    game.equip(character.id, 'potion_id', 'potion')
    return game, character


def _normalize(value, ids=None):
    """Compare generated identities by stable encounter order, preserving fields."""
    if ids is None:
        ids = {}
    if isinstance(value, UUID):
        return ids.setdefault(value, f'uuid_{len(ids)}')
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {'type': type(value).__name__, **{
            field.name: _normalize(getattr(value, field.name), ids)
            for field in fields(value) if field.name != '_inventory'
        }}
    if isinstance(value, Mapping):
        return {_normalize(key, ids): _normalize(item, ids) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item, ids) for item in value]
    if isinstance(value, set):
        return sorted(_normalize(item, ids) for item in value)
    return value


def _sequence(consumer, character):
    game = consumer.game
    battle = game.create_pve(character.id, 'forest')
    hero = next(p for p in battle.participants.values() if p.character_id is not None)
    monster = next(p for p in battle.participants.values() if p.character_id is None)
    # One identity map keeps actors and targets consistent across every snapshot.
    ids = {}
    trace = [{'battle': _normalize(battle, ids)}]
    for command in ('guard', 'potion', 'power', 'attack'):
        if isinstance(consumer, ConsoleConsumer):
            events = consumer.command(battle.id, hero.id, command, monster.id)
        else:
            events = consumer.callback({'battle': battle.id, 'actor': hero.id,
                                        'action': command, 'target': monster.id})
        trace.append({'command': command, 'events': _normalize(events, ids),
                      'battle': _normalize(battle, ids)})
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team == 'heroes'
    assert battle.drops == [('potion', 2), ('ring', 1)]
    assert character.inventory.consumables['potion'] == 4  # three - one + two
    assert sum(item.definition_id == 'ring' for item in character.inventory.items.values()) == 1
    trace.append({'character': _normalize(character, ids)})
    return trace


@pytest.mark.parametrize('participant_ids', [(1, 2, 3, 4), (2, 1, 4, 3)],
                         ids=['hero-first', 'monster-first'])
def test_transport_sequences_match_without_sharing_mutable_player_battle_or_rng_state(
        world, monkeypatch, participant_ids):
    # The engine orders events by actor UUID. Independent random IDs can reverse
    # that order even with identical RNG seeds; exercise both orders deliberately.
    generated_ids = iter(UUID(int=value) for value in participant_ids)
    monkeypatch.setattr('core.service.uuid4', generated_ids.__next__)
    console_game, console_character = _new_game(world)
    telegram_game, telegram_character = _new_game(world)
    console = ConsoleConsumer(world, console_game)
    telegram = TelegramConsumer(world, telegram_game)
    assert console_game.store is not telegram_game.store
    assert console_character.inventory is not telegram_character.inventory
    before_character = _normalize(telegram_character)
    before_rng = telegram_game.rng.getstate()
    console_trace = _sequence(console, console_character)
    assert not telegram_game.store.battles
    assert _normalize(telegram_character) == before_character
    assert telegram_game.rng.getstate() == before_rng
    assert _sequence(telegram, telegram_character) == console_trace
    assert world.monsters['wolf'].loadouts['common'].weapon is None
    assert world.items['sword'].bonus['melee_damage'] == 150
