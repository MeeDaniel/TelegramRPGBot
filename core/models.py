"""Pure domain models: content definitions, equipment, characters and combat state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias
from uuid import UUID, uuid4


class Rarity(str, Enum):
    COMMON = 'common'
    UNCOMMON = 'uncommon'
    RARE = 'rare'
    EPIC = 'epic'
    LEGENDARY = 'legendary'
    MYTHIC = 'mythic'

    @property
    def label(self) -> str:
        return {
            Rarity.COMMON: 'Обычный', Rarity.UNCOMMON: 'Необычный',
            Rarity.RARE: 'Редкий', Rarity.EPIC: 'Эпический',
            Rarity.LEGENDARY: 'Легендарный', Rarity.MYTHIC: 'Мифический',
        }[self]


class AttackType(str, Enum):
    MELEE = 'melee'
    MAGIC = 'magic'
    RANGED = 'ranged'
    SUPPORT = 'support'


class AttackMode(str, Enum):
    WEAPON = 'weapon'
    BASIC = 'basic'


class Controller(str, Enum):
    HUMAN = 'human'
    AI = 'ai'


class BattleStatus(str, Enum):
    WAITING = 'waiting'
    FINISHED = 'finished'
    CANCELLED = 'cancelled'


@dataclass(frozen=True, slots=True)
class StatBonus:
    melee_damage: int = 0
    magic_damage: int = 0
    ranged_damage: int = 0
    max_health: int = 0
    defense: int = 0


@dataclass(frozen=True, slots=True)
class Stats:
    melee_damage: int = 1
    magic_damage: int = 1
    ranged_damage: int = 1
    max_health: int = 100
    defense: int = 0

    def with_bonuses(self, bonuses: list[StatBonus]) -> Stats:
        return Stats(**{
            name: max(0 if name != 'max_health' else 1,
                      getattr(self, name) + sum(getattr(b, name) for b in bonuses))
            for name in self.__dataclass_fields__
        })


BASE_STATS = Stats()


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemDefinition:
    id: str
    name: str
    rarity: Rarity = Rarity.COMMON
    bonus: StatBonus = field(default_factory=StatBonus)


@dataclass(frozen=True, slots=True, kw_only=True)
class Weapon(ItemDefinition):
    attack_type: AttackType = AttackType.MELEE
    support_heal: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Armor(ItemDefinition):
    guard_multiplier: float = 2.0


@dataclass(frozen=True, slots=True, kw_only=True)
class Accessory(ItemDefinition):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class Superpower(ItemDefinition):
    """MVP effect: a stat buff on the chosen allied target, effective next round."""
    effect_bonus: StatBonus = field(default_factory=StatBonus)
    duration: int = 2
    cooldown: int = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class Potion(ItemDefinition):
    heal_amount: int = 50
    cooldown: int = 3


@dataclass(frozen=True, slots=True)
class ItemInstance:
    definition_id: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Inventory:
    items: dict[UUID, ItemInstance] = field(default_factory=dict)
    consumables: dict[str, int] = field(default_factory=dict)

    def add_item(self, definition_id: str) -> UUID:
        item = ItemInstance(definition_id=definition_id)
        self.items[item.id] = item
        return item.id

    def add_consumable(self, definition_id: str, amount: int) -> None:
        if amount < 0:
            raise ValueError('Amount must be nonnegative')
        self.consumables[definition_id] = self.consumables.get(definition_id, 0) + amount

    def consume(self, definition_id: str, amount: int = 1) -> None:
        if amount < 0 or self.consumables.get(definition_id, 0) < amount:
            raise ValueError('Not enough consumables')
        self.consumables[definition_id] -= amount


@dataclass(slots=True)
class EquippedSlots:
    weapon: UUID | None = None
    armor: UUID | None = None
    accessory1: UUID | None = None
    accessory2: UUID | None = None
    superpower: UUID | None = None
    potion_id: str | None = None


@dataclass(slots=True)
class Character:
    name: str
    id: UUID = field(default_factory=uuid4)
    inventory: Inventory = field(default_factory=Inventory)
    slots: EquippedSlots = field(default_factory=EquippedSlots)


@dataclass(frozen=True, slots=True)
class Equipment:
    weapon: Weapon | None = None
    armor: Armor | None = None
    accessory1: Accessory | None = None
    accessory2: Accessory | None = None
    superpower: Superpower | None = None
    potion: Potion | None = None

    def items(self) -> tuple[ItemDefinition, ...]:
        return tuple(item for item in (
            self.weapon, self.armor, self.accessory1,
            self.accessory2, self.superpower, self.potion,
        ) if item is not None)


@dataclass(frozen=True, slots=True)
class ActiveEffect:
    source_id: UUID
    bonus: StatBonus
    starts_round: int
    ends_round: int
    name: str


@dataclass(slots=True)
class BattleParticipant:
    id: UUID
    name: str
    team_id: str
    controller: Controller
    equipment: Equipment
    current_hp: int
    potions_left: int = 0
    potion_ready_round: int = 1
    superpower_ready_round: int = 1
    effects: list[ActiveEffect] = field(default_factory=list)
    active: bool = True
    character_id: UUID | None = None

    def is_alive(self) -> bool:
        return self.active and self.current_hp > 0

    def stats(self, round_number: int) -> Stats:
        bonuses = [item.bonus for item in self.equipment.items()]
        bonuses += [e.bonus for e in self.effects
                    if e.starts_round <= round_number <= e.ends_round]
        return BASE_STATS.with_bonuses(bonuses)


@dataclass(frozen=True, slots=True)
class Attack:
    target_id: UUID
    mode: AttackMode = AttackMode.WEAPON


@dataclass(frozen=True, slots=True)
class Guard:
    pass


@dataclass(frozen=True, slots=True)
class UseSuperpower:
    target_id: UUID


@dataclass(frozen=True, slots=True)
class DrinkPotion:
    pass


BattleAction: TypeAlias = Attack | Guard | UseSuperpower | DrinkPotion


@dataclass(frozen=True, slots=True)
class CombatEvent:
    text: str
    kind: str
    actor_id: UUID | None = None
    target_id: UUID | None = None
    amount: int = 0


@dataclass(slots=True)
class Battle:
    participants: dict[UUID, BattleParticipant]
    player_team: str
    enemy_team: str
    round_number: int = 1
    id: UUID = field(default_factory=uuid4)
    status: BattleStatus = BattleStatus.WAITING
    actions: dict[UUID, BattleAction] = field(default_factory=dict)
    cancel_votes: set[UUID] = field(default_factory=set)
    winner_team: str | None = None
    finish_reason: str = ''
    location_id: str | None = None
    monster_id: str | None = None
    monster_rarity: Rarity | None = None
    drops: list[tuple[str, int]] = field(default_factory=list)
    rewards_granted: bool = False

    def living(self) -> list[BattleParticipant]:
        return [p for p in self.participants.values() if p.is_alive()]

    def ready(self) -> bool:
        return self.status == BattleStatus.WAITING and all(
            p.id in self.actions for p in self.living()
        )

    def teams_alive(self) -> set[str]:
        return {p.team_id for p in self.living()}
