from core import Accessory, Armor, Potion, Superpower, Weapon

SLOTS = {
    'weapon': ('Оружие', Weapon),
    'armor': ('Броня', Armor),
    'accessory1': ('Аксессуар 1', Accessory),
    'accessory2': ('Аксессуар 2', Accessory),
    'superpower': ('Суперсила', Superpower),
    'potion_id': ('Зелье', Potion),
}


def slot_description(context, slot):
    character = context.character
    item_id = getattr(character.slots, slot)
    if item_id is None:
        return 'нет'
    definition_id = item_id if slot == 'potion_id' else character.inventory.items[item_id].definition_id
    item = context.game.catalog.items[definition_id]
    if slot == 'potion_id':
        return f'{item.name} ×{character.inventory.consumables.get(item_id, 0)}'
    return item.name
