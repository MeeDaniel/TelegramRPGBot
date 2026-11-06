"""Immutable content values; validation also covers direct construction."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .errors import ContentError, UnknownContentReference


_OMITTED = object()


@dataclass(frozen=True)
class ContentRef:
    section: str
    id: str

    def __post_init__(self):
        from .validation import SECTIONS, identifier, choice
        choice(self.section, SECTIONS, "$.section")
        identifier(self.id, "$.id")

    @classmethod
    def parse(cls, text: str) -> ContentRef:
        if not isinstance(text, str) or text.count(":") != 1:
            raise ContentError("Expected section:id reference", code="invalid_reference")
        return cls(*text.split(":"))

    def __str__(self):
        return f"{self.section}:{self.id}"


class _Validated:
    def __post_init__(self):
        from .validation import normalize_model
        normalize_model(self)


@dataclass(frozen=True, kw_only=True)
class ItemDefinition(_Validated):
    id: str
    name: str
    kind: str
    description: str = ""
    rarity: str = "common"
    bonus: Mapping[str, int] = field(default_factory=dict)
    attack_type: str | None = _OMITTED
    support_heal: int | None = _OMITTED
    guard_multiplier: float | None = _OMITTED
    effect_bonus: Mapping[str, int] | None = _OMITTED
    duration: int | None = _OMITTED
    cooldown: int | None = _OMITTED
    heal_amount: int | None = _OMITTED


@dataclass(frozen=True, kw_only=True)
class LoadoutDefinition(_Validated):
    weapon: ContentRef | None = None
    armor: ContentRef | None = None
    accessory1: ContentRef | None = None
    accessory2: ContentRef | None = None
    superpower: ContentRef | None = None
    potion: ContentRef | None = None
    potion_count: int = 0


@dataclass(frozen=True, kw_only=True)
class MonsterDefinition(_Validated):
    id: str
    name: str
    loadouts: Mapping[str, LoadoutDefinition]
    loot_table: ContentRef
    description: str = ""
    is_boss: bool = False


@dataclass(frozen=True, kw_only=True)
class SpawnDefinition(_Validated):
    monster: ContentRef
    weight: float


@dataclass(frozen=True, kw_only=True)
class LocationDefinition(_Validated):
    id: str
    name: str
    mode: str
    description: str = ""
    spawns: tuple[SpawnDefinition, ...] = ()
    rarity_weights: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class LootEntryDefinition(_Validated):
    item: ContentRef
    chance: float
    min_quantity: int = 1
    max_quantity: int = 1


@dataclass(frozen=True, kw_only=True)
class LootTableDefinition(_Validated):
    id: str
    name: str
    entries: tuple[LootEntryDefinition, ...]
    description: str = ""


@dataclass(frozen=True, kw_only=True)
class NpcDefinition(_Validated):
    id: str
    name: str
    role: str
    description: str = ""
    location: ContentRef | None = None
    lines: tuple[str, ...] = ()
    refs: tuple[ContentRef, ...] = ()


@dataclass(frozen=True, kw_only=True)
class StorySeedDefinition(_Validated):
    id: str
    name: str
    premise: str
    description: str = ""
    hooks: tuple[str, ...] = ()
    refs: tuple[ContentRef, ...] = ()


Definition = ItemDefinition | MonsterDefinition | LocationDefinition | LootTableDefinition | NpcDefinition | StorySeedDefinition


@dataclass(frozen=True, kw_only=True)
class ContentDocument:
    schema_version: int = 1
    canon: str = ""
    items: Mapping[str, ItemDefinition] = field(default_factory=dict)
    monsters: Mapping[str, MonsterDefinition] = field(default_factory=dict)
    locations: Mapping[str, LocationDefinition] = field(default_factory=dict)
    loot_tables: Mapping[str, LootTableDefinition] = field(default_factory=dict)
    npcs: Mapping[str, NpcDefinition] = field(default_factory=dict)
    story_seeds: Mapping[str, StorySeedDefinition] = field(default_factory=dict)
    source: str = field(default="<memory>", repr=False, compare=False)

    def __post_init__(self):
        from .validation import normalize_document
        normalize_document(self)


@dataclass(frozen=True, kw_only=True)
class ContentWorld(ContentDocument):
    def __post_init__(self):
        super().__post_init__()
        from .validation import validate_graph
        validate_graph(self)

    def resolve(self, ref: ContentRef) -> Definition:
        if not isinstance(ref, ContentRef):
            raise ContentError("Expected ContentRef", source=self.source, code="invalid_reference")
        try:
            return getattr(self, ref.section)[ref.id]
        except KeyError:
            raise UnknownContentReference(ref.section, ref.id, source=self.source) from None

    def npcs_at(self, location_id: str) -> tuple[NpcDefinition, ...]:
        ref = ContentRef("locations", location_id)
        self.resolve(ref)
        return tuple(npc for npc in self.npcs.values() if npc.location == ref)
