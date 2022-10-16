from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Message:
    topic: str
    payload: Any


@dataclass
class Receiver:
    method: Callable
    topic: str
    filter: Optional[str] = None
