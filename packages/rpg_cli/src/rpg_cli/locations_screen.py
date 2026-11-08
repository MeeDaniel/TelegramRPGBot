from .button import Button
from .screen import Screen
from .screen_view import ScreenView


class LocationsScreen(Screen):
    def __init__(self, context, error=''):
        self.context = context
        self.error = error

    def encounter(self, location_id):
        from .battle_screen import BattleScreen
        try:
            battle = self.context.game.create_pve(self.context.character.id, location_id)
        except ValueError as error:
            return LocationsScreen(self.context, str(error))
        self.context.battle = battle
        self.context.last_result = ''
        return BattleScreen(self.context)

    def view(self):
        lines = ['Локации. Выберите место для случайного боя.']
        buttons = []
        for location in self.context.game.catalog.locations.values():
            description = self.context.world.locations.get(location.id)
            lines.append(f'{location.name}: {description.description if description else ""}')
            buttons.append(Button(f'location:{location.id}', location.name,
                                  lambda key=location.id: self.encounter(key)))
        if not buttons:
            lines.append('Доступных локаций нет.')
        if self.error:
            lines.append(self.error)
        buttons += [Button('back', 'Назад', self.context.home),
                    Button('home', 'Домой', self.context.home)]
        return ScreenView('\n'.join(lines), tuple(buttons))
