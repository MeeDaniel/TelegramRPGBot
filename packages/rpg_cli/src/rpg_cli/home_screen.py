from core import BASE_STATS

from .button import Button
from .equipment import SLOTS, slot_description
from .screen import Screen
from .screen_view import ScreenView


class HomeScreen(Screen):
    def __init__(self, context):
        self.context = context

    def inventory(self):
        from .inventory_screen import InventoryScreen
        return InventoryScreen(self.context)

    def locations(self):
        from .locations_screen import LocationsScreen
        return LocationsScreen(self.context)

    def view(self):
        equipment = self.context.game.character_equipment(self.context.character)
        stats = BASE_STATS.with_bonuses([item.bonus for item in equipment.items()])
        text = (f'Герой: {self.context.character.name}\n'
                f'HP: {stats.max_health} | Защита: {stats.defense}\n'
                f'Урон: ближний {stats.melee_damage}, магия {stats.magic_damage}, '
                f'дальний {stats.ranged_damage}\n')
        text += '\n'.join(f'{label}: {slot_description(self.context, slot)}'
                          for slot, (label, _) in SLOTS.items())
        if self.context.last_result:
            text += '\n' + self.context.last_result
        return ScreenView(text, (
            Button('inventory', 'Инвентарь', self.inventory),
            Button('locations', 'Локации', self.locations),
            Button('exit', 'Выход', lambda: None),
            Button('home', 'Домой', self.context.home),
        ))
