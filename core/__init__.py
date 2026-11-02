"""A framework-independent turn-based RPG engine."""

from .engine import BattleEngine, CombatCalculator, InvalidAction
from .models import (
    BASE_STATS,
    Accessory,
    Armor,
    Attack,
    AttackMode,
    AttackType,
    Battle,
    BattleParticipant,
    BattleStatus,
    Character,
    Controller,
    DrinkPotion,
    Equipment,
    Guard,
    ItemDefinition,
    Potion,
    Rarity,
    StatBonus,
    Stats,
    Superpower,
    UseSuperpower,
    Weapon,
)
from .service import GameService, InMemoryStore
from .world import (
    Catalog,
    EncounterGenerator,
    EquipmentSpec,
    LocationDefinition,
    LootEntry,
    LootGenerator,
    LootTable,
    MonsterDefinition,
    SpawnEntry,
)

__all__ = [
    'BASE_STATS', 'Accessory', 'Armor', 'Attack', 'AttackMode', 'AttackType',
    'Battle', 'BattleEngine', 'BattleParticipant', 'BattleStatus', 'Catalog',
    'Character', 'CombatCalculator', 'Controller', 'DrinkPotion',
    'EncounterGenerator', 'Equipment', 'EquipmentSpec', 'GameService',
    'Guard', 'InMemoryStore', 'InvalidAction', 'ItemDefinition',
    'LocationDefinition', 'LootEntry', 'LootGenerator', 'LootTable',
    'MonsterDefinition', 'Potion', 'Rarity', 'SpawnEntry', 'StatBonus',
    'Stats', 'Superpower', 'UseSuperpower', 'Weapon',
]
