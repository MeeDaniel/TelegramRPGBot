from dataclasses import dataclass
from typing import Callable

from core import Character


@dataclass(frozen=True)
class CharacterPreset:
    id: str
    label: str
    create: Callable[[str], Character]
