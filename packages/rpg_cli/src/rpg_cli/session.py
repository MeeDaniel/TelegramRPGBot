from dataclasses import replace
from typing import Callable

from .input_button import InputButton
from .screen import Screen
from .screen_view import ScreenView


class Session:
    """A screen transition machine with one optional pending typed input."""

    def __init__(self, initial_screen: Screen, on_close: Callable[[], None] = lambda: None):
        self._screen = initial_screen
        self._on_close = on_close
        self._pending = None
        self._error = ''
        self._closed = False

    def view(self) -> ScreenView | None:
        if self._closed:
            return None
        view = self._screen.view()
        return replace(view, text=view.text + (f'\n{self._error}' if self._error else ''),
                       input_prompt=self._pending.prompt if self._pending else view.input_prompt)

    def select(self, button_id: str) -> ScreenView | None:
        if self._closed:
            return None
        if self._pending:
            if button_id not in ('back', 'home'):
                return self.view()
            self._pending = None
            self._error = ''
            if button_id == 'back':
                return self.view()
        button = next((b for b in self._screen.view().buttons if b.id == button_id), None)
        if button is None:
            self._error = 'Неверный выбор.'
            return self.view()
        self._error = ''
        if isinstance(button, InputButton):
            self._pending = button
        else:
            self._transition(button.callback())
        return self.view()

    def submit_input(self, raw: str) -> ScreenView | None:
        if self._closed or self._pending is None:
            return self.view()
        if raw.strip() in ('/back', '/home'):
            return self.select(raw.strip()[1:])
        try:
            value = self._pending.parser(raw)
        except ValueError as error:
            self._error = f'Неверный ввод: {error}'
            return self.view()
        button = self._pending
        self._pending = None
        self._error = ''
        self._transition(button.callback(value))
        return self.view()

    def _transition(self, screen):
        if screen is None:
            self.close()
        else:
            self._screen = screen

    def close(self) -> None:
        if not self._closed:
            self._on_close()
            self._closed = True
            self._pending = None
