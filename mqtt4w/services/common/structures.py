from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Union


@dataclass
class Message:
    topic: Union[Path, str]
    payload: str
    discovery: bool = False


@dataclass
class Receiver:
    subtopic: str
    function: Callable
    asynchronous: bool
