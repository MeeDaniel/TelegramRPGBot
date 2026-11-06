"""Build a bounded authoring prompt from an explicitly scoped snapshot."""
from __future__ import annotations

import json
from importlib import resources

from .errors import ContentError, ContentIOError, ContextBudgetExceeded
from .io import _json_value
from .models import ContentRef, ContentWorld, NpcDefinition, StorySeedDefinition
from .validation import (BONUSES, KIND_DEFAULTS, RARITIES, SECTIONS, SLOTS,
                         choice, integer, iter_references, reference, sequence, string)


def _resource(name: str) -> str:
    try:
        return resources.files("rpg_content").joinpath("resources", name).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise ContentIOError(str(error), source="bundled:" + name, code="read_error") from error


def _contract(section: str) -> str:
    """Render shared enum/default rules rather than maintaining prompt copies."""
    lines = []
    if section in ("items", "monsters", "locations"):
        lines.append("Редкости (порядок): " + ", ".join(RARITIES) + ".")
    if section == "items":
        lines.append("Бонусы: " + ", ".join(BONUSES) + "; целые, включая отрицательные, default 0.")
        for kind, defaults in KIND_DEFAULTS.items():
            lines.append(kind + ": дополнительные поля и defaults " + json.dumps(defaults, ensure_ascii=False) + ".")
    if section == "monsters":
        lines.append("Слоты и требуемый kind: " + json.dumps(SLOTS, ensure_ascii=False) + ".")
    return "\n".join(lines)


def build_context(world: ContentWorld, *, section: str, task: str,
                  refs: tuple[ContentRef, ...] = (), index_refs: tuple[ContentRef, ...] = (),
                  max_chars: int) -> str:
    if not isinstance(world, ContentWorld):
        raise ContentError("Expected ContentWorld")
    choice(section, SECTIONS, "$.section")
    string(task, "$.task", nonempty=True)
    integer(max_chars, "$.max_chars", 1)
    selections = []
    for label, values in (("refs", refs), ("index_refs", index_refs)):
        resolved = {}
        for ref in sequence(values, "$." + label):
            reference(ref, "$." + label)
            if ref not in resolved:
                resolved[ref] = world.resolve(ref)
        selections.append(resolved)
    selected, indexed = selections
    narrative = section in ("npcs", "story_seeds")
    records = []
    direct = {}
    for ref, definition in selected.items():
        if narrative:
            data = {key: getattr(definition, key) for key in ("id", "name", "description")}
            if isinstance(definition, NpcDefinition):
                data.update(role=definition.role, lines=definition.lines,
                            location=definition.location, refs=definition.refs)
            elif isinstance(definition, StorySeedDefinition):
                data.update(premise=definition.premise, hooks=definition.hooks, refs=definition.refs)
            visible_edges = iter_references(definition) if isinstance(definition, (NpcDefinition, StorySeedDefinition)) else ()
        else:
            data = definition
            visible_edges = iter_references(definition)
        records.append({"ref": str(ref), "data": _json_value(data)})
        for target, _, _ in visible_edges:
            if target not in selected:
                direct.setdefault(target, world.resolve(target))

    def summaries(values):
        return [{"type": ref.section, "id": ref.id, "name": definition.name}
                for ref, definition in values.items()]

    def formatted(value):
        return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)

    blocks = [
        _resource("common.md"),
        "Целевая секция: " + section + ". Верни envelope с schema_version: 1 и новыми записями только этой секции; остальные секции отсутствуют.",
        _resource(section + ".md"),
        _contract(section),
        "Пример структуры (ID примера не предоставляют право ссылки):\n" + _resource("examples/" + section + ".json"),
        "Задача:\n" + task.strip(),
        "Canon:\n" + world.canon,
        "Выбранные записи (профиль " + ("narrative" if narrative else "mechanical") + "):\n" + formatted(records),
        "Прямые цели, без дальнейшего раскрытия:\n" + formatted(summaries(direct)),
        "Индекс разрешённых ссылок:\n" + formatted(summaries(indexed)),
    ]
    text = "\n\n".join(block for block in blocks if block) + "\n"
    if len(text) > max_chars:
        raise ContextBudgetExceeded(len(text), max_chars)
    return text
