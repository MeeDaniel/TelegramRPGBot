"""In-memory application layer: orchestration, equipment, rewards and persistence seam."""

from __future__ import annotations

from random import Random
from uuid import UUID, uuid4

from .engine import BattleEngine, InvalidAction
from .models import (
    BASE_STATS,
    Accessory,
    Armor,
    Battle,
    BattleAction,
    BattleParticipant,
    BattleStatus,
    Character,
    CombatEvent,
    Controller,
    Equipment,
    Potion,
    Superpower,
    Weapon,
)
from .world import Catalog, EncounterGenerator, LootGenerator, MonsterAI


class InMemoryStore:
    def __init__(self):
        self.characters: dict[UUID, Character] = {}
        self.battles: dict[UUID, Battle] = {}


class GameService:
    """No UI details; replace InMemoryStore with repositories/transactions later."""

    def __init__(self, catalog: Catalog, store: InMemoryStore | None = None,
                 rng: Random | None = None):
        self.catalog = catalog
        self.store = store if store is not None else InMemoryStore()
        self.rng = rng if rng is not None else Random()
        self.engine = BattleEngine()
        self.encounters = EncounterGenerator(catalog, self.rng)
        self.loot = LootGenerator(catalog, self.rng)
        self.ai = MonsterAI(self.rng)

    def register_character(self, character: Character) -> None:
        if character.id in self.store.characters:
            raise ValueError('Duplicate character ID')
        self.store.characters[character.id] = character

    def equip(self, character_id: UUID, slot: str, item_id: UUID | str | None) -> None:
        character = self.store.characters[character_id]
        if any(b.status == BattleStatus.WAITING and any(
            p.character_id == character_id and p.is_alive() for p in b.participants.values()
        ) for b in self.store.battles.values()):
            raise ValueError('Cannot change equipment during an active battle')
        slots = character.slots
        valid = {'weapon': Weapon, 'armor': Armor, 'accessory1': Accessory,
                 'accessory2': Accessory, 'superpower': Superpower, 'potion_id': Potion}
        if slot not in valid:
            raise ValueError('Unknown equipment slot')
        if slot == 'potion_id':
            if item_id is not None and \
                not isinstance(item_id, str) or not isinstance(self.catalog.items[item_id], Potion): # type: ignore
                raise ValueError('Invalid potion')
            slots.potion_id = item_id
            return
        if item_id is not None:
            if not isinstance(item_id, UUID) or item_id not in character.inventory.items:
                raise ValueError('Item is not owned by character')
            item = self.catalog.items[character.inventory.items[item_id].definition_id]
            if not isinstance(item, valid[slot]):
                raise ValueError('Item is of the wrong slot type')
            other = [getattr(slots, name) for name in valid if name != slot and name != 'potion_id']
            if item_id in other:
                raise ValueError('Item cannot be equipped twice')
        setattr(slots, slot, item_id)

    def character_equipment(self, character: Character) -> Equipment:
        slots = character.slots
        def definition(item_id):
            return self.catalog.items[character.inventory.items[item_id].definition_id] if item_id else None
        return Equipment(
            weapon=definition(slots.weapon), armor=definition(slots.armor),
            accessory1=definition(slots.accessory1),
            accessory2=definition(slots.accessory2),
            superpower=definition(slots.superpower),
            potion=self.catalog.items[slots.potion_id] if slots.potion_id else None,
        )

    def create_pve(self, character_id: UUID, location_id: str) -> Battle:
        if any(b.status == BattleStatus.WAITING and any(
            p.character_id == character_id and p.active for p in b.participants.values()
        ) for b in self.store.battles.values()):
            raise ValueError('Character is already in an active battle')
        character = self.store.characters[character_id]
        equipment = self.character_equipment(character)
        spawn = self.encounters.generate(location_id)
        hero_id, monster_id = uuid4(), uuid4()
        hero_potions = character.inventory.consumables.get(equipment.potion.id, 0) if equipment.potion else 0
        hero = BattleParticipant(
            id=hero_id, name=character.name, team_id='heroes', controller=Controller.HUMAN,
            equipment=equipment, current_hp=self._max_hp(equipment),
            potions_left=hero_potions, character_id=character_id,
        )
        monster = BattleParticipant(
            id=monster_id, name=f'{spawn.rarity.label} {spawn.definition.name}',
            team_id='monsters', controller=Controller.AI,
            equipment=spawn.equipment, current_hp=self._max_hp(spawn.equipment),
            potions_left=spawn.potion_count,
        )
        battle = Battle(
            participants={hero_id: hero, monster_id: monster},
            player_team='heroes', enemy_team='monsters',
            location_id=location_id, monster_id=spawn.definition.id,
            monster_rarity=spawn.rarity,
        )
        self.store.battles[battle.id] = battle
        self._fill_ai_actions(battle)
        return battle

    @staticmethod
    def _max_hp(equipment: Equipment) -> int:
        return BASE_STATS.with_bonuses([item.bonus for item in equipment.items()]).max_health

    def submit_action(self, battle_id: UUID, actor_id: UUID, action: BattleAction) -> list[CombatEvent]:
        battle = self.store.battles[battle_id]
        actor = battle.participants[actor_id]
        if actor.controller != Controller.HUMAN:
            raise InvalidAction('Only a human participant can submit a manual action')
        self._fill_ai_actions(battle)
        events = self.engine.submit_action(battle, actor_id, action)
        self._process_events(battle, events)
        if battle.status == BattleStatus.WAITING and not battle.actions:
            self._fill_ai_actions(battle)
        return events

    def leave(self, battle_id: UUID, actor_id: UUID) -> list[CombatEvent]:
        battle = self.store.battles[battle_id]
        if battle.participants[actor_id].controller != Controller.HUMAN:
            raise InvalidAction('Only a human can request leave')
        events = self.engine.leave(battle, actor_id)
        self._process_events(battle, events)
        return events

    def cancel(self, battle_id: UUID, actor_id: UUID) -> list[CombatEvent]:
        battle = self.store.battles[battle_id]
        return self.engine.request_cancel(battle, actor_id)

    def _fill_ai_actions(self, battle: Battle) -> None:
        if battle.status != BattleStatus.WAITING:
            return
        for actor in list(battle.living()):
            if actor.controller == Controller.AI and actor.id not in battle.actions:
                action = self.ai.choose(battle, actor)
                # AI is intentionally unaware of opponents' pending actions.
                self.engine.submit_action(battle, actor.id, action)

    def _process_events(self, battle: Battle, events: list[CombatEvent]) -> None:
        for event in events:
            if event.kind == 'potion_used':
                actor = battle.participants[event.actor_id]
                if actor.character_id is not None:
                    potion = actor.equipment.potion
                    assert potion is not None
                    self.store.characters[actor.character_id].inventory.consume(potion.id)
        if battle.status == BattleStatus.FINISHED and not battle.rewards_granted:
            # Only PvE victories against monsters grant random rewards.
            if battle.winner_team == battle.player_team and battle.monster_id is not None:
                drops = self.loot.roll(battle.monster_id, battle.monster_rarity)
                battle.drops.extend(drops)
                for participant in battle.participants.values():
                    if participant.character_id is None or participant.team_id != battle.player_team:
                        continue
                    inventory = self.store.characters[participant.character_id].inventory
                    for definition_id, amount in drops:
                        if isinstance(self.catalog.items[definition_id], Potion):
                            inventory.add_consumable(definition_id, amount)
                        else:
                            for _ in range(amount):
                                inventory.add_item(definition_id)
            battle.rewards_granted = True
