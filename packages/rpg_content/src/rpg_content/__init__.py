"""Standalone immutable RPG content API."""
from .errors import ContentError, ContentIOError, UnknownContentReference, ContextBudgetExceeded
from .models import (ContentRef, ContentDocument, ContentWorld, Definition,
                     ItemDefinition, MonsterDefinition, LocationDefinition,
                     LootTableDefinition, NpcDefinition, StorySeedDefinition,
                     LoadoutDefinition, SpawnDefinition, LootEntryDefinition)
from .parser import parse
from .validation import validate
from .merge import merge
from .io import load


def build_context(world: ContentWorld, *, section: str, task: str,
                  refs: tuple[ContentRef, ...] = (), index_refs: tuple[ContentRef, ...] = (),
                  max_chars: int) -> str:
    from .context import build_context as implementation
    return implementation(world, section=section, task=task, refs=refs,
                          index_refs=index_refs, max_chars=max_chars)


__all__ = [
    "ContentError", "ContentIOError", "UnknownContentReference", "ContextBudgetExceeded",
    "ContentRef", "ContentDocument", "ContentWorld", "Definition", "ItemDefinition",
    "MonsterDefinition", "LocationDefinition", "LootTableDefinition", "NpcDefinition",
    "StorySeedDefinition", "LoadoutDefinition", "SpawnDefinition", "LootEntryDefinition",
    "parse", "load", "validate", "merge", "build_context",
]
