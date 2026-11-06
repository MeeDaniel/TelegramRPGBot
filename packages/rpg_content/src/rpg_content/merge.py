"""Ordered, add-only document composition."""
from collections.abc import Iterable

from .errors import ContentError
from .models import ContentDocument, ContentWorld
from .validation import SECTIONS


def merge(documents: Iterable[ContentDocument]) -> ContentWorld:
    sections = {section: {} for section in SECTIONS}
    sources = {}
    canon = ""
    version = 1
    source = "<memory>"
    for document in documents:
        if not isinstance(document, ContentDocument):
            raise ContentError("Expected ContentDocument", code="invalid_document")
        source = document.source
        if document.schema_version != version:
            raise ContentError("Incompatible schema versions", source=source, path="$.schema_version", code="schema_version")
        if canon and document.canon and canon != document.canon:
            raise ContentError("Incompatible canon", source=source, path="$.canon", code="canon_conflict")
        canon = canon or document.canon
        for section in SECTIONS:
            target = sections[section]
            for id, definition in getattr(document, section).items():
                if id in target:
                    raise ContentError(f"Duplicate ID: {id}", source=source, path=f"$.{section}.{id}", code="duplicate_id")
                target[id] = definition
                sources[(section, id)] = source
    try:
        return ContentWorld(schema_version=version, canon=canon, source=source, **sections)
    except ContentError as error:
        # Graph paths identify the referring definition, whose source can differ
        # from the last document (including when the final document is empty).
        parts = error.path.split(".", 3)
        if len(parts) >= 3:
            error.source = sources.get((parts[1], parts[2]), error.source)
            error.args = (f"{error.source}:{error.path}: {error.code}: {error.message}",)
        raise
