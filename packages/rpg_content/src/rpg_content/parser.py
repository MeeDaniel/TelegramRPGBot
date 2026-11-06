"""Strict JSON decoding into structurally valid detached documents."""
from __future__ import annotations

import json
import math

from .errors import ContentError
from .models import ContentDocument, ContentRef, LoadoutDefinition, SpawnDefinition, LootEntryDefinition
from .validation import SECTIONS, KIND_DEFAULTS, KIND_FIELDS, SLOTS, construct, fail, mapping, section_types


class _ObjectPairs(list):
    pass


def _objects(value, path="$"):
    if isinstance(value, _ObjectPairs):
        result = {}
        for key, child in value:
            if key in result:
                fail(f"Duplicate object key: {key}", f"{path}.{key}", "duplicate_key")
            result[key] = _objects(child, f"{path}.{key}")
        return result
    if isinstance(value, list):
        return [_objects(child, f"{path}[{i}]") for i, child in enumerate(value)]
    return value


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        fail("Nonfinite numbers are forbidden", code="invalid_number")
    return value


def _constant(text):
    fail(f"Forbidden JSON constant {text}", code="invalid_number")


def _integer(text):
    try:
        return int(text)
    except ValueError as error:
        # Honor the interpreter's digit limit, while retaining our public error
        # contract instead of leaking the decoder's raw ValueError.
        raise ContentError("JSON integer exceeds the interpreter digit limit", code="invalid_number") from error


def _ref(value, path, *, nullable=False):
    if value is None and nullable:
        return None
    try:
        return ContentRef.parse(value)
    except ContentError as error:
        error.path = path
        raise


def _array(value, path):
    if not isinstance(value, list):
        fail("Expected JSON array", path)
    return value


def _decode(cls, data, path):
    mapping(data, path)
    data = dict(data)
    # JSON null only belongs to explicitly nullable reference fields.
    nullable = set(SLOTS) if cls is LoadoutDefinition else {"location"}
    for key, value in data.items():
        if value is None and key not in nullable:
            fail("Null is not allowed", f"{path}.{key}")
    name = cls.__name__
    if name == "ItemDefinition":
        kind = data.get("kind")
        if isinstance(kind, str) and kind in KIND_DEFAULTS:
            forbidden = (set(data) & KIND_FIELDS) - set(KIND_DEFAULTS[kind])
            if forbidden:
                fail(f"Fields not allowed for {kind}: {', '.join(sorted(forbidden))}", path, "unknown_field")
    elif cls is LoadoutDefinition:
        for key in SLOTS:
            if key in data:
                data[key] = _ref(data[key], f"{path}.{key}", nullable=True)
    elif name == "MonsterDefinition":
        if "loot_table" in data:
            data["loot_table"] = _ref(data["loot_table"], f"{path}.loot_table")
        if "loadouts" in data:
            mapping(data["loadouts"], f"{path}.loadouts")
            data["loadouts"] = {key: _decode(LoadoutDefinition, value, f"{path}.loadouts.{key}") for key, value in data["loadouts"].items()}
    elif name == "LocationDefinition" and "spawns" in data:
        data["spawns"] = tuple(_decode(SpawnDefinition, value, f"{path}.spawns[{i}]") for i, value in enumerate(_array(data["spawns"], f"{path}.spawns")))
    elif cls is SpawnDefinition and "monster" in data:
        data["monster"] = _ref(data["monster"], f"{path}.monster")
    elif name == "LootTableDefinition" and "entries" in data:
        data["entries"] = tuple(_decode(LootEntryDefinition, value, f"{path}.entries[{i}]") for i, value in enumerate(_array(data["entries"], f"{path}.entries")))
    elif cls is LootEntryDefinition and "item" in data:
        data["item"] = _ref(data["item"], f"{path}.item")
    elif name in ("NpcDefinition", "StorySeedDefinition"):
        if "location" in data:
            data["location"] = _ref(data["location"], f"{path}.location", nullable=True)
        if "refs" in data:
            data["refs"] = tuple(_ref(value, f"{path}.refs[{i}]") for i, value in enumerate(_array(data["refs"], f"{path}.refs")))
    return construct(cls, data, path)


def parse(text: str, source: str = "<memory>") -> ContentDocument:
    try:
        if not isinstance(text, str):
            fail("Expected JSON text")
        raw = _objects(json.loads(text, object_pairs_hook=_ObjectPairs, parse_constant=_constant,
                                  parse_float=_finite_float, parse_int=_integer))
        mapping(raw, "$")
        if set(raw) - {"schema_version", "canon", *SECTIONS}:
            key = next(iter(set(raw) - {"schema_version", "canon", *SECTIONS}))
            fail("Unknown envelope field", f"$.{key}", "unknown_field")
        if "schema_version" not in raw:
            fail("Missing schema_version", "$.schema_version", "missing_field")
        data = {"schema_version": raw["schema_version"], "canon": raw.get("canon", ""), "source": source}
        for section, cls in section_types().items():
            definitions = {}
            for i, value in enumerate(_array(raw.get(section, []), f"$.{section}")):
                definition = _decode(cls, value, f"$.{section}[{i}]")
                if definition.id in definitions:
                    fail("Duplicate ID", f"$.{section}[{i}].id", "duplicate_id")
                definitions[definition.id] = definition
            data[section] = definitions
        return ContentDocument(**data)
    except json.JSONDecodeError as error:
        raise ContentError(error.msg, source=source, path=f"$ (line {error.lineno}, column {error.colno})", code="invalid_json") from error
    except ContentError as error:
        error.source = source
        error.args = (f"{source}:{error.path}: {error.code}: {error.message}",)
        raise
