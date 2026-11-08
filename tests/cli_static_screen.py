"""A custom screen for public extension acceptance tests."""

from rpg_cli import Screen, ScreenView


class StaticScreen(Screen):
    """A real user-defined screen exercising the public extension seam."""

    def __init__(self, text='Custom screen', buttons=()):
        self.text = text
        self.buttons = tuple(buttons)

    def view(self):
        return ScreenView(self.text, self.buttons)
