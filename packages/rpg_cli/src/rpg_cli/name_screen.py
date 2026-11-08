from .button import Button
from .input_button import InputButton
from .screen import Screen
from .screen_view import ScreenView


class NameScreen(Screen):
    def __init__(self, context):
        self.context = context

    @staticmethod
    def parse_name(raw):
        name = raw.strip()
        if not name:
            raise ValueError('Введите непустое имя.')
        return name

    def confirm(self, name):
        from .weapon_screen import WeaponScreen
        self.context.name = name
        return WeaponScreen(self.context)

    def view(self):
        return ScreenView('=== Консольная RPG ===\nСоздание героя. Имя: '
                          + (self.context.name or self.context.default_name), (
            InputButton('name', 'Ввести имя', 'Имя героя: ', self.parse_name, self.confirm),
            Button('home', 'Домой — начать с выбранными значениями', self.context.home),
            Button('exit', 'Выход', lambda: None),
        ))
