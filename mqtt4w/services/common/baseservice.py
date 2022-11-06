import logging
import pathlib
from enum import Enum
from typing import AsyncGenerator, Callable, List, NamedTuple, Union

from mqtt4w.services.common.discovery import DiscoveryEntity
from mqtt4w.services.common.structures import Message, Receiver

LOG = logging.getLogger(__name__)


class BaseService:
    def __init__(self) -> None:
        self.__senders: List[AsyncGenerator[None, Message]] = []
        self.__receivers: List[Receiver] = []
        self.__discoveries: List[DiscoveryEntity] = []
        self.__initializers: List[Callable] = []

    @property
    def discoveries(self):
        return self.__discoveries

    @property
    def senders(self):
        return self.__senders

    @property
    def receivers(self):
        return self.__receivers

    @property
    def initializers(self):
        return self.__initializers

    def register_receiver(self, subtopic: Union[str, pathlib.Path], receiver_fn):
        self.__receivers.append(Receiver(str(subtopic), receiver_fn, True))

    def register_synchronous_receiver(self, subtopic, receiver_fn):
        LOG.warning(f"Registered synchronous receiver {receiver_fn.__name__}.")
        self.__receivers.append(Receiver(str(subtopic), receiver_fn, False))

    def register_sender_gen(self, sender_fn):
        self.__senders.append(sender_fn)

    def register_initializer(self, initialize_fn):
        self.__initializers.append(initialize_fn)

    def register_discoverable(self, entity_type, entity_id, subconfig):
        self.__discoveries.append(DiscoveryEntity(entity_type, entity_id, subconfig))
