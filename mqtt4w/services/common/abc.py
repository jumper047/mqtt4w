import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List

from mqtt4w.services.common.discovery import DiscoveryEntity

from .structures import Message


class AbstractService(ABC):
    incoming_msg: asyncio.Queue
    outgoing_msg: asyncio.Queue

    @abstractmethod
    def discovery(self) -> List[DiscoveryEntity]:
        pass

    @abstractmethod
    async def start(self):
        pass
