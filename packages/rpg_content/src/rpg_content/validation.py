"""Single source of local field rules and snapshot graph invariants."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import fields
from types import MappingProxyType
from typing import TYPE_CHECKING

from .errors import ContentError, UnknownContentReference

if TYPE_CHECKING:
    from .models import ContentDocument, ContentWorld

SECTIONS = ("items", "monsters", "locations", "loot_tables", "npcs", "story_seeds")
RARITIES = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
BONUSES = ("melee_damage", "magic_damage", "ranged_damage", "max_health", "defense")
SLOTS = {"weapon": "weapon", "armor": "armor", "accessory1": "accessory", "accessory2": "accessory", "superpower": "superpower", "potion": "potion"}
KIND_DEFAULTS = {
    "weapon": {"attack_type": "melee", "support_heal": 0},
    "armor": {"guard_multiplier": 2.0},
    "accessory": {},
    "superpower": {"effect_bonus": {}, "duration": 2, "cooldown": 3},
    "potion": {"heal_amount": 50, "cooldown": 3},
}
KIND_FIELDS = frozenset(key for defaults in KIND_DEFAULTS.values() for key in defaults)


def fail(message, path="$", code="invalid_field"):
    raise ContentError(message, path=path, code=code)


def string(value, path, *, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        fail("Expected nonempty text" if nonempty else "Expected text", path)


def identifier(value, path):
    if not isinstance(value, str) or re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", value) is None:
        fail("Invalid content ID", path, "invalid_id")


def choice(value, allowed, path):
    if not isinstance(value, str) or value not in allowed:
        fail(f"Expected one of {', '.join(allowed)}", path)


def integer(value, path, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        fail(f"Expected integer >= {minimum}" if minimum is not None else "Expected integer", path)


def number(value, path, *, minimum=0, exclusive=False, maximum=None):
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
        fail("Expected finite number", path)
    if value < minimum or (exclusive and value == minimum) or (maximum is not None and value > maximum):
        fail("Number outside allowed range", path)


def mapping(value, path):
    if not isinstance(value, Mapping):
        fail("Expected mapping", path)


def sequence(value, path):
    if not isinstance(value, (tuple, list)):
        fail("Expected sequence", path)
    return tuple(value)


def reference(value, path, section=None, *, nullable=False):
    from .models import ContentRef
    if value is None and nullable:
        return
    if not isinstance(value, ContentRef) or (section is not None and value.section != section):
        fail(f"Expected {section or 'content'} reference", path, "invalid_reference")


def bonus(value, path):
    mapping(value, path)
    unknown = set(value) - set(BONUSES)
    if unknown:
        fail("Unknown bonus field", f"{path}.{next(iter(unknown))}", "unknown_field")
    result = {key: value.get(key, 0) for key in BONUSES}
    for key, amount in result.items():
        integer(amount, f"{path}.{key}")
    return MappingProxyType(result)


def unique(values, path):
    if len(set(values)) != len(values):
        fail("Duplicate entry", path, "duplicate_entry")


def nested(value, cls, path):
    if isinstance(value, cls):
        return value
    if isinstance(value, Mapping):
        return construct(cls, dict(value), path)
    fail(f"Expected {cls.__name__}", path)


def construct(cls, data, path="$"):
    """Shape checking shared by nested constructor inputs and JSON decoding."""
    mapping(data, path)
    allowed = {f.name for f in fields(cls)}
    if set(data) - allowed:
        key = next(iter(set(data) - allowed))
        fail(f"Unknown field: {key}", f"{path}.{key}", "unknown_field")
    from dataclasses import MISSING
    missing = [f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING and f.name not in data]
    if missing:
        fail("Missing field: " + ", ".join(missing), f"{path}.{missing[0]}", "missing_field")
    try:
        return cls(**data)
    except ContentError as error:
        if error.path == "$":
            error.path = path
        elif error.path.startswith("$."):
            error.path = path + error.path[1:]
        raise


def normalize_model(model):
    from .models import (ItemDefinition, LoadoutDefinition, MonsterDefinition, SpawnDefinition,
                         LocationDefinition, LootEntryDefinition, LootTableDefinition, NpcDefinition, StorySeedDefinition,
                         _OMITTED)
    set_value = lambda key, value: object.__setattr__(model, key, value)
    if hasattr(model, "id"):
        identifier(model.id, "$.id")
        string(model.name, "$.name", nonempty=True)
        string(model.description, "$.description")
    if isinstance(model, ItemDefinition):
        choice(model.kind, KIND_DEFAULTS, "$.kind")
        choice(model.rarity, RARITIES, "$.rarity")
        set_value("bonus", bonus(model.bonus, "$.bonus"))
        defaults = KIND_DEFAULTS[model.kind]
        for key in KIND_FIELDS:
            value = getattr(model, key)
            if key not in defaults:
                if value is _OMITTED:
                    set_value(key, None)
                elif value is not None:
                    fail(f"Field {key} is not allowed for {model.kind}", f"$.{key}")
            elif value is _OMITTED:
                set_value(key, defaults[key])
        if model.kind == "weapon":
            choice(model.attack_type, ("melee", "magic", "ranged", "support"), "$.attack_type")
            integer(model.support_heal, "$.support_heal", 0)
            if model.support_heal > 0 and model.attack_type != "support":
                fail("Healing requires support attack type", "$.support_heal")
        elif model.kind == "armor":
            number(model.guard_multiplier, "$.guard_multiplier", exclusive=True)
        elif model.kind == "superpower":
            set_value("effect_bonus", bonus(model.effect_bonus, "$.effect_bonus"))
            integer(model.duration, "$.duration", 1)
            integer(model.cooldown, "$.cooldown", 0)
        elif model.kind == "potion":
            integer(model.heal_amount, "$.heal_amount", 0)
            integer(model.cooldown, "$.cooldown", 0)
    elif isinstance(model, LoadoutDefinition):
        for slot in SLOTS:
            reference(getattr(model, slot), f"$.{slot}", "items", nullable=True)
        integer(model.potion_count, "$.potion_count", 0)
        if model.potion_count and model.potion is None:
            fail("Potion count requires potion", "$.potion_count")
    elif isinstance(model, MonsterDefinition):
        mapping(model.loadouts, "$.loadouts")
        unknown = set(model.loadouts) - set(RARITIES)
        if unknown:
            fail("Unknown rarity", f"$.loadouts.{next(iter(unknown))}", "unknown_field")
        if set(model.loadouts) != set(RARITIES):
            fail("Loadouts require all six rarities", "$.loadouts")
        set_value("loadouts", MappingProxyType({rarity: nested(model.loadouts[rarity], LoadoutDefinition, f"$.loadouts.{rarity}") for rarity in RARITIES}))
        reference(model.loot_table, "$.loot_table", "loot_tables")
        if type(model.is_boss) is not bool:
            fail("Expected boolean", "$.is_boss")
    elif isinstance(model, SpawnDefinition):
        reference(model.monster, "$.monster", "monsters")
        number(model.weight, "$.weight", exclusive=True)
    elif isinstance(model, LocationDefinition):
        choice(model.mode, ("encounter", "narrative"), "$.mode")
        spawns = tuple(nested(value, SpawnDefinition, f"$.spawns[{i}]") for i, value in enumerate(sequence(model.spawns, "$.spawns")))
        unique(tuple(spawn.monster for spawn in spawns), "$.spawns")
        mapping(model.rarity_weights, "$.rarity_weights")
        weights = dict(model.rarity_weights)
        unknown = set(weights) - set(RARITIES)
        if unknown:
            fail("Unknown rarity", f"$.rarity_weights.{next(iter(unknown))}", "unknown_field")
        if model.mode == "narrative":
            if spawns or weights:
                fail("Narrative location cannot have encounter mechanics", "$")
        else:
            if not spawns or set(weights) != set(RARITIES):
                fail("Encounter requires spawns and six rarity weights", "$")
            for rarity, weight in weights.items():
                number(weight, f"$.rarity_weights.{rarity}")
            if not any(weights.values()):
                fail("At least one rarity weight must be positive", "$.rarity_weights")
            weights = {rarity: weights[rarity] for rarity in RARITIES}
        set_value("spawns", spawns)
        set_value("rarity_weights", MappingProxyType(weights))
    elif isinstance(model, LootEntryDefinition):
        reference(model.item, "$.item", "items")
        number(model.chance, "$.chance", maximum=1)
        integer(model.min_quantity, "$.min_quantity", 1)
        integer(model.max_quantity, "$.max_quantity", 1)
        if model.min_quantity > model.max_quantity:
            fail("Minimum quantity exceeds maximum", "$.min_quantity")
    elif isinstance(model, LootTableDefinition):
        entries = tuple(nested(value, LootEntryDefinition, f"$.entries[{i}]") for i, value in enumerate(sequence(model.entries, "$.entries")))
        unique(tuple(entry.item for entry in entries), "$.entries")
        set_value("entries", entries)
    elif isinstance(model, (NpcDefinition, StorySeedDefinition)):
        if isinstance(model, NpcDefinition):
            string(model.role, "$.role", nonempty=True)
            reference(model.location, "$.location", "locations", nullable=True)
            text_field = "lines"
        else:
            string(model.premise, "$.premise", nonempty=True)
            text_field = "hooks"
        texts = sequence(getattr(model, text_field), f"$.{text_field}")
        for index, text in enumerate(texts):
            string(text, f"$.{text_field}[{index}]", nonempty=True)
        set_value(text_field, texts)
        refs = sequence(model.refs, "$.refs")
        for index, ref in enumerate(refs):
            reference(ref, f"$.refs[{index}]")
        unique(refs, "$.refs")
        set_value("refs", refs)


def section_types():
    from .models import ItemDefinition, MonsterDefinition, LocationDefinition, LootTableDefinition, NpcDefinition, StorySeedDefinition
    return dict(zip(SECTIONS, (ItemDefinition, MonsterDefinition, LocationDefinition, LootTableDefinition, NpcDefinition, StorySeedDefinition)))


def normalize_document(document):
    integer(document.schema_version, "$.schema_version")
    if document.schema_version != 1:
        fail("Unsupported schema version", "$.schema_version", "schema_version")
    string(document.canon, "$.canon")
    string(document.source, "$.source", nonempty=True)
    for section, cls in section_types().items():
        values = getattr(document, section)
        mapping(values, f"$.{section}")
        copied = {}
        for key, definition in values.items():
            if not isinstance(definition, cls):
                fail(f"Expected {cls.__name__}", f"$.{section}.{key}")
            if key != definition.id:
                fail("Mapping key does not match definition ID", f"$.{section}.{key}")
            copied[key] = definition
        object.__setattr__(document, section, MappingProxyType(copied))


def iter_references(definition):
    """Yield direct typed references and paths, never chase narrative edges."""
    from .models import MonsterDefinition, LocationDefinition, LootTableDefinition, NpcDefinition, StorySeedDefinition
    if isinstance(definition, MonsterDefinition):
        yield definition.loot_table, ".loot_table", None
        for rarity, loadout in definition.loadouts.items():
            for slot, kind in SLOTS.items():
                ref = getattr(loadout, slot)
                if ref is not None:
                    yield ref, f".loadouts.{rarity}.{slot}", kind
    elif isinstance(definition, LocationDefinition):
        for i, spawn in enumerate(definition.spawns):
            yield spawn.monster, f".spawns[{i}].monster", None
    elif isinstance(definition, LootTableDefinition):
        for i, entry in enumerate(definition.entries):
            yield entry.item, f".entries[{i}].item", None
    elif isinstance(definition, (NpcDefinition, StorySeedDefinition)):
        if isinstance(definition, NpcDefinition) and definition.location is not None:
            yield definition.location, ".location", None
        for i, ref in enumerate(definition.refs):
            yield ref, f".refs[{i}]", None


def validate_graph(world):
    for section in SECTIONS:
        for definition in getattr(world, section).values():
            for ref, suffix, kind in iter_references(definition):
                path = f"$.{section}.{definition.id}{suffix}"
                try:
                    target = world.resolve(ref)
                except UnknownContentReference:
                    raise UnknownContentReference(ref.section, ref.id, source=world.source, path=path) from None
                if kind is not None and target.kind != kind:
                    raise ContentError(f"Slot requires item kind {kind}", source=world.source, path=path, code="slot_kind")


def validate(document: ContentDocument, base: ContentWorld | None = None) -> ContentWorld:
    from .models import ContentDocument, ContentWorld
    from .merge import merge
    if not isinstance(document, ContentDocument):
        fail("Expected ContentDocument")
    if base is not None and not isinstance(base, ContentWorld):
        fail("Expected ContentWorld base")
    return merge((document,) if base is None else (base, document))
