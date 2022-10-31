import asyncio
from pathlib import Path
from typing import AsyncGenerator, Callable, Coroutine, List, Optional

from asyncio_mqtt.client import Client

from mqtt4w.services.common import AbstractService, Message
from mqtt4w.services.common.constants import OFFLINE, ONLINE
from mqtt4w.services.common.discovery import expand_discovery_entity


class ServicesManager:
    def __init__(
        self,
        client: Client,
        services: List[AbstractService],
        *,
        workstation_id: str,
        workstation_name: str,
        base_topic: Path,
        discovery_prefix: Path,
        discovery_enabled: bool,
        availability_subtopic: Path,
    ):
        self.running: bool = False
        self.mqtt_client = client
        self.base_topic = base_topic
        self.workstation_id = workstation_id
        self.workstation_name = workstation_name
        # TODO: normalize workstation name when using it as part of path!
        self.base_topic /= self.workstation_name
        self.discovery_prefix = discovery_prefix
        self.discovery_enabled = discovery_enabled
        self.availability_topic = base_topic / workstation_name / availability_subtopic
        self.tasks = set()
        for s in services:
            self.add_service(s)

    def add_service(self, service: AbstractService) -> None:
        self.tasks.add(service.start())
        self.tasks.add(self._send_from(service.outgoing_msg))
        if self.discovery_enabled:
            self.tasks.add(self.advertise_service(service))
        # for receiver in service.message_receivers:
        #     self.tasks.add(
        #         self._receive_to(receiver.method, receiver.topic, receiver.filter)
        #     )

    async def advertise_service(self, service: AbstractService):
        for entity in service.discovery():
            message = expand_discovery_entity(
                entity,
                self.workstation_id,
                self.base_topic,
                self.workstation_name,
                self.availability_topic,
            )
            await self.send_message(message)

    async def send_message(self, message: Message):
        if message.discovery:
            topic = self.discovery_prefix / message.topic
        else:
            topic = self.base_topic / message.topic
        payload = message.payload
        await self.mqtt_client.publish(str(topic), payload, qos=1)

    async def start_all(self) -> None:
        self.running = True
        await self.mqtt_client.publish(str(self.availability_topic), ONLINE)
        await asyncio.gather(*self.tasks)
        await self.mqtt_client.publish(str(self.availability_topic), OFFLINE)

    async def _send_from(self, outgoing_queue: asyncio.Queue) -> None:
        while self.running:
            message = await outgoing_queue.get()
            await self.send_message(message)

    # async def _receive_to(
    #     self, receiver_fn: Callable, subtopic: str, filter: Optional[str] = None
    # ) -> None:
    #     topic = str(self.base_topic / subtopic)
    #     filter = filter or topic
    #     async with self.mqtt_client.filtered_messages(filter) as messages:
    #         await self.mqtt_client.subscribe(topic)
    #         async for message in messages:
    #             await receiver_fn(message.topic, message.payload.decode())
