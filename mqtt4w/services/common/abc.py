from abc import ABC, abstractmethod
from typing import AsyncGenerator, List

from .structures import Message, Receiver


class AbstractService(ABC):
    @property
    @abstractmethod
    def message_receivers(self) -> List[Receiver]:
        pass

    @abstractmethod
    async def generate_message(self) -> AsyncGenerator[Message, None]:
        pass
