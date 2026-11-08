from .button import Button
from .equipment import SLOTS, slot_description
from .screen import Screen
from .screen_view import ScreenView


class InventoryScreen(Screen):
    def __init__(self, context, slot=None, error=''):
        self.context = context
        self.slot = slot
        self.error = error

    def equip(self, item_id):
        try:
            self.context.game.equip(self.context.character.id, self.slot, item_id)
        except ValueError as error:
            return InventoryScreen(self.context, self.slot, str(error))
        return InventoryScreen(self.context)

    def candidates(self):
        character = self.context.character
        if self.slot == 'potion_id':
            for definition_id, item in self.context.game.catalog.items.items():
                count = character.inventory.consumables.get(definition_id, 0)
                if isinstance(item, SLOTS[self.slot][1]) and count > 0:
                    yield definition_id, f'{item.name} ×{count}'
            return
        used = {getattr(character.slots, slot) for slot in SLOTS if slot != self.slot}
        for instance in character.inventory.items.values():
            item = self.context.game.catalog.items[instance.definition_id]
            if isinstance(item, SLOTS[self.slot][1]) and instance.id not in used:
                yield instance.id, f'{item.name} [{instance.id}]'

    def view(self):
        if self.slot is None:
            buttons = tuple(Button(f'slot:{slot}', f'{label}: {slot_description(self.context, slot)}',
                                   lambda key=slot: InventoryScreen(self.context, key))
                            for slot, (label, _) in SLOTS.items())
            text = 'Инвентарь. Выберите слот.'
        else:
            candidates = tuple(self.candidates())
            buttons = tuple(Button(f'equip:{item_id}', label,
                                   lambda key=item_id: self.equip(key))
                            for item_id, label in candidates)
            buttons += (Button('unequip', 'Снять предмет', lambda: self.equip(None)),)
            text = f'{SLOTS[self.slot][0]}: {slot_description(self.context, self.slot)}'
            if not candidates:
                text += '\nНет подходящих предметов.'
        return ScreenView(text + (f'\n{self.error}' if self.error else ''), buttons + (
            Button('back', 'Назад', lambda: InventoryScreen(self.context)
                   if self.slot else self.context.home()),
            Button('home', 'Домой', self.context.home),
        ))
