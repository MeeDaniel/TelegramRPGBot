from dataclasses import dataclass

from .button import Button
from .input_button import InputButton


@dataclass(frozen=True)
class ScreenView:
    text: str
    buttons: tuple[Button | InputButton, ...]
    input_prompt: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'buttons', tuple(self.buttons))
