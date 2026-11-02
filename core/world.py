"""Content catalog, weighted encounters, monster AI and independent loot tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from .models import (
    Accessory, Armor, Attack, AttackMode, AttackType, Battle,
    BattleParticipant, DrinkPotion, Equipment, Guard, ItemDefinition,
    Potion, Rarity, Superpower, UseSuperpower, Weapon,
)


@dataclass(frozen=True, slots=True)
class EquipmentSpec:
    weapon: str | None = None
    armor: str | None = None
    accessory1: str | None = None
    accessory2: str | None = None
    superpower: str | None = None
    potion: str | None = None
    potion_count: int = 0


@dataclass(frozen=True, slots=True)
class MonsterDefinition:
    id: str
    name: str
    loadouts: dict[Rarity, EquipmentSpec]
    loot_table_id: str
    is_boss: bool = False


@dataclass(frozen=True, slots=True)
class SpawnEntry:
    monster_id: str
    weight: float


@dataclass(frozen=True, slots=True)
class LocationDefinition:
    id: str
    name: str
    spawns: tuple[SpawnEntry, ...]
    rarity_weights: dict[Rarity, float]


@dataclass(frozen=True, slots=True)
class LootEntry:
    item_id: str
    chance: float  # independent roll in [0, 1]
    min_quantity: int = 1
    max_quantity: int = 1


@dataclass(frozen=True, slots=True)
class LootTable:
    id: str
    entries: tuple[LootEntry, ...]


@dataclass(frozen=True, slots=True)
class MonsterSpawn:
    definition: MonsterDefinition
    rarity: Rarity
    equipment: Equipment
    potion_count: int


@dataclass(slots=True)
class Catalog:
    items: dict[str, ItemDefinition] = field(default_factory=dict)
    monsters: dict[str, MonsterDefinition] = field(default_factory=dict)
    locations: dict[str, LocationDefinition] = field(default_factory=dict)
    loot_tables: dict[str, LootTable] = field(default_factory=dict)

    def equip(self, spec: EquipmentSpec) -> Equipment:
        def get(item_id: str | None, expected: type):
            if item_id is None:
                return None
            item = self.items[item_id]
            if not isinstance(item, expected):
                raise ValueError(f'{item_id} is not {expected.__name__}')
            return item
        return Equipment(
            weapon=get(spec.weapon, Weapon), armor=get(spec.armor, Armor),
            accessory1=get(spec.accessory1, Accessory),
            accessory2=get(spec.accessory2, Accessory),
            superpower=get(spec.superpower, Superpower),
            potion=get(spec.potion, Potion),
        )


class EncounterGenerator:
    def __init__(self, catalog: Catalog, rng: Random):
        self.catalog = catalog
        self.rng = rng

    def generate(self, location_id: str) -> MonsterSpawn:
        location = self.catalog.locations[location_id]
        if not location.spawns or not location.rarity_weights:
            raise ValueError('Location has an empty spawn table')
        monster_id = self.rng.choices(
            [x.monster_id for x in location.spawns],
            weights=[x.weight for x in location.spawns], k=1,
        )[0]
        rarity = self.rng.choices(
            list(location.rarity_weights),
            weights=list(location.rarity_weights.values()), k=1,
        )[0]
        definition = self.catalog.monsters[monster_id]
        spec = definition.loadouts[rarity]
        return MonsterSpawn(definition, rarity, self.catalog.equip(spec), spec.potion_count)


class LootGenerator:
    def __init__(self, catalog: Catalog, rng: Random):
        self.catalog = catalog
        self.rng = rng

    def roll(self, monster_id: str, rarity: Rarity) -> list[tuple[str, int]]:
        monster = self.catalog.monsters[monster_id]
        table = self.catalog.loot_tables[monster.loot_table_id]
        # Higher-rarity monsters make configured drops more likely, but never exceed 100%.
        multiplier = 1 + list(Rarity).index(rarity) * 0.15
        drops = []
        for entry in table.entries:
            if self.rng.random() < min(1.0, entry.chance * multiplier):
                drops.append((entry.item_id, self.rng.randint(entry.min_quantity, entry.max_quantity)))
        return drops


class MonsterAI:
    """Chooses using public participant state, never pending opponent actions."""

    def __init__(self, rng: Random):
        self.rng = rng

    def choose(self, battle: Battle, actor: BattleParticipant):
        friends = [p for p in battle.living() if p.team_id == actor.team_id]
        foes = [p for p in battle.living() if p.team_id != actor.team_id]
        if not foes:
            raise ValueError('No enemy targets')
        maximum = actor.stats(battle.round_number).max_health
        if (actor.equipment.potion is not None and actor.potions_left > 0
                and battle.round_number >= actor.potion_ready_round
                and actor.current_hp <= maximum // 2 and self.rng.random() < .65):
            return DrinkPotion()
        if (actor.equipment.superpower is not None
                and battle.round_number >= actor.superpower_ready_round
                and self.rng.random() < .30):
            return UseSuperpower(target_id=self.rng.choice(friends).id)
        if self.rng.random() < .12:
            return Guard()
        weapon = actor.equipment.weapon
        if weapon and weapon.attack_type == AttackType.SUPPORT:
            # A solo support mob still has a basic melee attack.
            return Attack(target_id=self.rng.choice(foes).id, mode=AttackMode.BASIC)
        return Attack(target_id=self.rng.choice(foes).id)
