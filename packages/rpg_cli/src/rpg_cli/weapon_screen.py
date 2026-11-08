from .button import Button
from .screen import Screen
from .screen_view import ScreenView


class WeaponScreen(Screen):
    def __init__(self, context):
        self.context = context

    def choose(self, preset_id):
        self.context.finalize(preset_id)
        return self.context.home()

    def back(self):
        from .name_screen import NameScreen
        return NameScreen(self.context)

    def view(self):
        buttons = tuple(Button(f'preset:{preset.id}', preset.label,
                               lambda key=preset.id: self.choose(key))
                        for preset in self.context.presets.values())
        return ScreenView(f'Герой: {self.context.name}\nВыберите стартовый набор:', buttons + (
            Button('back', 'Назад', self.back),
            Button('home', 'Домой', self.context.home),
            Button('exit', 'Выход', lambda: None),
        ))
