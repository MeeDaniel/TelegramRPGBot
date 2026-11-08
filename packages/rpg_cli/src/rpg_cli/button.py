from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .screen import Screen


@dataclass(frozen=True)
class Button:
    id: str
    label: str
    callback: Callable[[], Screen | None] = field(compare=False, repr=False)
