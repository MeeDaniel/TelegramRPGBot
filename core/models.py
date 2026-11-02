"""Pure domain models: content definitions, equipment, characters and combat state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
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


@dataclass(slots=True, init=False)
class Inventory:
    items: dict[UUID, ItemInstance]
    _consumables: dict[str, int]
    _reservations: dict[UUID, tuple[str, int]] = field(repr=False)

    def __init__(self, items: dict[UUID, ItemInstance] | None = None,
                 consumables: Mapping[str, int] | None = None):
        self.items = dict(items) if items is not None else {}
        self._consumables = {}
        self._reservations = {}
        for definition_id, amount in (consumables or {}).items():
            self.add_consumable(definition_id, amount)

    @property
    def consumables(self) -> Mapping[str, int]:
        """Total stock, including quantities reserved for active participants."""
        return MappingProxyType(self._consumables)

    def _available(self, definition_id: str) -> int:
        reserved = sum(amount for item_id, amount in self._reservations.values()
                       if item_id == definition_id)
        return self._consumables.get(definition_id, 0) - reserved

    def add_item(self, definition_id: str) -> UUID:
        item = ItemInstance(definition_id=definition_id)
        self.items[item.id] = item
        return item.id

    def add_consumable(self, definition_id: str, amount: int) -> None:
        if amount < 0:
            raise ValueError('Amount must be nonnegative')
        self._consumables[definition_id] = self._consumables.get(definition_id, 0) + amount

    def consume(self, definition_id: str, amount: int = 1) -> None:
        if amount < 0 or self._available(definition_id) < amount:
            raise ValueError('Not enough consumables')
        self._consumables[definition_id] = self._consumables.get(definition_id, 0) - amount

    def _reserve(self, owner_id: UUID, definition_id: str, amount: int) -> None:
        if owner_id in self._reservations:
            raise ValueError('Participant already has a reservation')
        if amount < 0 or self._available(definition_id) < amount:
            raise ValueError('Not enough consumables')
        self._reservations[owner_id] = (definition_id, amount)

    def _consume_reserved(self, owner_id: UUID, definition_id: str) -> None:
        reserved_id, amount = self._reservations.get(owner_id, (None, 0))
        if reserved_id != definition_id or amount < 1 or self._consumables.get(definition_id, 0) < 1:
            raise ValueError('Not enough reserved consumables')
        self._consumables[definition_id] -= 1
        self._reservations[owner_id] = (definition_id, amount - 1)

    def _release(self, owner_id: UUID) -> None:
        self._reservations.pop(owner_id, None)


@dataclass(frozen=True, slots=True)
class EquippedSlots:
    weapon: UUID | None = None
    armor: UUID | None = None
    accessory1: UUID | None = None
    accessory2: UUID | None = None
    superpower: UUID | None = None
    potion_id: str | None = None

    def __post_init__(self) -> None:
        instances = [item_id for item_id in (
            self.weapon, self.armor, self.accessory1, self.accessory2, self.superpower,
        ) if item_id is not None]
        if len(instances) != len(set(instances)):
            raise ValueError('Item cannot be equipped twice')


@dataclass(slots=True, init=False)
class Character:
    name: str
    id: UUID
    inventory: Inventory
    _slots: EquippedSlots

    def __init__(self, name: str, id: UUID | None = None,
                 inventory: Inventory | None = None, slots: EquippedSlots | None = None):
        self.name = name
        self.id = id if id is not None else uuid4()
        self.inventory = inventory if inventory is not None else Inventory()
        self._slots = slots if slots is not None else EquippedSlots()

    @property
    def slots(self) -> EquippedSlots:
        return self._slots

    def _set_slot(self, slot: str, item_id: UUID | str | None) -> None:
        self._slots = replace(self._slots, **{slot: item_id})


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
    _inventory: Inventory | None = field(default=None, repr=False, compare=False)

    def is_alive(self) -> bool:
        return self.active and self.current_hp > 0

    def stats(self, round_number: int) -> Stats:
        bonuses = [item.bonus for item in self.equipment.items()]
        bonuses += [e.bonus for e in self.effects
                    if e.starts_round <= round_number <= e.ends_round]
        return BASE_STATS.with_bonuses(bonuses)

    def _consume_potion(self) -> None:
        if self.equipment.potion is None or self.potions_left < 1:
            raise ValueError('Not enough potions')
        if self._inventory is not None:
            self._inventory._consume_reserved(self.id, self.equipment.potion.id)
        self.potions_left -= 1

    def _release_potions(self) -> None:
        if self._inventory is not None:
            self._inventory._release(self.id)

    def _start_round(self, round_number: int) -> None:
        self.effects = [effect for effect in self.effects if effect.ends_round >= round_number]
        self.current_hp = max(0, min(self.current_hp, self.stats(round_number).max_health))


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
