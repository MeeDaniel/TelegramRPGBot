"""Explicit UTF-8 reads and deterministic atomic writes."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import fields, is_dataclass
from collections.abc import Mapping
from pathlib import Path

from .errors import ContentIOError
from .models import ContentRef, ContentWorld, ItemDefinition
from .parser import parse
from .validation import SECTIONS, KIND_FIELDS, KIND_DEFAULTS, validate


def load(path: str | Path) -> ContentWorld:
    source = str(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ContentIOError(str(error), source=source, code="read_error") from error
    return validate(parse(text, source=source))


def _json_value(value):
    if isinstance(value, ContentRef):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _json_value(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(child) for child in value]
    if is_dataclass(value):
        result = {}
        for field in fields(value):
            if isinstance(value, ItemDefinition) and field.name in KIND_FIELDS and field.name not in KIND_DEFAULTS[value.kind]:
                continue
            result[field.name] = _json_value(getattr(value, field.name))
        return result
    return value


def serialize(world: ContentWorld) -> str:
    if not isinstance(world, ContentWorld):
        from .errors import ContentError
        raise ContentError("Expected ContentWorld")
    envelope = {"schema_version": world.schema_version, "canon": world.canon}
    envelope.update({section: [_json_value(definition) for definition in getattr(world, section).values()] for section in SECTIONS})
    return json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def write_atomic(path: str | Path, text: str) -> None:
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except (OSError, UnicodeError) as error:
        raise ContentIOError(str(error), source=str(path), code="write_error") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
