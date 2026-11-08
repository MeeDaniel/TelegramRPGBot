from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from .screen import Screen

T = TypeVar('T')


@dataclass(frozen=True)
class InputButton(Generic[T]):
    id: str
    label: str
    prompt: str
    parser: Callable[[str], T] = field(compare=False, repr=False)
    callback: Callable[[T], Screen | None] = field(compare=False, repr=False)
