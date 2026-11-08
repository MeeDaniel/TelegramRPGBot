from abc import ABC, abstractmethod

from .screen_view import ScreenView


class Screen(ABC):
    @abstractmethod
    def view(self) -> ScreenView:
        """Describe this screen without performing actions."""
