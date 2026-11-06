"""Project a validated content snapshot into independently owned combat models."""

from rpg_content import ContentWorld

from .models import (
    Accessory, Armor, AttackType, ItemDefinition, Potion, Rarity, StatBonus,
    Superpower, Weapon,
)
from .world import (
    Catalog, EquipmentSpec, LocationDefinition, LootEntry, LootTable,
    MonsterDefinition, SpawnEntry,
)


def to_catalog(world: ContentWorld) -> Catalog:
    """Copy mechanics into a fresh catalog, excluding narrative-only locations."""
    catalog = Catalog()
    for definition in world.items.values():
        common = dict(id=definition.id, name=definition.name,
                      rarity=Rarity(definition.rarity),
                      bonus=StatBonus(**definition.bonus))
        item: ItemDefinition
        if definition.kind == 'weapon':
            item = Weapon(**common, attack_type=AttackType(definition.attack_type),
                          support_heal=definition.support_heal)
        elif definition.kind == 'armor':
            item = Armor(**common, guard_multiplier=definition.guard_multiplier)
        elif definition.kind == 'accessory':
            item = Accessory(**common)
        elif definition.kind == 'superpower':
            item = Superpower(**common, effect_bonus=StatBonus(**definition.effect_bonus),
                              duration=definition.duration, cooldown=definition.cooldown)
        elif definition.kind == 'potion':
            item = Potion(**common, heal_amount=definition.heal_amount,
                          cooldown=definition.cooldown)
        else:
            raise ValueError(f'Unsupported item kind: {definition.kind}')
        catalog.items[item.id] = item

    for definition in world.monsters.values():
        loadouts = {}
        for rarity, loadout in definition.loadouts.items():
            slots = {}
            for slot in ('weapon', 'armor', 'accessory1', 'accessory2', 'superpower', 'potion'):
                ref = getattr(loadout, slot)
                slots[slot] = ref.id if ref is not None else None
            loadouts[Rarity(rarity)] = EquipmentSpec(**slots, potion_count=loadout.potion_count)
        catalog.monsters[definition.id] = MonsterDefinition(
            id=definition.id, name=definition.name, loadouts=loadouts,
            loot_table_id=definition.loot_table.id, is_boss=definition.is_boss,
        )

    for definition in world.loot_tables.values():
        catalog.loot_tables[definition.id] = LootTable(definition.id, tuple(
            LootEntry(entry.item.id, entry.chance, entry.min_quantity, entry.max_quantity)
            for entry in definition.entries
        ))

    for definition in world.locations.values():
        if definition.mode == 'encounter':
            catalog.locations[definition.id] = LocationDefinition(
                id=definition.id, name=definition.name,
                spawns=tuple(SpawnEntry(entry.monster.id, entry.weight)
                             for entry in definition.spawns),
                rarity_weights={Rarity(rarity): weight
                                for rarity, weight in definition.rarity_weights.items()},
            )
    return catalog
